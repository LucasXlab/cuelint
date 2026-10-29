"""Environment, TOML config and profile overrides."""

from __future__ import annotations

import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from .errors import CueLintError
from .profiles import PROFILE_RANGES, Profile, with_overrides

DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_CONFIG_BYTES = 64 * 1024


def max_file_bytes(environ: dict[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = env.get("CUELINT_MAX_FILE_BYTES")
    if raw is None or raw == "":
        return DEFAULT_MAX_FILE_BYTES
    try:
        value = int(raw)
    except ValueError:
        raise CueLintError("config_invalid", f"CUELINT_MAX_FILE_BYTES 必须是整数，收到 {raw!r}。") from None
    if not 1 <= value <= 100 * 1024 * 1024:
        raise CueLintError("config_invalid", "CUELINT_MAX_FILE_BYTES 必须在 1 到 104857600 之间。")
    return value


def color_mode(environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    value = env.get("CUELINT_COLOR", "auto")
    if value not in {"auto", "always", "never"}:
        raise CueLintError("config_invalid", f"CUELINT_COLOR 只能是 auto、always 或 never，收到 {value!r}。")
    return value


def now_utc(environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    raw = env.get("CUELINT_NOW")
    if raw is None or raw == "":
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise CueLintError("config_invalid", "CUELINT_NOW 不是合法的 ISO 8601 时间。") from None
    if value.tzinfo is None:
        raise CueLintError("config_invalid", "CUELINT_NOW 必须带时区，例如 2026-10-29T12:00:00Z。")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_override(key: str, value: object) -> None:
    if key not in PROFILE_RANGES:
        raise CueLintError("config_invalid", f"未知配置键 \"{key}\"。")
    kind, low, high = PROFILE_RANGES[key]
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise CueLintError("config_invalid", f"{key} 必须是整数。")
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CueLintError("config_invalid", f"{key} 必须是数字。")
    if not low <= float(value) <= high:
        raise CueLintError("config_invalid", f"{key} 必须在 {low} 到 {high} 之间。")


def read_config(path: str | Path | None) -> dict[str, object]:
    if path is None:
        return {}
    p = Path(path)
    try:
        if not p.exists():
            raise CueLintError("config_invalid", f"配置文件不存在：{p}", file=str(p))
        if not p.is_file():
            raise CueLintError("config_invalid", f"配置路径不是普通文件：{p}", file=str(p))
        size = p.stat().st_size
        if size > MAX_CONFIG_BYTES:
            raise CueLintError("config_invalid", f"配置文件 {size} 字节，超过上限 65536 字节。", file=str(p))
        raw = p.read_bytes()
    except CueLintError:
        raise
    except OSError as exc:
        raise CueLintError("config_invalid", f"读取配置失败：{exc}", file=str(p)) from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CueLintError("config_invalid", f"配置文件不是合法的 UTF-8 TOML：{exc}", file=str(p)) from None
    if set(data) - {"profile"}:
        extra = ", ".join(sorted(set(data) - {"profile"}))
        raise CueLintError("config_invalid", f"未知配置表：{extra}。只接受 [profile]。", file=str(p))
    profile = data.get("profile", {})
    if not isinstance(profile, dict):
        raise CueLintError("config_invalid", "[profile] 必须是表。", file=str(p))
    for key, value in profile.items():
        _check_override(key, value)
    return dict(profile)


def build_profile(name: str, config_path: str | Path | None, cli: dict[str, object] | None = None) -> Profile:
    data = read_config(config_path)
    for key, value in (cli or {}).items():
        if value is not None:
            _check_override(key, value)
            data[key] = value
    return with_overrides(name, data)
