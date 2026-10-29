"""Deterministic repair pipeline.

Every mutation records a before/after snapshot. The pipeline never changes
wording: it removes empty/duplicate cues, replaces control characters, adjusts
timing, splits at legal token boundaries, and rewraps lines.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from .layout import best_layout, flatten_lines, split_text, tokenize
from .model import Cue, Document, Fix, Snapshot
from .profiles import Profile, count_lines, cps, display_width, normalized_text, strip_markup, visible_chars
from .rules import CONTROL_RE, markup_state

_uid = itertools.count(1)


@dataclass
class WorkingCue:
    uid: int
    origin: int
    start: int
    end: int
    text: str
    identifier: str | None
    settings: str
    source_line: int

    @property
    def duration(self) -> int:
        return self.end - self.start


def _from_cue(cue: Cue) -> WorkingCue:
    return WorkingCue(
        uid=next(_uid),
        origin=cue.origin_index if cue.origin_index is not None else cue.index,
        start=cue.start_ms,
        end=cue.end_ms,
        text=normalized_text(cue.text),
        identifier=cue.identifier,
        settings=cue.settings,
        source_line=cue.source_line,
    )


def _snapshot(cue: WorkingCue) -> Snapshot:
    return Snapshot(cue.start, cue.end, cue.text)


def _record(fixes: list[Fix], cue: WorkingCue, action: str, after: list[WorkingCue], detail: str) -> None:
    fixes.append(Fix(cue.origin, action, _snapshot(cue), [_snapshot(c) for c in after], detail))


def _clean_text(text: str) -> str:
    cleaned = CONTROL_RE.sub(" ", text)
    lines = [line for line in cleaned.split("\n")]
    lines = [" ".join(line.split(" ")) if "  " in line else line for line in lines]
    # Collapse runs of spaces introduced by control replacement, preserving
    # intentional single spaces and line structure.
    import re

    lines = [re.sub(r" {2,}", " ", line).strip(" \t") for line in lines]
    return "\n".join(lines)


def _clean(fixes: list[Fix], cues: list[WorkingCue]) -> list[WorkingCue]:
    kept: list[WorkingCue] = []
    for cue in cues:
        new_text = _clean_text(cue.text)
        if new_text != cue.text:
            before = _snapshot(cue)
            cue.text = new_text
            fixes.append(Fix(cue.origin, "remove-control", before, [_snapshot(cue)], "清理控制字符。"))
        if not strip_markup(normalized_text(cue.text)).strip():
            _record(fixes, cue, "remove-empty", [], "删除空字幕。")
            continue
        kept.append(cue)
    seen: dict[tuple[int, int, str], WorkingCue] = {}
    result: list[WorkingCue] = []
    for cue in kept:
        key = (cue.start, cue.end, normalized_text(cue.text))
        if key in seen:
            _record(fixes, cue, "remove-duplicate", [], f"与 #{seen[key].origin} 重复，保留前一条。")
            continue
        seen[key] = cue
        result.append(cue)
    return result


def _timing(fixes: list[Fix], cues: list[WorkingCue], profile: Profile) -> None:
    cues.sort(key=lambda c: (c.start, c.origin))
    for pair_index, (prev, nxt) in enumerate(zip(cues, cues[1:])):
        gap = nxt.start - prev.end
        if gap < profile.min_gap_ms:
            new_end = nxt.start - profile.min_gap_ms
            if new_end - prev.start >= profile.min_duration_ms and new_end > prev.start:
                before = _snapshot(prev)
                prev.end = new_end
                action = "trim-overlap" if gap < 0 else "trim-gap"
                fixes.append(Fix(prev.origin, action, before, [_snapshot(prev)], f"结束时间改为 {prev.end}ms，间隔 {profile.min_gap_ms}ms。"))
                continue
            new_start = prev.end + profile.min_gap_ms
            if nxt.end - new_start >= profile.min_duration_ms and new_start >= 0:
                before = _snapshot(nxt)
                nxt.start = new_start
                action = "trim-overlap" if gap < 0 else "trim-gap"
                fixes.append(Fix(nxt.origin, action, before, [_snapshot(nxt)], f"开始时间改为 {nxt.start}ms，间隔 {profile.min_gap_ms}ms。"))
                continue
            new_end = new_start + profile.min_duration_ms
            limit = nxt.start + profile.max_duration_ms
            if pair_index + 2 < len(cues):
                limit = min(limit, cues[pair_index + 2].start - profile.min_gap_ms)
            # Extending the shifted cue keeps the minimum duration without
            # stealing time from the following cue.
            if new_start >= 0 and new_end <= limit and new_end > nxt.end:
                before = _snapshot(nxt)
                nxt.start = new_start
                nxt.end = new_end
                action = "trim-overlap" if gap < 0 else "trim-gap"
                fixes.append(Fix(nxt.origin, action, before, [_snapshot(nxt)], f"开始时间改为 {new_start}ms，结束时间延长到 {new_end}ms。"))
    for i, cue in enumerate(cues):
        if cue.duration <= 0:
            continue
        if cue.duration < profile.min_duration_ms:
            limit = cue.start + profile.max_duration_ms
            if i + 1 < len(cues):
                limit = min(limit, cues[i + 1].start - profile.min_gap_ms)
            if limit - cue.start >= profile.min_duration_ms and limit > cue.end:
                before = _snapshot(cue)
                cue.end = limit
                fixes.append(Fix(cue.origin, "extend-duration", before, [_snapshot(cue)], f"结束时间延长到 {limit}ms。"))


def _extend_for_cps(fixes: list[Fix], cues: list[WorkingCue], profile: Profile) -> None:
    """Extend cues that are too fast, but never into the next cue's gap."""
    for i, cue in enumerate(cues):
        if cue.duration <= 0:
            continue
        chars = visible_chars(cue.text)
        if chars == 0 or cps(cue.text, cue.duration) <= profile.max_cps:
            continue
        needed = cue.start + math.ceil(chars / profile.max_cps * 1000)
        limit = cue.start + profile.max_duration_ms
        if i + 1 < len(cues):
            limit = min(limit, cues[i + 1].start - profile.min_gap_ms)
        target = min(needed, limit)
        if target > cue.end and target - cue.start >= profile.min_duration_ms:
            before = _snapshot(cue)
            cue.end = target
            fixes.append(
                Fix(
                    cue.origin,
                    "extend-duration",
                    before,
                    [_snapshot(cue)],
                    f"为降低语速延长到 {target}ms。",
                )
            )


