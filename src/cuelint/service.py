"""Orchestration: parse, check, fix, preflight and write outputs."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import now_utc
from .errors import CueLintError
from .fixer import fix_document
from .model import Counts, FileResult, Report
from .parser import parse_file, serialize
from .profiles import Profile
from .rules import check_document, count_issues


@dataclass
class RunOptions:
    mode: str
    profile: Profile
    profile_name: str
    max_bytes: int
    output_dir: Path | None = None
    suffix: str = "fixed"
    force: bool = False
    report_path: Path | None = None


@dataclass
class Bundle:
    report: Report
    report_path: Path | None
    results: list[FileResult]


def _input_paths(paths: list[str]) -> list[Path]:
    resolved = [Path(p).expanduser().resolve() for p in paths]
    seen: set[Path] = set()
    for path in resolved:
        if path in seen:
            raise CueLintError("usage_error", f"输入文件重复：{path}", file=str(path))
        seen.add(path)
    return resolved


def _output_path(input_path: Path, fmt: str, opts: RunOptions) -> Path:
    stem = input_path.stem if input_path.suffix else input_path.name
    name = f"{stem}.{opts.suffix}.{fmt}"
    return (opts.output_dir / name) if opts.output_dir else (input_path.parent / name)


def _same_path(a: Path, b: Path) -> bool:
    if a.resolve() == b.resolve():
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _preflight(outputs: list[Path], inputs: list[Path], force: bool) -> None:
    seen: set[Path] = set()
    for path in outputs:
        resolved = path.resolve()
        if any(_same_path(resolved, other) for other in seen):
            raise CueLintError("output_collision", f"两个输入产生同一个输出：{resolved}", file=str(resolved))
        seen.add(resolved)
        if any(_same_path(resolved, input_path) for input_path in inputs):
            raise CueLintError("output_collision", f"输出路径与输入相同：{resolved}", file=str(resolved))
        parent = resolved.parent
        if not parent.exists() or not parent.is_dir():
            raise CueLintError("output_unwritable", f"输出目录不存在：{parent}", file=str(resolved), exit_code=3)
        if resolved.is_dir():
            raise CueLintError("output_unwritable", f"输出路径是目录：{resolved}", file=str(resolved), exit_code=3)
        if resolved.exists() and not force:
            raise CueLintError(
                "output_exists",
                f"输出文件已存在：{resolved}。加 --force 覆盖，或换 --out-dir。",
                file=str(resolved),
                exit_code=3,
            )
        if not os.access(parent, os.W_OK):
            raise CueLintError("output_unwritable", f"输出目录不可写：{parent}", file=str(resolved), exit_code=3)


def _prepare_report(path: Path | None, inputs: list[Path], outputs: list[Path]) -> Path | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if any(_same_path(resolved, other) for other in inputs) or any(_same_path(resolved, other) for other in outputs):
        raise CueLintError("output_collision", f"报告路径与输入或输出相同：{resolved}", file=str(resolved))
    if not resolved.parent.exists() or not resolved.parent.is_dir():
        raise CueLintError("output_unwritable", f"报告目录不存在：{resolved.parent}", file=str(resolved))
    if resolved.exists() and resolved.is_dir():
        raise CueLintError("output_unwritable", f"报告路径是目录：{resolved}", file=str(resolved))
    return resolved


def _atomic_write(path: Path, text: str) -> None:
    fd = -1
    tmp_name = ""
    try:
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".cuelint-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp_name, 0o644 & ~mask)
        os.replace(tmp_name, path)
        tmp_name = ""
    except OSError as exc:
        raise CueLintError("output_unwritable", f"写入失败：{exc}", file=str(path), exit_code=3) from None
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def run(paths: list[str], opts: RunOptions) -> Bundle:
    inputs = _input_paths(paths)
    docs = [parse_file(p, max_bytes=opts.max_bytes) for p in inputs]

    if opts.output_dir is not None:
        out_dir = opts.output_dir.expanduser().resolve()
        if out_dir.exists() and not out_dir.is_dir():
            raise CueLintError("output_unwritable", f"--out-dir 不是目录：{out_dir}", file=str(out_dir))
        if not out_dir.exists():
            try:
                out_dir.mkdir()
            except OSError as exc:
                raise CueLintError("output_unwritable", f"创建输出目录失败：{exc}", file=str(out_dir)) from None
        opts.output_dir = out_dir

    results: list[FileResult] = []
    outputs: list[Path] = []
    rendered: list[tuple[Path, str]] = []
    for input_path, doc in zip(inputs, docs):
        initial = check_document(doc, opts.profile)
        before = count_issues(initial)
        if opts.mode == "check":
            results.append(
                FileResult(
                    input=str(input_path),
                    output=None,
                    format=doc.format,
                    cues=len(doc.cues),
                    before=before,
                    after=before,
                    initial_issues=initial,
                    issues=initial,
                    fixes=[],
                )
            )
            continue
        fixed_doc, fixes = fix_document(doc, opts.profile)
        if not fixed_doc.cues:
            raise CueLintError(
                "all_cues_removed",
                f"{input_path.name} 删除空字幕后没有可写出的 cue，未写出任何文件。",
                exit_code=1,
                file=str(input_path),
            )
        after_issues = check_document(fixed_doc, opts.profile)
        bad = [i for i in after_issues if i.rule == "invalid-duration"]
        if bad:
            cues = ", ".join(f"#{i.origin_index}" for i in bad)
            raise CueLintError(
                "unfixable_timing",
                f"{input_path} 仍有非法时长，未写出任何文件：{cues}",
                file=str(input_path),
                exit_code=1,
            )
        out_path = _output_path(input_path, fixed_doc.format, opts)
        outputs.append(out_path)
        rendered.append((out_path, serialize(fixed_doc)))
        results.append(
            FileResult(
                input=str(input_path),
                output=str(out_path),
                format=fixed_doc.format,
                cues=len(fixed_doc.cues),
                before=before,
                after=count_issues(after_issues),
                initial_issues=initial,
                issues=after_issues,
                fixes=fixes,
            )
        )

    report_path = _prepare_report(opts.report_path, inputs, outputs)
    if opts.mode == "fix":
        _preflight(outputs, inputs, opts.force)
        for path, text in rendered:
            _atomic_write(path, text)
    report = Report(
        version=__version__,
        generated_at=now_utc(),
        profile=opts.profile_name,
        files=results,
    )
    if report_path is not None:
        from .report import render_report

        _atomic_write(report_path, render_report(report))
    return Bundle(report=report, report_path=report_path, results=results)


def failed_threshold(report: Report, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    for file in report.files:
        if file.after.error:
            return True
        if fail_on == "warning" and file.after.warning:
            return True
    return False
