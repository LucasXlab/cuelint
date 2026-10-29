# 功能与规则

CueLint 0.1.0 只做一件事：在发布前检查 SRT / WebVTT 字幕，修掉能确定修好的问题，并把修不了的问题留在报告里。

## 输入与输出

- 输入：UTF-8 的 `.srt` 或 `.vtt`，最大 20 MiB；最多 10000 条 cue、2000000 个可见字符；单行最多 4000 字符。
- `check`：只读字幕，可写 HTML 报告。
- `fix`：写 `<名字>.fixed.srt` / `<名字>.fixed.vtt`，可改 `--suffix`、`--out-dir`，默认不覆盖。
- 输出原编码为 UTF-8、无 BOM、`\n` 换行；SRT 时间统一 `HH:MM:SS,mmm`，VTT 统一 `HH:MM:SS.mmm`。
- 多文件按命令行顺序处理；任一文件解析失败或仍有非法时长时，不写任何字幕输出。

## 13 条规则

| ID | 严重度 | 检查 | 自动修复 |
|---|---|---|---|
| `empty-cue` | error | 去掉标记和空白后没有可见字符 | 删除整条 |
| `duplicate-cue` | warning | 相邻 cue 时间与文本完全相同 | 删除后一条 |
| `invalid-duration` | error | 结束时间小于等于开始时间 | 不修，退出 1 |
| `overlap` | error | 与上一条时间重叠 | 后移开始时间；必要时延长结束 |
| `duration-too-short` | warning | 停留低于档位下限 | 在下一 cue 前延长；必要时后移下一 cue |
| `duration-too-long` | warning | 停留高于档位上限 | 拆段并分配时间 |
| `gap-too-small` | warning | 相邻 cue 间隔小于下限（含 0） | 后移后一条开始 |
| `cps-too-high` | error | 可见字符 / 秒超过上限 | 延长停留；必要时拆段 |
| `line-too-long` | warning | 任一行显示宽度超过上限 | 重新断行 |
| `too-many-lines` | warning | 行数超过上限 | 重新断行 |
| `control-char` | error | 含 C0/C1 控制字符（Tab 除外） | 替换为空格 |
| `unbalanced-markup` | error | `<i>`、`<b>`、`<u>` 未闭合或多余闭合 | 删除标记 |
| `complex-markup` | warning | 出现 `<font>`、`{\...}` 等复杂标记 | 不修 |

严重度只影响默认失败阈值和报告颜色；所有问题都会进入报告。`--fail-on error|warning|never` 控制退出码。

显示宽度：东亚宽字符（W/F）算 2 列，组合字符算 0，控制字符算 0，其余算 1。CPS 按可见 Unicode 码点计数，不计空白和标记。这样中文和英文可以用同一套行宽限制。

## 档位与覆盖

内置四个档位：`latin`、`cjk`、`presentation`、`strict`。数字见 README。它们不是平台标准，只是可复现的默认值。

优先级：内置档位 < 配置文件 < 命令行。配置文件只接受 `[profile]`，键：

```toml
[profile]
max_line_width = 36
max_lines = 2
max_cps = 9.0
min_duration_ms = 1000
max_duration_ms = 8000
min_gap_ms = 80
```

命令行可覆盖 `--max-line-width`、`--max-lines`、`--max-cps`、`--min-duration`、`--max-duration`、`--min-gap`。范围在启动时校验，越界退出 2。

## 修复策略

1. 先清理文本：控制字符换空格、去首尾空白、合并连续空格、删除空 cue、删除相邻重复 cue、处理标记。
2. 再处理时间：消除重叠、补最小间隔、补最短停留、延长过快 cue。延长只在下一条 cue 之前和档位上限内进行。
3. 最后处理排版：优先用两行放下；放不下时按词/字断行；仍然超宽或超时长时拆段。
4. 一条原 cue 最多拆成 8 段；需要 9 段时放弃拆段，保留问题。
5. 拆段时每个片段重新计算 CPS 和时长；拆分后如果更差，不拆。
6. 对输出再跑一次 `fix`，应为 0 处修复且字节相同（幂等）。

不保证所有问题都能修好。修不好时，问题会以“需人工”出现在报告和 JSON 的 `issues` 中，不会静默消失。

## 报告

- 单文件、自包含、无外部请求；CSP 禁止脚本和外部资源。
- 六个总览指标：修复前错误/警告、修复处数、修复后错误/警告、需人工。
- 每个文件一节：输入名、格式、cue 数、档位、问题表、修复预览。
- 问题表包含状态（已修复 / 仍存在 / 需人工）、规则、cue 序号、时间码、消息、原文摘录。
- 超过 20 条问题时折叠，前 20 条展开。
- 浅色/深色跟随系统；≤639px 堆叠；无横向滚动。
- 报告时间可用 `CUELINT_NOW` 固定，便于截图和测试。

## 环境变量

| 变量 | 默认 | 取值 |
|---|---|---|
| `CUELINT_COLOR` | `auto` | `auto` / `always` / `never` |
| `CUELINT_NOW` | 空 | 带时区的 ISO 8601；只影响报告时间 |
| `CUELINT_MAX_FILE_BYTES` | `20971520` | 1024–104857600 |

非法值退出 2，错误信息指出变量和允许范围。`--format json` 不输出 ANSI 颜色。