def _allocate(cue: WorkingCue, chunks: list[str], profile: Profile) -> list[WorkingCue] | None:
    n = len(chunks)
    available = cue.duration - profile.min_gap_ms * (n - 1)
    if available < profile.min_duration_ms * n:
        return None
    weights = [max(1, visible_chars(chunk)) for chunk in chunks]
    extra = available - profile.min_duration_ms * n
    total = sum(weights)
    durations = [profile.min_duration_ms + (extra * w) // total for w in weights]
    for i in range(available - sum(durations)):
        durations[i % n] += 1
    if any(d <= 0 for d in durations):
        return None
    out: list[WorkingCue] = []
    cursor = cue.start
    for i, (chunk, duration) in enumerate(zip(chunks, durations)):
        out.append(
            WorkingCue(
                uid=next(_uid),
                origin=cue.origin,
                start=cursor,
                end=cursor + duration,
                text=chunk,
                identifier=cue.identifier if i == 0 else (f"{cue.identifier}-{i + 1}" if cue.identifier else None),
                settings=cue.settings if i == 0 else "",
                source_line=cue.source_line,
            )
        )
        cursor += duration + profile.min_gap_ms
    out[-1].end = cue.end
    return out


def _split(fixes: list[Fix], cues: list[WorkingCue], i: int, profile: Profile, reason: str) -> bool:
    cue = cues[i]
    if cue.duration <= 0:
        return False
    max_count = 8
    min_count = max(2, math.ceil(cue.duration / profile.max_duration_ms)) if cue.duration > profile.max_duration_ms else 2
    original_cps = cps(cue.text, cue.duration)
    for count in range(min_count, max_count + 1):
        chunks = split_text(cue.text, count, profile.max_line_width, profile.max_lines)
        if chunks is None:
            continue
        if original_cps > profile.max_cps:
            # Splitting adds gaps, so it can only make a too-fast cue worse.
            continue
        made = _allocate(cue, chunks, profile)
        if made is None:
            continue
        if any(cps(c.text, c.duration) > profile.max_cps for c in made):
            continue
        if any(c.duration > profile.max_duration_ms for c in made):
            continue
        _record(fixes, cue, "split-cue", made, f"按{reason}拆成 {len(made)} 段，间隔 {profile.min_gap_ms}ms。")
        cues[i : i + 1] = made
        return True
    return False


def _fit_one(fixes: list[Fix], cues: list[WorkingCue], i: int, profile: Profile) -> bool:
    cue = cues[i]
    complex_markup, _ = markup_state(cue.text)
    if complex_markup:
        return False
    tokens = tokenize(cue.text)
    lines = best_layout(tokens, profile.max_line_width, profile.max_lines)
    if lines is not None:
        new_text = flatten_lines(lines)
        if normalized_text(new_text) != normalized_text(cue.text):
            before = _snapshot(cue)
            cue.text = new_text
            fixes.append(Fix(cue.origin, "rewrap", before, [_snapshot(cue)], f"重排为 {len(lines)} 行。"))
        return True
    if _split(fixes, cues, i, profile, "排版"):
        return True
    return False


def _duration_split(fixes: list[Fix], cues: list[WorkingCue], i: int, profile: Profile) -> bool:
    cue = cues[i]
    if cue.duration <= profile.max_duration_ms:
        return False
    if _split(fixes, cues, i, profile, "时长"):
        return True
    return False


def fix_document(doc: Document, profile: Profile) -> tuple[Document, list[Fix]]:
    fixes: list[Fix] = []
    cues = [_from_cue(c) for c in doc.cues]
    cues = _clean(fixes, cues)
    _timing(fixes, cues, profile)
    _extend_for_cps(fixes, cues, profile)
    # Duration splitting first: it may change the text distribution per cue.
    i = 0
    while i < len(cues):
        if _duration_split(fixes, cues, i, profile):
            continue
        i += 1
    # Rewrap and split cues that still do not fit the line rules.
    i = 0
    while i < len(cues):
        cue = cues[i]
        complex_markup, _ = markup_state(cue.text)
        if not complex_markup:
            text_lines = cue.text.split("\n")
            too_wide = any(display_width(line) > profile.max_line_width for line in text_lines)
            too_many = count_lines(cue.text) > profile.max_lines
            if too_wide or too_many:
                if _fit_one(fixes, cues, i, profile):
                    continue
        i += 1
    # A second timing pass fixes gaps introduced by splitting and any overlap
    # left by a previous trim that could not satisfy the duration floor.
    _timing(fixes, cues, profile)
    cues.sort(key=lambda c: (c.start, c.origin))
    out_cues: list[Cue] = []
    for n, cue in enumerate(cues, 1):
        out_cues.append(
            Cue(
                index=n,
                start_ms=cue.start,
                end_ms=cue.end,
                text=cue.text,
                identifier=cue.identifier,
                settings=cue.settings,
                source_line=cue.source_line,
                origin_index=cue.origin,
            )
        )
    return Document(format=doc.format, cues=out_cues, header_lines=doc.header_lines, source_path=doc.source_path), fixes
