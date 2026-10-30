# 开发与测试

## 环境

- Python 3.11+（开发机用 3.13.5）
- pytest 9.x（仅测试依赖）
- 运行时只用标准库，不依赖网络、浏览器、音视频库

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m pytest
```

## 目录

```text
src/cuelint/
  cli.py        argparse、文本/JSON 输出、退出码
  parser.py     SRT/VTT 解析、限制、序列化
  rules.py      13 条规则
  layout.py     显示宽度、断行 DP、拆段 DP
  fixer.py      清理、时间轴、断行、拆段
  profiles.py   档位、宽度/CPS 计算
  service.py    多文件编排、预检、原子写
  report.py     HTML 报告
  config.py     TOML、环境变量、时间
tests/          89 个 pytest 用例
examples/       可直接运行的中文字幕样本
```

## 测试原则

- 全部在 `tmp_path` 中运行，不读写用户文件。
- 不联网：一个用例在进程内把 `socket.socket.connect` 替换成抛异常，然后跑完整 `fix`。
- 不用固定 `sleep`；性能用例只测单次上限。
- 解析失败、非法时长、输出已存在、输出不可写、报告冲突都有独立用例。
- 每个可修复规则至少有一个命中、一个不命中、一个修不了的用例。
- 连续运行三遍必须全部通过；不允许 skip/xfail。当前记录见 `notes/test-runs.txt`。

## 性能

测试集包含 2000 条 cue 的检查用例（<5 秒）。SPEC 的目标是 10000 条 cue、每条 40 字符在 Apple M 系列 / Python 3.11 上不超过 5 秒；不在 README 写未实测的绝对数字，只写测试约束。

## 修改规则时的检查单

1. 改 `rules.py` 的规则定义和 `_issue` 字段。
2. 如果可自动修复，改 `fixer.py` 并加 `Fix.action`。
3. 加/改 `tests/test_rules.py` 和 `tests/test_fixer.py`。
4. 如果影响报告状态，改 `report.py` 并加 `tests/test_report.py`。
5. 更新 `docs/features.md`、`SPEC.md`（如契约变了）、`CHANGELOG.md`。
6. 跑三遍 `python -m pytest`。

## 发布前

```bash
python -m pytest
python -m build --sdist --wheel   # 可选，需要 build
pipx install .
cuelint --version
git tag v0.1.0
```

版本号只在 `pyproject.toml` 和 `src/cuelint/__init__.py`；改版本要同时改两处，并更新 `CHANGELOG.md`。
