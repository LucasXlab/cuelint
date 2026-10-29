"""SRT and WebVTT parsing and serialization.

The parser is deliberately small and strict: it accepts the common documented
shapes, preserves cue settings and header lines, and reports the source line of
every parse failure. It never guesses at a broken timestamp.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import CueLintError
from .model import Cue, Document
from .profiles import visible_chars

TIMESTAMP_RE = re.compile(r"^(\d{1,3}:\d{2}:\d{2}[,.]\d{3}|\d{1,2}:\d{2}[,.]\d{3})$")
MAX_MS = 3_599_999_999
MAX_LINE = 4000


def _err(message: str, *, file: str, line: int | None = None, code: str = "parse_error") -> CueLintError:
    return CueLintError(code, message, file=file, line=line)


def parse_timestamp(raw: str, *, file: str, line: int) -> int:
    value = raw.strip()
    if not TIMESTAMP_RE.match(value):
        raise _err(f"时间格式不正确：{value!r}。应为 HH:MM:SS,mmm 或 MM:SS.mmm。", file=file, line=line)
    if "," in value:
        main, millis = value.split(",", 1)
    else:
        main, millis = value.split(".", 1)
    parts = main.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = int(parts[1])
    else:
        raise _err(f"时间格式不正确：{value!r}。", file=file, line=line)
    if minutes >= 60 or seconds >= 60:
        raise _err(f"时间里的分钟或秒不能大于等于 60：{value!r}。", file=file, line=line)
    if hours > 999:
        raise _err(f"时间超过 999 小时：{value!r}。", file=file, line=line)
    ms = ((hours * 60 + minutes) * 60 + seconds) * 1000 + int(millis)
    if ms > MAX_MS:
        raise _err(f"时间超过 3599999999 ms：{value!r}。", file=file, line=line)
    return ms


def format_timestamp(ms: int, *, separator: str) -> str:
    if ms < 0:
        raise ValueError("negative timestamp")
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def parse_bytes(data: bytes, *, source: str = "", max_bytes: int = 20 * 1024 * 1024) -> Document:
    if len(data) > max_bytes:
        raise _err(f"文件 {len(data)} 字节，超过上限 {max_bytes} 字节。", file=source, code="input_too_large")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise _err("不支持 UTF-16 编码，请先转为 UTF-8。", file=source, code="encoding_unsupported")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _err(f"文件不是合法的 UTF-8：{exc}。", file=source, code="encoding_unsupported") from None
    if not text.strip():
        raise _err("文件为空。", file=source)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\n"):
        text = text[1:]
    lines = text.split("\n")
    for number, line in enumerate(lines, 1):
        if len(line) > MAX_LINE:
            raise _err(f"第 {number} 行有 {len(line)} 个字符，超过单行上限 {MAX_LINE}。", file=source, line=number)
    if lines and lines[0].startswith("WEBVTT"):
        return _parse_vtt(lines, source=source)
    return _parse_srt(lines, source=source)


def parse_file(path: str | Path, *, max_bytes: int = 20 * 1024 * 1024) -> Document:
    p = Path(path)
    try:
        if not p.exists():
            raise _err(f"文件不存在：{p}", file=str(p), code="input_not_found")
        if not p.is_file():
            raise _err(f"不是普通文件：{p}", file=str(p), code="input_not_file")
        size = p.stat().st_size
        if size > max_bytes:
            raise _err(f"文件 {size} 字节，超过上限 {max_bytes} 字节。", file=str(p), code="input_too_large")
        data = p.read_bytes()
    except CueLintError:
        raise
    except OSError as exc:
        raise _err(f"读取失败：{exc}", file=str(p), code="input_not_found") from None
    return parse_bytes(data, source=str(p.resolve()), max_bytes=max_bytes)


def _parse_srt(lines: list[str], *, source: str) -> Document:
    cues: list[Cue] = []
    i = 0
    while i < len(lines):
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break
        block_start = i
        block: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            block.append(lines[i])
            i += 1
        if not block:
            continue
        pos = 0
        if len(block) >= 2 and re.fullmatch(r"\d+", block[0].strip()) and "-->" in block[1]:
            pos = 1
        elif "-->" not in block[0]:
            raise _err("找不到时间行（应包含 -->）。", file=source, line=block_start + 1)
        timing = block[pos]
        start_ms, end_ms, settings = _parse_timing(timing, file=source, line_number=block_start + pos + 1)
        text = "\n".join(block[pos + 1 :])
        cues.append(
            Cue(
                index=len(cues) + 1,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                settings=settings,
                source_line=block_start + pos + 1,
                origin_index=len(cues) + 1,
            )
        )
    if not cues:
        raise _err("没有解析到任何字幕 cue。", file=source)
    _check_limits(cues, source=source)
    return Document(format="srt", cues=cues, source_path=source, encoding="utf-8")


def _parse_vtt(lines: list[str], *, source: str) -> Document:
    first = lines[0]
    if not (first == "WEBVTT" or first.startswith("WEBVTT ") or first.startswith("WEBVTT\t")):
        raise _err("WebVTT 文件的第一行必须以 WEBVTT 开头。", file=source, line=1)
    header: list[str] = []
    rest = first[len("WEBVTT") :].strip()
    if rest:
        header.append(rest)
    i = 1
    while i < len(lines) and lines[i].strip() != "":
        header.append(lines[i].strip())
        i += 1
    if len(header) > 100:
        raise _err("WebVTT 头部超过 100 行。", file=source, line=1)
    for offset, line in enumerate(header, 1):
        if len(line) > 200:
            raise _err(f"WebVTT 头部第 {offset} 行超过 200 个字符。", file=source, line=offset)
    cues: list[Cue] = []
    while i < len(lines):
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break
        block_start = i
        block: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            block.append(lines[i])
            i += 1
        if not block:
            continue
        head = block[0].strip()
        if re.match(r"^(NOTE|STYLE|REGION)(\s|$)", head):
            continue
        if any("-->" in line for line in block[:2]):
            if "-->" in block[0]:
                pos = 0
                identifier = None
            else:
                pos = 1
                identifier = block[0]
            timing = block[pos]
            start_ms, end_ms, settings = _parse_timing(timing, file=source, line_number=block_start + pos + 1)
            text = "\n".join(block[pos + 1 :])
            cues.append(
                Cue(
                    index=len(cues) + 1,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                    identifier=identifier,
                    settings=settings,
                    source_line=block_start + pos + 1,
                    origin_index=len(cues) + 1,
                )
            )
        else:
            raise _err("cue 块里找不到时间行（应包含 -->）。", file=source, line=block_start + 1)
    if not cues:
        raise _err("没有解析到任何字幕 cue。", file=source)
    _check_limits(cues, source=source)
    return Document(format="vtt", cues=cues, header_lines=header, source_path=source, encoding="utf-8")


def _parse_timing(raw: str, *, file: str, line_number: int | None = None) -> tuple[int, int, str]:
    if "-->" not in raw:
        raise _err("时间行缺少 -->。", file=file, line=line_number)
    left, right = raw.split("-->", 1)
    start_ms = parse_timestamp(left.strip(), file=file, line=line_number or 0)
    right = right.strip()
    match = TIMESTAMP_RE.match(right.split(" ", 1)[0].split("\t", 1)[0])
    if not match:
        raise _err(f"结束时间格式不正确：{right!r}。", file=file, line=line_number)
    token = match.group(0)
    end_ms = parse_timestamp(token, file=file, line=line_number or 0)
    settings = right[len(token) :].strip()
    return start_ms, end_ms, settings


def _check_limits(cues: list[Cue], *, source: str) -> None:
    if len(cues) > 10000:
        raise _err(f"字幕 cue 有 {len(cues)} 条，超过上限 10000 条。", file=source, code="input_too_large")
    total = sum(visible_chars(c.text) for c in cues)
    if total > 2_000_000:
        raise _err(f"字幕文本共 {total} 个字符，超过上限 2000000 个。", file=source, code="input_too_large")


def serialize(doc: Document) -> str:
    if doc.format == "srt":
        parts: list[str] = []
        for n, cue in enumerate(doc.cues, 1):
            timing = (
                f"{format_timestamp(cue.start_ms, separator=',')} --> "
                f"{format_timestamp(cue.end_ms, separator=',')}"
            )
            if cue.settings:
                timing += " " + cue.settings
            parts.append(f"{n}\n{timing}\n{cue.text}")
        return "\n\n".join(parts) + "\n"
    lines = ["WEBVTT"]
    lines.extend(doc.header_lines)
    lines.append("")
    for cue in doc.cues:
        if cue.identifier:
            lines.append(cue.identifier)
        timing = (
            f"{format_timestamp(cue.start_ms, separator='.')} --> "
            f"{format_timestamp(cue.end_ms, separator='.')}"
        )
        if cue.settings:
            timing += " " + cue.settings
        lines.append(timing)
        lines.extend(cue.text.split("\n"))
        lines.append("")
    return "\n".join(lines)
