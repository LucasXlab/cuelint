"""Built-in subtitle profiles and the text measurements rules rely on."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from .errors import CueLintError

TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")

PROFILE_NAMES = ("latin", "cjk", "presentation", "strict")


@dataclass(frozen=True)
class Profile:
    name: str
    max_line_width: int
    max_lines: int
    max_cps: float
    min_duration_ms: int
    max_duration_ms: int
    min_gap_ms: int


BUILTINS: dict[str, Profile] = {
    "latin": Profile("latin", 42, 2, 17.0, 1000, 7000, 80),
    "cjk": Profile("cjk", 36, 2, 9.0, 1000, 8000, 80),
    "presentation": Profile("presentation", 32, 2, 15.0, 1500, 6000, 120),
    "strict": Profile("strict", 37, 2, 15.0, 1200, 6000, 120),
}

DEFAULT_PROFILE = "cjk"

PROFILE_RANGES = {
    "max_line_width": (int, 10, 100),
    "max_lines": (int, 1, 4),
    "max_cps": (float, 1.0, 30.0),
    "min_duration_ms": (int, 200, 10000),
    "max_duration_ms": (int, 1000, 60000),
    "min_gap_ms": (int, 0, 1000),
}


def get_profile(name: str) -> Profile:
    try:
        return BUILTINS[name]
    except KeyError:
        raise CueLintError(
            "usage_error",
            f"未知 profile \"{name}\"。可用：latin、cjk、presentation、strict。",
        ) from None


def as_dict(profile: Profile) -> dict:
    return {
        "name": profile.name,
        "maxLineWidth": profile.max_line_width,
        "maxLines": profile.max_lines,
        "maxCps": profile.max_cps,
        "minDurationMs": profile.min_duration_ms,
        "maxDurationMs": profile.max_duration_ms,
        "minGapMs": profile.min_gap_ms,
    }


def strip_markup(text: str) -> str:
    return TAG_RE.sub("", text)


def normalized_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u200b", "")
    return "\n".join(line.strip(" \t") for line in text.split("\n"))


def count_lines(text: str) -> int:
    return 0 if text == "" else text.count("\n") + 1


def visible_chars(text: str) -> int:
    plain = strip_markup(text)
    return sum(1 for ch in plain if not ch.isspace())


def display_width(text: str) -> int:
    plain = strip_markup(text)
    total = 0
    for ch in plain:
        category = unicodedata.category(ch)
        if category in {"Mn", "Me"}:
            continue
        if ch == "\t":
            total += 1
            continue
        if category in {"Cc", "Cf"}:
            continue
        total += 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1
    return total


def cps(text: str, duration_ms: int) -> float:
    if duration_ms <= 0:
        return 0.0
    return visible_chars(text) / (duration_ms / 1000.0)


def validate_profile(profile: Profile) -> Profile:
    values = {
        "max_line_width": profile.max_line_width,
        "max_lines": profile.max_lines,
        "max_cps": profile.max_cps,
        "min_duration_ms": profile.min_duration_ms,
        "max_duration_ms": profile.max_duration_ms,
        "min_gap_ms": profile.min_gap_ms,
    }
    for key, (kind, low, high) in PROFILE_RANGES.items():
        value = values[key]
        if kind is int and (not isinstance(value, int) or isinstance(value, bool)):
            raise CueLintError("config_invalid", f"{key} 必须是整数。")
        if kind is float and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise CueLintError("config_invalid", f"{key} 必须是数字。")
        if not low <= float(value) <= high:
            raise CueLintError("config_invalid", f"{key} 必须在 {low} 到 {high} 之间。")
    if profile.max_duration_ms <= profile.min_duration_ms:
        raise CueLintError("config_invalid", "max_duration_ms 必须大于 min_duration_ms。")
    if profile.min_gap_ms >= profile.min_duration_ms:
        raise CueLintError("config_invalid", "min_gap_ms 必须小于 min_duration_ms。")
    return profile


def with_overrides(name: str, overrides: dict[str, object]) -> Profile:
    base = get_profile(name)
    data = asdict(base)
    for key, value in overrides.items():
        if key not in PROFILE_RANGES:
            raise CueLintError("config_invalid", f"未知配置键 \"{key}\"。")
        if value is None:
            continue
        data[key] = float(value) if key == "max_cps" else int(value)
    data["name"] = base.name
    return validate_profile(Profile(**data))
