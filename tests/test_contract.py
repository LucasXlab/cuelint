import json
import os
import socket
from pathlib import Path

import pytest

from cuelint.config import max_file_bytes, now_utc
from cuelint.errors import CueLintError
from cuelint.parser import parse_bytes, serialize
from cuelint.profiles import BUILTINS, display_width, visible_chars
from cuelint.service import RunOptions, run


def test_width_cjk_latin_combining():
    assert display_width("中") == 2
    assert display_width("a") == 1
    assert display_width("e\u0301") == 1
    assert visible_chars("<i>一 二</i>") == 2


def test_no_network_calls(monkeypatch, tmp_path):
    def blocked(*args, **kwargs):
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
    bundle = run([str(p)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    assert bundle.report.files[0].cues == 1


def test_output_permissions_and_atomic(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    bundle = run([str(p)], RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    out = Path(bundle.results[0].output)
    assert out.exists()
    assert oct(out.stat().st_mode & 0o777) == "0o644"


def test_parse_and_serialize_no_crash_on_utf8_text(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好，世界\n", encoding="utf-8")
    doc = parse_bytes(p.read_bytes())
    assert "你好" in serialize(doc)


def test_env_max_bytes(monkeypatch):
    monkeypatch.setenv("CUELINT_MAX_FILE_BYTES", "123")
    assert max_file_bytes() == 123
    monkeypatch.setenv("CUELINT_MAX_FILE_BYTES", "no")
    with pytest.raises(CueLintError) as exc:
        max_file_bytes()
    assert exc.value.code == "config_invalid"


def test_env_now(monkeypatch):
    monkeypatch.setenv("CUELINT_NOW", "2026-10-29T20:00:00+08:00")
    assert now_utc() == "2026-10-29T12:00:00Z"
    monkeypatch.setenv("CUELINT_NOW", "2026-10-29T12:00:00")
    with pytest.raises(CueLintError):
        now_utc()
    monkeypatch.setenv("CUELINT_NOW", "2026-10-29T12:00:00Z")
    assert now_utc() == "2026-10-29T12:00:00Z"


def test_report_path_collision(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    with pytest.raises(CueLintError) as exc:
        run([str(p)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024, report_path=p))
    assert exc.value.code == "output_collision"


def test_output_does_not_overwrite_input(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    # Same directory but default .fixed is different; force collision via out-dir is impossible,
    # so verify the default output is distinct.
    bundle = run([str(p)], RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    assert Path(bundle.results[0].output) != p
    assert p.read_text().startswith("1\n")
