import json
from pathlib import Path

import pytest

from cuelint.config import color_mode, max_file_bytes, now_utc
from cuelint.errors import CueLintError
from cuelint.parser import parse_bytes
from cuelint.profiles import BUILTINS
from cuelint.service import RunOptions, run


def test_too_many_cues():
    blocks = [f"{i+1}\n00:00:01,000 --> 00:00:02,000\nHi" for i in range(10001)]
    with pytest.raises(CueLintError) as exc:
        parse_bytes(("\n\n".join(blocks) + "\n").encode())
    assert exc.value.code == "input_too_large"


def test_header_limits():
    header = "WEBVTT\n" + "\n".join("x" * 30 for _ in range(101)) + "\n\n00:01.000 --> 00:02.000\nHi\n"
    with pytest.raises(CueLintError) as exc:
        parse_bytes(header.encode())
    assert exc.value.code == "parse_error"


def test_out_dir_missing_parent_fails(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    opts = RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024, output_dir=tmp_path / "missing" / "out")
    with pytest.raises(CueLintError) as exc:
        run([str(p)], opts)
    assert exc.value.code == "output_unwritable"


def test_duplicate_outputs_collision(tmp_path):
    a = tmp_path / "a" / "x.srt"
    b = tmp_path / "b" / "x.srt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    b.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    opts = RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024, output_dir=tmp_path / "out")
    with pytest.raises(CueLintError) as exc:
        run([str(a), str(b)], opts)
    assert exc.value.code == "output_collision"


def test_color_env_invalid():
    with pytest.raises(CueLintError) as exc:
        color_mode({"CUELINT_COLOR": "rainbow"})
    assert exc.value.code == "config_invalid"


def test_env_max_min():
    assert max_file_bytes({"CUELINT_MAX_FILE_BYTES": "1024"}) == 1024
    with pytest.raises(CueLintError):
        max_file_bytes({"CUELINT_MAX_FILE_BYTES": "1023"})


def test_now_offsets():
    assert now_utc({"CUELINT_NOW": "2026-10-29T20:00:00+08:00"}) == "2026-10-29T12:00:00Z"
    assert now_utc({"CUELINT_NOW": "2026-10-29T12:00:00Z"}) == "2026-10-29T12:00:00Z"
    with pytest.raises(CueLintError):
        now_utc({"CUELINT_NOW": "2026-10-29"})
