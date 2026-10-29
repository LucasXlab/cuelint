import pytest

from cuelint.errors import CueLintError
from cuelint.parser import format_timestamp, parse_bytes, parse_timestamp, serialize


def test_parse_srt_basic():
    doc = parse_bytes(b"1\n00:00:01,000 --> 00:00:02,500\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n")
    assert doc.format == "srt"
    assert len(doc.cues) == 2
    assert doc.cues[0].start_ms == 1000
    assert doc.cues[0].end_ms == 2500
    assert doc.cues[0].text == "Hello"
    assert doc.cues[1].source_line == 6


def test_parse_srt_without_index():
    doc = parse_bytes(b"00:00:01,000 --> 00:00:02,000\nHello\n")
    assert doc.cues[0].text == "Hello"


def test_parse_srt_dot_millis_and_settings():
    doc = parse_bytes(b"1\n00:00:01.000 --> 00:00:02.000 X1:10 X2:20\nHello\n")
    assert doc.cues[0].start_ms == 1000
    assert doc.cues[0].settings == "X1:10 X2:20"


def test_parse_vtt_header_identifier_and_note():
    text = "WEBVTT - demo\n\nNOTE 跳过\n这一段\n\ncue-1\n00:01.000 --> 00:02.000 align:start\nHello\n"
    doc = parse_bytes(text.encode())
    assert doc.format == "vtt"
    assert doc.header_lines == ["- demo"]
    assert len(doc.cues) == 1
    assert doc.cues[0].identifier == "cue-1"
    assert doc.cues[0].settings == "align:start"
    assert doc.cues[0].start_ms == 1000


def test_parse_vtt_style_region_skipped():
    doc = parse_bytes(b"WEBVTT\n\nSTYLE\n::cue { color: red }\n\nREGION\nid:r1\n\n00:01.000 --> 00:02.000\nHi\n")
    assert len(doc.cues) == 1


def test_bom_and_crlf():
    doc = parse_bytes(b"\xef\xbb\xbf1\r\n00:00:01,000 --> 00:00:02,000\r\nHello\r\n")
    assert doc.cues[0].text == "Hello"


def test_parse_rejects_empty_and_no_cues():
    with pytest.raises(CueLintError) as exc:
        parse_bytes(b"")
    assert exc.value.code == "parse_error"
    with pytest.raises(CueLintError):
        parse_bytes(b"WEBVTT\n")


def test_parse_rejects_bad_timestamp():
    for bad in [b"1\n00:00:60,000 --> 00:00:02,000\nx\n", b"1\n00:00:01,1000 --> 00:00:02,000\nx\n"]:
        with pytest.raises(CueLintError) as exc:
            parse_bytes(bad)
        assert exc.value.code == "parse_error"


def test_parse_rejects_utf16():
    with pytest.raises(CueLintError) as exc:
        parse_bytes("1\n00:00:01,000 --> 00:00:02,000\n嗨\n".encode("utf-16"))
    assert exc.value.code == "encoding_unsupported"


def test_parse_rejects_overlong_line():
    with pytest.raises(CueLintError) as exc:
        parse_bytes(b"1\n00:00:01,000 --> 00:00:02,000\n" + b"x" * 4001 + b"\n")
    assert exc.value.code == "parse_error"
    assert exc.value.line == 3


def test_parse_file_limits_and_missing(tmp_path):
    from cuelint.parser import parse_file

    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n")
    with pytest.raises(CueLintError) as exc:
        parse_file(p, max_bytes=5)
    assert exc.value.code == "input_too_large"
    with pytest.raises(CueLintError) as exc:
        parse_file(tmp_path / "missing.srt")
    assert exc.value.code == "input_not_found"


def test_serialize_srt_roundtrip():
    doc = parse_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n")
    text = serialize(doc)
    assert text == "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n"
    assert serialize(parse_bytes(text.encode())) == text


def test_serialize_vtt_roundtrip():
    text = "WEBVTT - demo\n\nid\n00:01.000 --> 00:02.000 align:start\nHello\n"
    doc = parse_bytes(text.encode())
    once = serialize(doc)
    assert once == "WEBVTT\n- demo\n\nid\n00:00:01.000 --> 00:00:02.000 align:start\nHello\n"
    assert serialize(parse_bytes(once.encode())) == once


def test_timestamp_helpers():
    assert parse_timestamp("1:02:03,004", file="x", line=1) == 3_723_004
    assert parse_timestamp("02:03.004", file="x", line=1) == 123_004
    assert format_timestamp(3_723_004, separator=",") == "01:02:03,004"
