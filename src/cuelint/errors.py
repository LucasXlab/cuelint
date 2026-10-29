"""Typed errors that map to stable CLI exit codes and machine codes."""

from __future__ import annotations


class CueLintError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 2,
        file: str | None = None,
        line: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.file = file
        self.line = line
