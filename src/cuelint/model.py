"""Data model shared by the parser, rules, fixer, CLI and report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Cue:
    index: int
    start_ms: int
    end_ms: int
    text: str
    identifier: str | None = None
    settings: str = ""
    source_line: int = 0
    origin_index: int | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class Document:
    format: str
    cues: list[Cue]
    header_lines: list[str] = field(default_factory=list)
    source_path: str = ""
    encoding: str = "utf-8"


@dataclass
class Snapshot:
    start_ms: int
    end_ms: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"startMs": self.start_ms, "endMs": self.end_ms, "text": self.text}


@dataclass
class Issue:
    rule: str
    severity: str
    cue_index: int | None
    origin_index: int | None
    line: int | None
    message: str
    fixable: bool
    details: dict[str, Any] = field(default_factory=dict)
    timecode: str = ""
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "cueIndex": self.cue_index,
            "originIndex": self.origin_index,
            "line": self.line,
            "message": self.message,
            "fixable": self.fixable,
            "details": self.details,
            "timecode": self.timecode,
            "excerpt": self.excerpt,
        }


@dataclass
class Fix:
    cue_index: int
    action: str
    before: Snapshot
    after: list[Snapshot]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cueIndex": self.cue_index,
            "action": self.action,
            "before": self.before.to_dict(),
            "after": [x.to_dict() for x in self.after],
            "detail": self.detail,
        }


@dataclass
class Counts:
    error: int = 0
    warning: int = 0

    @property
    def total(self) -> int:
        return self.error + self.warning

    def to_dict(self) -> dict[str, int]:
        return {"error": self.error, "warning": self.warning, "total": self.total}


@dataclass
class FileResult:
    input: str
    output: str | None
    format: str
    cues: int
    before: Counts
    after: Counts
    initial_issues: list[Issue]
    issues: list[Issue]
    fixes: list[Fix]

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "format": self.format,
            "cues": self.cues,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "initialIssues": [x.to_dict() for x in self.initial_issues],
            "issues": [x.to_dict() for x in self.issues],
            "fixes": [x.to_dict() for x in self.fixes],
        }


@dataclass
class Report:
    version: str
    generated_at: str
    profile: str
    files: list[FileResult]

    @property
    def before(self) -> Counts:
        c = Counts()
        for f in self.files:
            c.error += f.before.error
            c.warning += f.before.warning
        return c

    @property
    def after(self) -> Counts:
        c = Counts()
        for f in self.files:
            c.error += f.after.error
            c.warning += f.after.warning
        return c

    @property
    def fix_count(self) -> int:
        return sum(len(f.fixes) for f in self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "cuelint",
            "version": self.version,
            "generatedAt": self.generated_at,
            "profile": self.profile,
            "summary": {
                "files": len(self.files),
                "before": self.before.to_dict(),
                "after": self.after.to_dict(),
                "fixes": self.fix_count,
                "remaining": self.after.total,
            },
            "files": [x.to_dict() for x in self.files],
        }
