import json
import os
from pathlib import Path

import pytest

from cuelint.cli import main


@pytest.fixture
def run(capsys):
    def _run(args, env=None):
        old = {}
        if env:
            for key, value in env.items():
                old[key] = os.environ.get(key)
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        try:
            code = main(args)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def srt(*blocks: tuple[str, str, str]) -> str:
    parts = []
    for i, (start, end, text) in enumerate(blocks, 1):
        parts.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(parts) + "\n"


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def json_out(text: str):
    return json.loads(text)
