"""Deterministic line breaking and cue splitting.

Text is tokenised once, then a dynamic program picks the break points with the
smallest sum of squared slack. This is the concrete meaning of "balanced" in
SPEC.md: no character is dropped, CJK breaks are allowed between characters,
Latin words are never split, and markup tags have zero width.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .profiles import display_width, normalized_text

TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")
CLOSING_PUNCT = set("。，、！？；：,.!?;:)]}）】》」』〉”’…")
OPENING_PUNCT = set("([{（【《〈「『“‘")


@dataclass(frozen=True)
class Token:
    text: str
    kind: str  # word, cjk, space, tag


def _is_cjk(ch: str) -> bool:
    if ch in CLOSING_PUNCT or ch in OPENING_PUNCT:
        return True
    return unicodedata.east_asian_width(ch) in {"W", "F"}


def tokenize(text: str) -> list[Token]:
    text = normalized_text(text).replace("\n", " ")
    tokens: list[Token] = []
    for part in re.split(r"(<[^>]*>|\{\\[^}]*\})", text):
        if not part:
            continue
        if TAG_RE.fullmatch(part):
            tokens.append(Token(part, "tag"))
        else:
            for chunk in re.findall(r"\s+|\S+", part):
                if chunk.isspace():
                    tokens.append(Token(" ", "space"))
                    continue
                run: list[str] = []
                for ch in chunk:
                    if _is_cjk(ch):
                        if run:
                            tokens.append(Token("".join(run), "word"))
                            run = []
                        tokens.append(Token(ch, "cjk"))
                    else:
                        run.append(ch)
                if run:
                    tokens.append(Token("".join(run), "word"))
    return tokens


def _breakable(tokens: list[Token], j: int) -> bool:
    if j <= 0 or j >= len(tokens):
        return False
    prev, nxt = tokens[j - 1], tokens[j]
    if prev.kind == "space" or nxt.kind == "space":
        return True
    if prev.kind == "tag" or nxt.kind == "tag":
        return True
    prev_text, next_text = prev.text[-1:], nxt.text[:1]
    if prev_text in OPENING_PUNCT or next_text in CLOSING_PUNCT:
        return False
    if prev.kind == "cjk" or nxt.kind == "cjk":
        return True
    return False


def _line_text(tokens: list[Token]) -> str:
    return "".join(t.text for t in tokens).strip(" ")


def best_layout(tokens: list[Token], max_width: int, max_lines: int, rebalance: bool = True) -> list[str] | None:
    n = len(tokens)
    if n == 0:
        return []
    # dp[line_count][i] = (cost, previous boundary)
    inf = float("inf")
    dp: list[list[tuple[float, int] | None]] = [[None] * (n + 1) for _ in range(max_lines + 1)]
    dp[0][0] = (0.0, -1)
    widths = [0] * (n + 1)
    for i, tok in enumerate(tokens, 1):
        widths[i] = widths[i - 1] + (0 if tok.kind == "tag" else 1)
    for lines in range(1, max_lines + 1):
        for i in range(1, n + 1):
            if i != n and not _breakable(tokens, i):
                continue
            best: tuple[float, int] | None = None
            for j in range(0, i):
                if j > 0 and not _breakable(tokens, j):
                    continue
                prev = dp[lines - 1][j]
                if prev is None:
                    continue
                line = _line_text(tokens[j:i])
                if not line:
                    continue
                width = display_width(line)
                if width > max_width:
                    continue
                cost = prev[0] + (max_width - width) ** 2
                if best is None or cost < best[0]:
                    best = (cost, j)
            dp[lines][i] = best
    chosen: int | None = None
    chosen_cost = inf
    for lines in range(1, max_lines + 1):
        if dp[lines][n] is not None and dp[lines][n][0] < chosen_cost:
            chosen = lines
            chosen_cost = dp[lines][n][0]
    if chosen is None:
        return None
    boundaries: list[int] = [n]
    i = n
    for lines in range(chosen, 0, -1):
        prev = dp[lines][i]
        assert prev is not None
        j = prev[1]
        boundaries.append(j)
        i = j
    boundaries.reverse()
    lines_out: list[str] = []
    for left, right in zip(boundaries, boundaries[1:]):
        line = _line_text(tokens[left:right])
        if line:
            lines_out.append(line)
    return _rebalance(lines_out) if rebalance else lines_out


def _rebalance(lines: list[str]) -> list[str]:
    closing = {"i": "</i>", "b": "</b>", "u": "</u>"}
    out: list[str] = []
    carry: list[str] = []
    for line in lines:
        prefix = "".join(f"<{tag}>" for tag in carry)
        stack = list(carry)
        for match in re.finditer(r"<\s*(/?)\s*([ibu])\b[^>]*>", line, re.IGNORECASE):
            closing_tag, name = match.group(1), match.group(2).lower()
            if closing_tag:
                if stack and stack[-1] == name:
                    stack.pop()
            else:
                stack.append(name)
        suffix = "".join(closing[tag] for tag in reversed(stack))
        out.append(prefix + line + suffix)
        carry = stack
    return out


def flatten_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def fit_text(text: str, max_width: int, max_lines: int) -> str | None:
    tokens = tokenize(text)
    lines = best_layout(tokens, max_width, max_lines)
    if lines is None:
        return None
    return flatten_lines(lines)


def split_text(text: str, count: int, max_width: int, max_lines: int) -> list[str] | None:
    if count < 2 or count > 8:
        return None
    tokens = tokenize(text)
    n = len(tokens)
    if n == 0:
        return None
    # dp[k][i] = (max_chunk_width, previous_j) for k chunks covering first i tokens
    inf = float("inf")
    dp: list[list[tuple[float, int] | None]] = [[None] * (n + 1) for _ in range(count + 1)]
    dp[0][0] = (0.0, -1)
    for k in range(1, count + 1):
        for i in range(1, n + 1):
            if i != n and not _breakable(tokens, i):
                continue
            best: tuple[float, int] | None = None
            for j in range(0, i):
                if j > 0 and not _breakable(tokens, j):
                    continue
                prev = dp[k - 1][j]
                if prev is None:
                    continue
                lines = best_layout(tokens[j:i], max_width, max_lines, rebalance=False)
                if lines is None:
                    continue
                width = max((display_width(line) for line in lines), default=0)
                value = max(prev[0], width)
                if best is None or value < best[0]:
                    best = (value, j)
            dp[k][i] = best
    if dp[count][n] is None:
        return None
    boundaries: list[int] = [n]
    i = n
    for k in range(count, 0, -1):
        prev = dp[k][i]
        assert prev is not None
        j = prev[1]
        boundaries.append(j)
        i = j
    boundaries.reverse()
    chunks: list[str] = []
    for left, right in zip(boundaries, boundaries[1:]):
        lines = best_layout(tokens[left:right], max_width, max_lines, rebalance=False)
        if lines is None:
            return None
        chunks.append(flatten_lines(lines))
    return _rebalance_chunks(chunks)


def _rebalance_chunks(chunks: list[str]) -> list[str]:
    closing = {"i": "</i>", "b": "</b>", "u": "</u>"}
    carry: list[str] = []
    out: list[str] = []
    for chunk in chunks:
        prefix = "".join(f"<{tag}>" for tag in carry)
        stack = list(carry)
        for match in re.finditer(r"<\s*(/?)\s*([ibu])\b[^>]*>", chunk, re.IGNORECASE):
            closing_tag, name = match.group(1), match.group(2).lower()
            if closing_tag:
                if stack and stack[-1] == name:
                    stack.pop()
            else:
                stack.append(name)
        suffix = "".join(closing[tag] for tag in reversed(stack))
        out.append(prefix + chunk + suffix)
        carry = stack
    return out
