"""Command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .config import build_profile, color_mode, max_file_bytes
from .errors import CueLintError
from .model import Report
from .profiles import BUILTINS, as_dict
from .rules import RULES
from .service import RunOptions, failed_threshold, run

PROFILE_KEYS = [
    ("max_line_width", "--max-line-width", "行宽"),
    ("max_lines", "--max-lines", "行数"),
    ("max_cps", "--max-cps", "CPS"),
    ("min_duration_ms", "--min-duration-ms", "最短时长"),
    ("max_duration_ms", "--max-duration-ms", "最长时长"),
    ("min_gap_ms", "--min-gap-ms", "最小间隔"),
]


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"错误：{message}", file=sys.stderr)
        raise SystemExit(2)


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text")


def _add_profile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default="cjk", help="latin/cjk/presentation/strict")
    parser.add_argument("--config", type=Path, default=None, help="TOML [profile] 配置")
    for dest, flag, label in PROFILE_KEYS:
        parser.add_argument(flag, dest=dest, type=float if dest == "max_cps" else int, default=None, help=label)


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--fail-on", choices=("error", "warning", "never"), default="error")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="cuelint", description="本地字幕质检与修复工具。", add_help=True)
    parser.add_argument("--version", action="version", version=f"cuelint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="只检查，不写字幕")
    check.add_argument("inputs", nargs="+", metavar="INPUT")
    _add_profile_args(check)
    _add_output_args(check)

    fix = sub.add_parser("fix", help="修复并写出 .fixed 字幕")
    fix.add_argument("inputs", nargs="+", metavar="INPUT")
    _add_profile_args(fix)
    _add_output_args(fix)
    fix.add_argument("--out-dir", type=Path, default=None)
    fix.add_argument("--suffix", default="fixed")
    fix.add_argument("--force", action="store_true")

    profiles = sub.add_parser("profiles", help="列出内置 profile")
    _add_format(profiles)

    rules = sub.add_parser("rules", help="列出规则")
    _add_format(rules)

    explain = sub.add_parser("explain", help="解释一条规则")
    explain.add_argument("rule_id")
    _add_format(explain)
    return parser


def _json_mode(argv: list[str]) -> bool:
    for i, arg in enumerate(argv):
        if arg == "--format" and i + 1 < len(argv) and argv[i + 1] == "json":
            return True
        if arg == "--format=json":
            return True
    return False


def _print_error(error: CueLintError, json_mode: bool) -> None:
    if json_mode:
        data: dict[str, object] = {"error": error.message, "code": error.code}
        if error.file:
            data["file"] = error.file
        if error.line is not None:
            data["line"] = error.line
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(f"错误：{error.message}", file=sys.stderr)
        if error.file:
            print(f"文件：{error.file}", file=sys.stderr)
        if error.line is not None:
            print(f"行：{error.line}", file=sys.stderr)


def _profile_from_args(args: argparse.Namespace):
    overrides = {dest: getattr(args, dest) for dest, _, _ in PROFILE_KEYS}
    try:
        return build_profile(args.profile, args.config, overrides)
    except CueLintError as exc:
        if exc.file is None and args.config is not None:
            exc.file = str(args.config)
        raise


def _paint(text: str, color: int, enabled: bool) -> str:
    return f"\033[{color}m{text}\033[0m" if enabled else text


def _text_check(report: Report, profile: str, color: bool = False) -> None:
    any_issue = False
    blocks: list[str] = []
    for file in report.files:
        lines = [f"{Path(file.input).name}  {file.format}  {file.cues} 条字幕  profile={profile}"]
        lines.append(f"  错误 {file.after.error}  警告 {file.after.warning}")
        for issue in file.issues:
            any_issue = True
            label = "[错误]" if issue.severity == "error" else "警告"
            label = _paint(label, 31 if issue.severity == "error" else 33, color)
            cue = "—" if issue.cue_index is None else f"#{issue.cue_index}"
            lines.append(f"  {label} {issue.rule}  {cue}  {issue.timecode}  {issue.message}")
            if issue.excerpt:
                lines.append(f"      {issue.excerpt}")
        blocks.append("\n".join(lines))
    print("\n\n".join(blocks))
    print()
    print(f"合计：错误 {report.after.error}  警告 {report.after.warning}")
    if not any_issue:
        print("未发现问题。")


def _text_fix(report: Report, profile: str, report_path: Path | None, color: bool = False) -> None:
    blocks: list[str] = []
    for file in report.files:
        lines = [f"{Path(file.input).name}  {file.format}  {file.cues} 条字幕  profile={profile}"]
        lines.append(f"  修复 {len(file.fixes)} 处")
        lines.append(f"  修复后：错误 {file.after.error}  警告 {file.after.warning}")
        lines.append(f"  输出：{file.output}")
        if report_path is not None:
            lines.append(f"  报告：{report_path}")
        blocks.append("\n".join(lines))
    print("\n\n".join(blocks))
    print()
    print(f"合计：修复 {report.fix_count} 处  剩余错误 {report.after.error}  剩余警告 {report.after.warning}")


def _run_files(args: argparse.Namespace, mode: str) -> int:
    profile = _profile_from_args(args)
    if mode == "fix":
        suffix = args.suffix
        if not (1 <= len(suffix) <= 20) or any(ch in suffix for ch in "/\\\x00") or suffix.startswith("."):
            raise CueLintError("usage_error", "--suffix 必须是 1–20 个字符，不能含 /、\\、NUL，且不能以 . 开头。")
    opts = RunOptions(
        mode=mode,
        profile=profile,
        profile_name=args.profile,
        max_bytes=max_file_bytes(),
        output_dir=args.out_dir if mode == "fix" else None,
        suffix=args.suffix if mode == "fix" else "fixed",
        force=args.force if mode == "fix" else False,
        report_path=args.report,
    )
    bundle = run(args.inputs, opts)
    json_mode = args.format == "json"
    use_color = False
    if not json_mode:
        mode_color = color_mode()
        use_color = mode_color == "always" or (
            mode_color == "auto" and sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"
        )
    if json_mode:
        print(json.dumps(bundle.report.to_dict(), ensure_ascii=False, indent=2))
    elif mode == "check":
        _text_check(bundle.report, args.profile, use_color)
    else:
        _text_fix(bundle.report, args.profile, bundle.report_path, use_color)
    return 1 if failed_threshold(bundle.report, args.fail_on) else 0


def _list_profiles(fmt: str) -> int:
    if fmt == "json":
        print(json.dumps({"profiles": [as_dict(BUILTINS[name]) for name in ("latin", "cjk", "presentation", "strict")]}, ensure_ascii=False))
    else:
        for name in ("latin", "cjk", "presentation", "strict"):
            p = BUILTINS[name]
            print(f"{name}  行宽 {p.max_line_width}  行数 {p.max_lines}  CPS {p.max_cps:.1f}  时长 {p.min_duration_ms}–{p.max_duration_ms} ms  间隔 {p.min_gap_ms} ms")
    return 0


def _list_rules(fmt: str) -> int:
    labels = {"auto": "可修复", "conditional": "条件可修复", "manual": "需人工"}
    if fmt == "json":
        data = {"rules": [{"id": r.id, "severity": r.severity, "fixability": r.fixability, "description": r.description} for r in RULES]}
        print(json.dumps(data, ensure_ascii=False))
    else:
        for rule in RULES:
            print(f"{rule.id}  {rule.severity}  {labels[rule.fixability]}  {rule.description}")
    return 0


def _explain(rule_id: str, fmt: str) -> int:
    rule = next((r for r in RULES if r.id == rule_id), None)
    if rule is None:
        message = f"未知规则 \"{rule_id}\"。用 cuelint rules 查看全部规则。"
        if fmt == "json":
            print(json.dumps({"error": message, "code": "unknown_rule"}, ensure_ascii=False))
        else:
            print(f"错误：{message}", file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps({"id": rule.id, "severity": rule.severity, "fixability": rule.fixability, "condition": rule.condition, "fix": rule.fix, "unfixable": rule.unfixable}, ensure_ascii=False))
    else:
        print(f"规则：{rule.id}")
        print(f"级别：{rule.severity}")
        print(f"可修复：{rule.fixability}")
        print(f"条件：{rule.condition}")
        print(f"修复：{rule.fix}")
        print(f"修不了：{rule.unfixable}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = _json_mode(argv)
    try:
        # Environment validation happens even for commands that do not use it,
        # so a broken environment fails before any file is touched.
        color_mode()
        args = build_parser().parse_args(argv)
        if args.command == "check":
            return _run_files(args, "check")
        if args.command == "fix":
            return _run_files(args, "fix")
        if args.command == "profiles":
            return _list_profiles(args.format)
        if args.command == "rules":
            return _list_rules(args.format)
        if args.command == "explain":
            return _explain(args.rule_id, args.format)
        return 2
    except CueLintError as exc:
        _print_error(exc, json_mode)
        return exc.exit_code
    except SystemExit as exc:
        return int(exc.code or 0)
    except KeyboardInterrupt:
        return 130
    except Exception:
        if json_mode:
            print(json.dumps({"error": "内部错误。", "code": "internal_error"}, ensure_ascii=False))
        else:
            print("错误：内部错误。", file=sys.stderr)
        return 70
