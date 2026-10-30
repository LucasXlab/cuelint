import json

import pytest

from cuelint.errors import CueLintError
from cuelint.fixer import fix_document
from cuelint.parser import parse_bytes, serialize
from cuelint.profiles import BUILTINS
from cuelint.rules import check_document
from cuelint.service import RunOptions, run

CJK = BUILTINS["cjk"]


def opts(mode="fix", **kw):
    return RunOptions(mode=mode, profile=CJK, profile_name="cjk", max_bytes=20 * 1024 * 1024, **kw)


def test_terminal_excerpt_strips_ansi(run, tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello \x1b[31mRED\x1b[0m world\n")
    code, out, _ = run(["check", str(p)])
    assert "\x1b[" not in out
    assert "hello" in out


def test_invalid_duration_fix_writes_nothing(run, tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:02,500 --> 00:00:03,000\na\n\n2\n00:00:02,900 --> 00:00:02,800\nb\n")
    code, out, _ = run(["fix", str(p), "--format", "json"])
    assert code == 1 and json.loads(out)["code"] == "unfixable_timing"
    assert not (tmp_path / "a.fixed.srt").exists()


def test_complex_markup_not_split_or_rewrapped():
    text = '<font color="red">' + "一二三四五六七八九十" * 6 + "</font>"
    d = parse_bytes(f"1\n00:00:00,000 --> 00:00:20,000\n{text}\n".encode())
    out, fixes = fix_document(d, CJK)
    assert len(out.cues) == 1 and out.cues[0].text == text
    assert fixes == []


def test_timestamp_limit_respected_and_output_reparseable():
    d = parse_bytes(b"1\n999:59:58,000 --> 999:59:58,500\nshort\n")
    out, _ = fix_document(d, CJK)
    assert all(c.end_ms <= 3_599_999_999 for c in out.cues)
    assert serialize(parse_bytes(serialize(out).encode())) == serialize(out)


def test_invalid_now_writes_nothing(run, tmp_path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    code, out, _ = run(["fix", str(p), "--format", "json"], env={"CUELINT_NOW": "not-a-time"})
    assert code == 2 and json.loads(out)["code"] == "config_invalid"
    assert not (tmp_path / "a.fixed.srt").exists()


def test_unfixable_breakpoint_flags():
    d = parse_bytes(("1\n00:00:00,000 --> 00:00:20,000\n" + "x" * 100 + "\n").encode())
    issues = check_document(d, CJK)
    flags = {i.rule: i.fixable for i in issues}
    assert flags["duration-too-long"] is False
    assert flags["line-too-long"] is False


def test_gap_only_does_not_shift_next_cue():
    d = parse_bytes(b"1\n00:00:00,000 --> 00:00:01,000\na\n\n2\n00:00:01,050 --> 00:00:03,000\nb\n")
    out, _ = fix_document(d, CJK)
    assert out.cues[1].start_ms == 1050


def test_i_self_closing_is_unbalanced():
    d = parse_bytes(b"1\n00:00:01,000 --> 00:00:02,000\n<i/>hi\n")
    assert [i.rule for i in check_document(d, CJK)] == ["unbalanced-markup"]


def test_intentional_double_spaces_untouched():
    d = parse_bytes(b"1\n00:00:00,000 --> 00:00:03,000\naa  aa\n")
    out, fixes = fix_document(d, CJK)
    assert out.cues[0].text == "aa  aa"
    assert fixes == []


def test_srt_rejects_mm_ss_but_vtt_accepts():
    with pytest.raises(CueLintError) as exc:
        parse_bytes(b"1\n00:01,000 --> 00:02,000\nHi\n")
    assert exc.value.code == "parse_error"
    doc = parse_bytes(b"WEBVTT\n\n00:01.000 --> 00:02.000\nHi\n")
    assert doc.format == "vtt" and doc.cues[0].start_ms == 1000


def test_vtt_header_preserved_and_bom_encoding():
    text = "WEBVTT\n  indented header\n\n00:01.000 --> 00:02.000\nHi\n"
    doc = parse_bytes(text.encode())
    assert doc.header_lines == ["  indented header"]
    assert serialize(doc) == "WEBVTT\n  indented header\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
    bom = b"\xef\xbb\xbf" + b"1\n00:00:01,000 --> 00:00:02,000\nHi\n"
    assert parse_bytes(bom).encoding == "utf-8-sig"


def test_complex_only_cue_is_not_empty_or_deleted():
    d = parse_bytes(b"1\n00:00:01,000 --> 00:00:02,000\n<font></font>\n")
    assert "empty-cue" not in [i.rule for i in check_document(d, CJK)]
    out, _ = fix_document(d, CJK)
    assert len(out.cues) == 1
