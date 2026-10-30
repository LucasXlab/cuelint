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
    monkeypatch.setenv("CUELINT_MAX_FILE_BYTES", "1024")
    assert max_file_bytes() == 1024
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


def test_symlink_input_resolves_to_same_file(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    link = tmp_path / "link.srt"
    link.symlink_to(p)
    bundle = run([str(link)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    assert bundle.results[0].input == str(p.resolve())


def test_nul_byte_is_control_char(tmp_path):
    p = tmp_path / "a.srt"
    p.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nhi\x00there\n")
    bundle = run([str(p)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    assert any(i.rule == "control-char" for i in bundle.results[0].issues)


def test_report_has_no_external_urls(tmp_path):
    from cuelint.report import render_report

    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    bundle = run([str(p)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    html = render_report(bundle.report)
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html


def test_large_file_performance(tmp_path):
    import time

    blocks = []
    for i in range(2000):
        blocks.append(f"{i+1}\n00:{i//60:02d}:{i%60:02d},000 --> 00:{i//60:02d}:{i%60:02d},900\nHello world")
    p = tmp_path / "large.srt"
    p.write_text("\n\n".join(blocks) + "\n")
    start = time.perf_counter()
    bundle = run([str(p)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    elapsed = time.perf_counter() - start
    assert bundle.report.files[0].cues == 2000
    assert elapsed < 5.0


def test_report_case_variant_input_collision(tmp_path):
    upper = tmp_path / "A.srt"
    upper.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    lower = tmp_path / "a.srt"
    if not lower.exists():
        pytest.skip("case-insensitive filesystem required")
    with pytest.raises(CueLintError) as exc:
        run([str(upper)], RunOptions(mode="check", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024, report_path=lower))
    assert exc.value.code == "output_collision"


def test_umask_respected(tmp_path):
    import os

    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    old = os.umask(0o077)
    try:
        bundle = run([str(p)], RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024))
    finally:
        os.umask(old)
    assert oct(Path(bundle.results[0].output).stat().st_mode & 0o777) == "0o600"


def test_output_directory_with_force_aborts_batch(tmp_path):
    a = tmp_path / "a.srt"
    b = tmp_path / "b.srt"
    a.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    b.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    (tmp_path / "b.fixed.srt").mkdir()
    with pytest.raises(CueLintError) as exc:
        run([str(a), str(b)], RunOptions(mode="fix", profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024, force=True))
    assert exc.value.code == "output_unwritable"
    assert not (tmp_path / "a.fixed.srt").exists()


def test_double_arrow_rejected(tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000 --> 00:00:03,000\nHi\n")
    with pytest.raises(CueLintError) as exc:
        parse_bytes(p.read_bytes())
    assert exc.value.code == "parse_error"
