"""Rule definitions and pure checks. Fixing lives in fixer.py."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .model import Cue, Document, Issue
from .parser import format_timestamp
from .profiles import Profile, count_lines, cps, display_width, normalized_text, strip_markup, visible_chars


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    fixability: str
    description: str
    condition: str
    fix: str
    unfixable: str


RULES: list[Rule] = [
    Rule("empty-cue", "error", "auto", "字幕文本为空。", "去掉标记和空白后没有字符。", "删除该 cue。", "无。"),
    Rule("duplicate-cue", "warning", "auto", "两条字幕的起止时间和文本完全相同。", "规范化后 start、end、text 都相等。", "保留第一条，删除后面的。", "无。"),
    Rule("invalid-duration", "error", "manual", "字幕的结束时间不晚于开始时间。", "end_ms <= start_ms。", "无。", "保留原样；fix 整个批次不写输出。"),
    Rule("overlap", "error", "conditional", "两条字幕在时间上重叠。", "后一条 start_ms < 前一条 end_ms。", "修剪前一条的结束时间，或后移后一条的开始时间。", "两个方向都会破坏最小时长时保留原样。"),
    Rule("duration-too-short", "warning", "conditional", "字幕停留时间低于下限。", "end_ms - start_ms < min_duration_ms。", "延长结束时间，不压到下一条。", "下一条之前没有足够空间时保留原样。"),
    Rule("duration-too-long", "warning", "conditional", "字幕停留时间超过上限。", "end_ms - start_ms > max_duration_ms。", "在合法断点拆成多段，段间留 min_gap_ms。", "找不到断点、超过 8 段或任一段过短时保留原样。"),
    Rule("gap-too-small", "warning", "conditional", "相邻字幕之间的间隔低于下限。", "0 <= 下一条 start_ms - 前一条 end_ms < min_gap_ms。", "缩短前一条的结束时间。", "缩短后低于最小时长时保留原样。"),
    Rule("cps-too-high", "error", "conditional", "毎秒可见字符数超过上限。", "visible_chars / (duration_ms/1000) > max_cps。", "延长结束时间；仍超速则在合法断点拆段。", "延长和拆段都不满足时保留原样。"),
    Rule("line-too-long", "warning", "conditional", "某一行的显示宽度超过上限。", "任一行的 display_width > max_line_width。", "重新断行；必要时拆段。", "单个不可断 token 超宽或命中 complex-markup 时保留。"),
    Rule("too-many-lines", "warning", "conditional", "字幕行数超过上限。", "text 的行数 > max_lines。", "重新断行；必要时拆段。", "命中 complex-markup 或断不开时保留。"),
    Rule("control-char", "error", "auto", "字幕含控制字符。", "含 U+0000–U+0008、U+000B、U+000C、U+000E–U+001F、U+007F–U+009F。", "替换为一个半角空格，再压缩连续空格。", "无。"),
    Rule("unbalanced-markup", "warning", "manual", "i/b/u 标记没有正确闭合或嵌套。", "开闭数量不配对，或关闭顺序与栈顶不符。", "无。", "保留原样。"),
    Rule("complex-markup", "warning", "manual", "含 i/b/u 之外的标记。", "出现其他 <...> 或 {\\...} 标记。", "不做排版和拆段，只检查。", "保留原样。"),
]
RULE_BY_ID = {r.id: r for r in RULES}
RULE_ORDER = {r.id: n for n, r in enumerate(RULES)}
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
SIMPLE_TAG_RE = re.compile(r"<\s*(/?)\s*([ibu])\b([^>]*)>", re.IGNORECASE)
ANY_TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def _excerpt(text: str, limit: int = 80) -> str:
    plain = " ".join(strip_markup(normalized_text(text)).split())
    out: list[str] = []
    width = 0
    for ch in plain:
        step = 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1
        if width + step > limit:
            return "".join(out) + "…"
        out.append(ch)
        width += step
    return "".join(out)


def _issue(rule: str, cue: Cue, message: str, fixable: bool, **details) -> Issue:
    return Issue(
        rule=rule,
        severity=RULE_BY_ID[rule].severity,
        cue_index=cue.index,
        origin_index=cue.origin_index if cue.origin_index is not None else cue.index,
        line=cue.source_line,
        message=message,
        fixable=fixable,
        details=details,
        timecode=format_timestamp(cue.start_ms, separator=","),
        excerpt=_excerpt(cue.text),
    )


def markup_state(text: str) -> tuple[bool, bool]:
    """Return (complex, unbalanced) for a cue text."""
    tags = list(ANY_TAG_RE.finditer(text))
    simple = list(SIMPLE_TAG_RE.finditer(text))
    if len(tags) != len(simple):
        return True, False
    stack: list[str] = []
    for m in simple:
        closing, name = m.group(1), m.group(2).lower()
        if closing:
            if not stack or stack[-1] != name:
                return False, True
            stack.pop()
        else:
            body = m.group(0)
            if body.endswith("/>") or body.lower().startswith("<br"):
                return True, False
            stack.append(name)
    return False, bool(stack)


def duplicate_keys(doc: Document) -> set[int]:
    seen: set[tuple[int, int, str]] = set()
    dupes: set[int] = set()
    for cue in doc.cues:
        key = (cue.start_ms, cue.end_ms, normalized_text(cue.text))
        if key in seen:
            dupes.add(cue.index)
        else:
            seen.add(key)
    return dupes


def check_document(doc: Document, profile: Profile) -> list[Issue]:
    issues: list[Issue] = []
    dupes = duplicate_keys(doc)
    ordered = sorted(doc.cues, key=lambda c: (c.start_ms, c.index))
    for cue in doc.cues:
        text = normalized_text(cue.text)
        duration = cue.end_ms - cue.start_ms
        plain = strip_markup(text)
        if not plain.strip():
            issues.append(_issue("empty-cue", cue, "字幕文本为空。", True))
        if cue.index in dupes:
            kept = min(
                (c.index for c in doc.cues if c.start_ms == cue.start_ms and c.end_ms == cue.end_ms and normalized_text(c.text) == text),
                default=cue.index,
            )
            issues.append(_issue("duplicate-cue", cue, f"与 #{kept} 起止时间和文本完全相同。", True, keptCue=kept))
        if duration <= 0:
            issues.append(
                _issue("invalid-duration", cue, f"结束时间 {cue.end_ms}ms 不晚于开始时间 {cue.start_ms}ms。", False, startMs=cue.start_ms, endMs=cue.end_ms)
            )
        else:
            if duration < profile.min_duration_ms:
                issues.append(
                    _issue(
                        "duration-too-short",
                        cue,
                        f"停留 {duration}ms，低于下限 {profile.min_duration_ms}ms。",
                        True,
                        actualMs=duration,
                        minMs=profile.min_duration_ms,
                    )
                )
            if duration > profile.max_duration_ms:
                issues.append(
                    _issue(
                        "duration-too-long",
                        cue,
                        f"停留 {duration}ms，超过上限 {profile.max_duration_ms}ms。",
                        True,
                        actualMs=duration,
                        maxMs=profile.max_duration_ms,
                    )
                )
            chars = visible_chars(text)
            value = cps(text, duration)
            if chars > 0 and value > profile.max_cps:
                issues.append(
                    _issue(
                        "cps-too-high",
                        cue,
                        f"{value:.1f} 字/秒，超过上限 {profile.max_cps:.1f} 字/秒。",
                        True,
                        cps=round(value, 6),
                        limit=profile.max_cps,
                        chars=chars,
                    )
                )
        lines = text.split("\n") if text else []
        for lineno, line in enumerate(lines, 1):
            width = display_width(line)
            if width > profile.max_line_width:
                complex_markup, _ = markup_state(text)
                issues.append(
                    _issue(
                        "line-too-long",
                        cue,
                        f"第 {lineno} 行 {width} 列，超过上限 {profile.max_line_width} 列。",
                        not complex_markup,
                        line=lineno,
                        width=width,
                        limit=profile.max_line_width,
                    )
                )
                break
        nlines = count_lines(text)
        if nlines > profile.max_lines:
            complex_markup, _ = markup_state(text)
            issues.append(
                _issue(
                    "too-many-lines",
                    cue,
                    f"有 {nlines} 行，超过上限 {profile.max_lines} 行。",
                    not complex_markup,
                    lines=nlines,
                    limit=profile.max_lines,
                )
            )
        controls = len(CONTROL_RE.findall(text))
        if controls:
            issues.append(_issue("control-char", cue, f"含 {controls} 个控制字符。", True, count=controls))
        complex_markup, unbalanced = markup_state(text)
        if complex_markup:
            tags = sorted({m.group(0) for m in ANY_TAG_RE.finditer(text) if not SIMPLE_TAG_RE.fullmatch(m.group(0))})
            issues.append(_issue("complex-markup", cue, f"含不处理的标记：{', '.join(tags[:3])}。", False, tags=tags[:10]))
        elif unbalanced:
            issues.append(_issue("unbalanced-markup", cue, "i/b/u 标记没有正确闭合或嵌套。", False, tags=[]))
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt.start_ms < prev.end_ms:
            overlap = prev.end_ms - nxt.start_ms
            issues.append(_issue("overlap", nxt, f"与前一条重叠 {overlap}ms。", True, overlapMs=overlap))
        else:
            gap = nxt.start_ms - prev.end_ms
            if gap < profile.min_gap_ms:
                issues.append(
                    _issue(
                        "gap-too-small",
                        nxt,
                        f"与前一条间隔 {gap}ms，低于下限 {profile.min_gap_ms}ms。",
                        True,
                        actualMs=gap,
                        minMs=profile.min_gap_ms,
                    )
                )
    issues.sort(key=lambda x: (RULE_ORDER[x.rule], x.cue_index if x.cue_index is not None else 0, x.line or 0))
    return issues


def count_issues(issues: list[Issue]):
    from .model import Counts

    c = Counts()
    for issue in issues:
        if issue.severity == "error":
            c.error += 1
        else:
            c.warning += 1
    return c
