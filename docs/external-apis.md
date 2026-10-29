# 已核实的外部依据

核实日期：2026-10-29（America/New_York）。项目运行时不调用任何外部 API、不联网、不读取密钥。本文件记录解析和默认阈值依据的公开文档，以及核实结果。

## 1. 运行时代码用到的外部接口

**没有。** `cuelint` 只用 Python 3.11 标准库：

- 文件读写：`pathlib`、`os`、`tempfile`；
- 时间：`datetime`、`zoneinfo`（不按本地时区计算）；
- 解析：`re`、`unicodedata`、`html`；
- 配置：`tomllib`；
- 命令行：`argparse`。

代码里没有 `urllib`、`http.client`、`requests`、`socket` 的调用。测试 `test_no_network` 在进程内把 `socket.socket` 替换为抛异常后运行完整 `fix`，证明这一点。

## 2. 格式与算法依据

| 用途 | 文档 | 链接 | 核实结果 |
|---|---|---|---|
| WebVTT 解析和输出 | W3C《WebVTT: The Web Video Text Tracks Format》 | https://www.w3.org/TR/webvtt1/ | 2026-10-29 返回 200；确认 `WEBVTT` 头、时间戳 `HH:MM:SS.mmm` 或 `MM:SS.mmm`、cue identifier、cue settings 的位置 |
| SRT 解析 | FFmpeg `libavformat/srtdec.c`（事实标准实现） | https://github.com/FFmpeg/FFmpeg/blob/master/libavformat/srtdec.c | 2026-10-29 返回 200；确认序号行可选、时间行格式、逗号毫秒、空行分块、坐标尾缀 |
| 显示宽度 | Unicode Standard Annex #11《East Asian Width》 | https://www.unicode.org/reports/tr11/ | 2026-10-29 返回 200；使用 `unicodedata.east_asian_width` 的 `W`/`F` 记 2 列 |
| 可读性阈值参考 | Netflix Timed Text Style Guide: Subtitle Timing Guidelines | https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines | 2026-10-29 返回 200；只用于人工核对默认值的量级，不声称符合 Netflix 认证 |
| 可读性阈值参考 | BBC Subtitle Guidelines | https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/ | 2026-10-29 返回 200；只用于人工核对断行和阅读速度的量级 |
| TOML 解析 | Python 3.11 `tomllib` 文档 | https://docs.python.org/3/library/tomllib.html | 2026-10-29 返回 200；确认只读、UTF-8、解析失败抛 `TOMLDecodeError` |

## 3. 默认值来源和边界

- `max_cps`（9.0 字/秒、17.0 字/秒、15.0 字/秒）是 CueLint 的默认值。Netflix 和 BBC 的公开指南给出的数字按语言和受众不同而不同；CueLint 不声称通过任何平台的验收。
- `max_line_width` 以“显示列”计：CJK 全角字符 2 列，拉丁字符 1 列。`cjk` 的 36 列对应一行 18 个汉字；`latin` 的 42 列对应 42 个拉丁字符。
- 这些值可以在 `cuelint.toml` 的 `[profile]` 里覆盖，范围见 `SPEC.md` 3.2。
- 不读取平台的上传规则，不检查平台特定的字符集或字体；报告里不出现“通过 YouTube/Netflix/B 站审核”这类断言。

## 4. 未核实、因此不进入代码的内容

- 不解析 ASS/SSA 的特效标签；`complex-markup` 只识别并保留，不解释。
- 不读取音频/视频时长，不检查字幕是否与语音对齐。
- 不调用任何翻译或大模型接口。
- 不解析字幕中的图片、字体附件或 Matroska 容器。
