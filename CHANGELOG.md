# 更新日志

## 0.1.0 — 2026-10-29

首个可用版本。

- SRT / WebVTT 解析与序列化，UTF-8、BOM、CRLF、1–3 位小时、逗号/点毫秒。
- 13 条字幕规则，覆盖空/重复、非法时长、重叠、停留、间隔、CPS、行宽、行数、控制字符和标记。
- `fix` 自动修复重叠、间隔、停留、CPS、断行、拆段、空/重复/控制字符；最多 8 段；幂等。
- 四个内置档位 `latin`、`cjk`、`presentation`、`strict`，支持 TOML 和命令行覆盖。
- 自包含 HTML 报告：CSP、转义、浅色/深色、375px、问题折叠、修复预览。
- 多文件批处理、原子写、输出预检、`--force` / `--out-dir` / `--suffix`。
- `check` / `fix` / `profiles` / `rules` / `explain`，文本和 JSON 输出，退出码 0/1/2/3/70。
- `CUELINT_COLOR`、`CUELINT_NOW`、`CUELINT_MAX_FILE_BYTES`。
- 94 个 pytest 用例，离线、无固定 sleep；连续三遍通过。
- MIT 许可证。
