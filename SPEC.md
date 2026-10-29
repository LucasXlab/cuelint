# CueLint 规格

版本：0.1.0（本文件与代码同版本）。本文件是唯一契约：命令、参数、字段名、规则编号、退出码、默认值必须与代码一致。实现中与本文不一致的地方，逐条记入 `docs/deviations.md`；本文没写的边界，按“最简单、能跑通”处理并补记。

## 0. 产品说明与范围

CueLint 是一个本地运行的字幕质检与修复命令行工具。输入已有的 SRT 或 WebVTT 文件，按一个明确的 profile 检查可读性，修掉能安全修的问题，输出修好的字幕和一份可复查的 HTML 报告。

第一版只做一条核心流程：

```bash
cuelint fix episode-07.srt --profile cjk --report report.html
```

读入一份字幕，检查并修复，写出 `episode-07.fixed.srt` 和 `report.html`，在终端给出修复前后的问题数。

非目标：

- 不做语音转写、听打、翻译、说话人识别。
- 不做字幕时间轴与音频的强制对齐；不读取音频或视频文件。
- 不编辑 ASS/SSA、图形字幕、卡拉 OK 逐字特效。
- 不做图形界面、账号体系、云同步、上传、遥测、联网请求。
- 不发布到 PyPI，不创建远程仓库，不推送；只在本地构建和安装。仓库里提供 CI 配置，只有在用户自己创建远程仓库并推送后才会运行。

## 1. 运行环境与安装

- Python 3.11 或更高版本。开发机使用 3.11.9；CI 使用 3.11 和 3.12 两个版本。
- 运行时只使用 Python 标准库，没有第三方运行时依赖。
- 安装：

  ```bash
  python3.11 -m pip install --user .
  # 或
  pipx install .
  ```

- 安装后命令名：`cuelint`。也可以 `python -m cuelint`。
- 最低磁盘空间 20MB，最低内存 128MB；不要求 GPU、网络、数据库。
- 支持平台：macOS 13+、Ubuntu 22.04+、Windows 10 22H2+。路径使用 `pathlib`，不写死分隔符。

## 2. 目录与技术栈

```
cuelint/
  pyproject.toml           构建配置，console_scripts 暴露 cuelint
  src/cuelint/
    __init__.py            __version__ = "0.1.0"
    __main__.py            python -m cuelint 入口
    cli.py                 argparse 命令、参数、退出码、文本/JSON 输出
    model.py               Cue、Document、Issue、Fix、Report 数据类
    parser.py              SRT/WebVTT 解析和序列化
    profiles.py            内置 profile、校验、宽度/CPS 计算
    config.py              TOML 读取、未知键拒绝、CLI 覆盖
    rules.py               规则定义与检查
    layout.py              断行、拆段、时间分配
    fixer.py               修复流水线、幂等、原子写
    report.py              HTML 报告
    terminal.py            颜色、文本表格、控制字符清理
  tests/                   pytest，全部离线
    fixtures/              小样本字幕
  examples/                演示用真实内容样本
  docs/                    规格、设计、外部依据、偏离、功能、开发
  README.md README_EN.md
  LICENSE CHANGELOG.md .gitignore .env.example
```

本地开发端口：无。没有 HTTP 服务。

## 3. 配置

### 3.1 环境变量

只读取以下三个变量，其他 `CUELINT_` 变量忽略。环境变量值非法时拒绝启动，退出码 2。

| 变量 | 默认 | 必填 | 取值 | 非法时 |
|---|---|---|---|---|
| `CUELINT_COLOR` | `auto` | 否 | `auto` / `always` / `never` | 打印 `错误：CUELINT_COLOR 只能是 auto、always 或 never。`，退出 2 |
| `CUELINT_NOW` | 空 | 否 | 带时区的 ISO 8601，例如 `2026-10-29T12:00:00Z` 或 `2026-10-29T20:00:00+08:00` | 打印 `错误：CUELINT_NOW 不是合法的 ISO 8601 时间。`，退出 2 |
| `CUELINT_MAX_FILE_BYTES` | `20971520` | 否 | 1024–104857600 的整数 | 打印 `错误：CUELINT_MAX_FILE_BYTES 必须是 1024 到 104857600 之间的整数。`，退出 2 |

- `CUELINT_COLOR=auto` 时，仅当标准输出是终端且 `TERM` 不为 `dumb` 时使用 ANSI 颜色。
- `CUELINT_NOW` 只影响报告里的生成时间和 JSON 的 `generatedAt`；不改变任何计算。测试和截图用它固定输出。解析时接受带 `Z` 或 `±HH:MM` 的 ISO 8601，必须包含时区；转换成 UTC 后精确到秒，舍去微秒。无时区、只有日期、非法月份日期都退出 2。
- 没有密钥、令牌、Cookie。任何日志都不打印字幕全文；文本输出只打印前 80 个显示列的摘录。

### 3.2 配置文件

- 路径由 `--config PATH` 指定；不自动搜索 `cuelint.toml`，避免在不同目录得到不同结果。
- 文件必须是 UTF-8 TOML，最大 64KB。只接受 `[profile]` 表，键如下；所有键可选。未知表、未知键、类型错误、越界、文件不存在、文件不可读、超过 64KB 都退出 2，`code` 为 `config_invalid`，并指出路径、键名和允许范围。
- 优先级：内置 profile < 配置文件 < 命令行参数。

```toml
[profile]
max_line_width = 36
max_lines = 2
max_cps = 9.0
min_duration_ms = 1000
max_duration_ms = 8000
min_gap_ms = 80
```

| 键 | 类型 | 范围 | 默认（`cjk` profile） |
|---|---|---|---|
| `max_line_width` | 整数 | 10–100 | 36 |
| `max_lines` | 整数 | 1–4 | 2 |
| `max_cps` | 浮点数 | 1.0–30.0 | 9.0 |
| `min_duration_ms` | 整数 | 200–10000 | 1000 |
| `max_duration_ms` | 整数 | 1000–60000，且大于 `min_duration_ms` | 8000 |
| `min_gap_ms` | 整数 | 0–1000，且小于 `min_duration_ms` | 80 |

### 3.3 命令行覆盖

`check` 和 `fix` 支持 `--max-line-width`、`--max-lines`、`--max-cps`、`--min-duration-ms`、`--max-duration-ms`、`--min-gap-ms`。同名参数同时出现在命令行和配置文件时，命令行生效；值按 3.2 的范围校验。

## 4. 数据模型

### 4.1 Document

| 字段 | 类型 | 取值 / 默认 | 说明 |
|---|---|---|---|
| `format` | 枚举 | `"srt"` / `"vtt"` | 由文件内容判断，不看扩展名 |
| `cues` | `Cue[]` | 至少 1 条 | 按解析顺序；修复后按 `start_ms` 升序 |
| `header_lines` | `string[]` | VTT 为 `WEBVTT` 后的头部行；SRT 为 `[]` | 输出时原样保留，单行最长 200 字符 |
| `source_path` | `string` | 绝对路径 | 只用于报表和错误信息 |
| `encoding` | 字符串 | `"utf-8"` / `"utf-8-sig"` | UTF-8 BOM 记为 `utf-8-sig` |

### 4.2 Cue

| 字段 | 类型 | 取值 / 默认 | 说明 |
|---|---|---|---|
| `index` | 整数 | 1 起 | 原始序号；修复后重新编号 |
| `identifier` | 字符串或 null | 默认 null | 仅 VTT：时间行前的一行文本，最长 100 字符 |
| `start_ms` | 整数 | 0–3599999999 | 毫秒 |
| `end_ms` | 整数 | 0–3599999999 | 毫秒；可以小于等于 `start_ms`，由规则报错 |
| `text` | 字符串 | 默认 `""` | 行间用 `\n`；保留标记 |
| `settings` | 字符串 | 默认 `""` | 时间行末尾的 VTT cue settings 或 SRT 坐标，原样保留 |
| `source_line` | 整数 | 1 起 | 时间行在输入文件中的行号 |

### 4.3 Issue

| 字段 | 类型 | 取值 / 默认 | 说明 |
|---|---|---|---|
| `rule` | 字符串 | 见第 6 节 | 规则编号 |
| `severity` | 枚举 | `"error"` / `"warning"` | |
| `cue_index` | 整数或 null | 默认 null | 原始 cue 序号；文件级问题为 null |
| `line` | 整数或 null | 默认 null | 来源行号 |
| `message` | 字符串 | 非空 | 中文，包含实际数值 |
| `fixable` | 布尔 | 默认 false | 修复流水线是否能处理 |
| `details` | 对象 | 默认 `{}` | 只放数值字段，键名见第 6 节 |

### 4.4 Fix

| 字段 | 类型 | 取值 | 说明 |
|---|---|---|---|
| `cue_index` | 整数 | 输入文件中的原始 cue 序号 | |
| `action` | 枚举 | `remove-empty` / `remove-duplicate` / `remove-control` / `trim-overlap` / `trim-gap` / `extend-duration` / `split-cue` / `rewrap` | |
| `before` | CueSnapshot | 修复前的快照 | 见 4.4.1 |
| `after` | CueSnapshot[] | 0–8 条；删除类为 `[]` | 修复后的快照 |
| `detail` | 字符串 | 非空中文 | 例如“拆成 2 段，间隔 80 ms” |

#### 4.4.1 CueSnapshot

| 字段 | 类型 | 说明 |
|---|---|---|
| `startMs` | 整数 | 毫秒 |
| `endMs` | 整数 | 毫秒 |
| `text` | 字符串 | 规范化后的文本，保留换行和标记 |

`Fix.before` 与 `Fix.after` 是报告预览的唯一数据来源。`Fix.cue_index` 始终是输入文件里的序号；`issues` 数组里的 `cue_index` 是输出文件里的最终序号；`initialIssues` 数组里的 `cue_index` 是输入文件里的序号。

### 4.5 FileResult

| 字段 | 类型 | 说明 |
|---|---|---|
| `input` | 字符串 | 绝对路径 |
| `output` | 字符串或 null | `check` 为 null |
| `format` | 枚举 | `srt` / `vtt` |
| `cues` | 整数 | 修复后的 cue 数 |
| `before` | Counts | `{error, warning, total}` |
| `after` | Counts | `{error, warning, total}` |
| `initialIssues` | Issue[] | 修复前检查到的全部问题；`check` 时与 `issues` 相同 |
| `issues` | Issue[] | 修复后的剩余问题；`check` 时等于 `initialIssues` |
| `fixes` | Fix[] | `fix` 时应用的修复；`check` 时为 `[]` |

### 4.6 Report（JSON）

顶层对象，字段固定：

```json
{
  "tool": "cuelint",
  "version": "0.1.0",
  "generatedAt": "2026-10-29T12:00:00Z",
  "profile": "cjk",
  "summary": {
    "files": 1,
    "before": {"error": 3, "warning": 2, "total": 5},
    "after": {"error": 0, "warning": 1, "total": 1},
    "fixes": 4,
    "remaining": 1
  },
  "files": [
    {
      "input": "/work/episode-07.srt",
      "output": "/work/episode-07.fixed.srt",
      "format": "srt",
      "cues": 42,
      "before": {"error": 3, "warning": 2, "total": 5},
      "after": {"error": 0, "warning": 1, "total": 1},
      "initialIssues": [],
      "issues": [],
      "fixes": []
    }
  ]
}
```

- 数组顺序等于命令行输入顺序。同一个输入文件在命令行出现两次（按 `resolve()` 后的路径判断）时，第二次视为重复参数，所有子命令都退出 2，`code` 为 `usage_error`。
- `generatedAt` 为 UTC ISO 8601，精确到秒，末尾 `Z`。设置了 `CUELINT_NOW` 时使用该值。
- 数字不补零，布尔是 JSON 布尔。

## 5. 命令行接口

### 5.1 通用

```
cuelint [--version] <command> [options] [INPUT...]
```

- 不带子命令、未知子命令、缺少必需参数：打印用法到标准错误，退出 2。
- `--version` 输出 `cuelint 0.1.0`，退出 0，不读任何文件。
- 所有子命令支持 `--format text|json`，默认 `text`。`--format json` 时标准输出只有一个 JSON 对象，标准错误为空（除非进程被信号杀死）。
- 所有路径参数可以是相对路径；内部转绝对路径，解析符号链接后判断冲突。
- 输入文件必须存在、是普通文件、可读；目录、设备、管道一律退出 2，`code` 为 `input_not_file`。
- 单文件字节数上限由 `CUELINT_MAX_FILE_BYTES` 决定，默认 20971520；超过时退出 2，`code` 为 `input_too_large`。解析后 cue 数上限固定为 10000，可见字符总数上限固定为 2000000；超过任一上限退出 2，`code` 为 `input_too_large`。
- 单行文本（时间行、文本行、头部行）超过 4000 个字符时退出 2，`code` 为 `parse_error`，并给出行号。
- 通配符由 shell 展开；CueLint 自己不展开 `*`。

### 5.2 `check`

```
cuelint check INPUT... [--profile NAME] [--config PATH] [--format text|json]
  [--report PATH] [--fail-on error|warning|never] [--max-line-width N] [--max-lines N]
  [--max-cps F] [--min-duration-ms N] [--max-duration-ms N] [--min-gap-ms N]
```

- 至少 1 个 `INPUT`。
- 不写字幕文件；给了 `--report` 时写一份 HTML 报告。报告是唯一会写的文件。
- 默认 `--fail-on error`：存在任意 `error` 时退出 1；只有 warning 时退出 0。
- `--fail-on warning`：存在任意 error 或 warning 时退出 1。
- `--fail-on never`：只要解析成功就退出 0。
- 解析或配置错误：退出 2，不写报告。报告路径的父目录必须已存在且是目录，否则退出 2，`code` 为 `output_unwritable`。

文本输出格式，每个文件一块：

```
episode-07.srt  srt  42 条字幕  profile=cjk
  错误 3  警告 2
  [错误] cps-too-high  #12  00:01:23,000  18.4 字/秒 > 9.0 字/秒
       客户原话摘录…
  警告 line-too-long  #15  00:01:40,500  “……” 第 1 行 44 列 > 36 列

合计：错误 3  警告 2
```

- 每条问题一行，`message` 后再打印一行缩进 6 个空格的字幕摘录，摘录去掉换行，最多 80 个显示列（按第 6 节的显示宽度计算，超出时截断并加 `…`）。
- 没有问题时打印 `未发现问题。`。
- 多个文件之间空一行。

JSON 输出：4.6 的对象，其中 `output` 全为 null，`fixes` 全为 `[]`，`before` 与 `after` 的计数相同，`initialIssues` 与 `issues` 是同一组问题的两份数组。

### 5.3 `fix`

```
cuelint fix INPUT... [--profile NAME] [--config PATH] [--out-dir DIR] [--suffix TEXT]
  [--report PATH] [--format text|json] [--force] [--fail-on error|warning|never]
  [--max-line-width N] [--max-lines N] [--max-cps F] [--min-duration-ms N]
  [--max-duration-ms N] [--min-gap-ms N]
```

- 至少 1 个 `INPUT`。
- 默认输出到每个输入文件所在目录：主文件名 + `.fixed` + 输出格式的扩展名（由内容判定，见 7.4）。例：`episode-07.srt` → `episode-07.fixed.srt`；内容是 SRT 的 `episode-07.vtt` → `episode-07.fixed.srt`；没有扩展名的 `episode-07` → `episode-07.fixed.srt`。
- `--suffix TEXT`：替换默认 `.fixed`；允许 1–20 个字符，不能含 `/`、`\`、NUL，不能以 `.` 开头。非法退出 2。
- `--out-dir DIR`：所有输出放此目录；目录不存在时创建，创建失败退出 2。只创建一层，不递归创建父目录。
- 输出文件已存在时默认退出 3，错误信息包含路径和 `--force` 提示。`--force` 时覆盖。
- 写任何文件前先对全部字幕输出路径做预检：存在且没有 `--force`、父目录不存在、父路径不是目录、无写权限，任一失败都退出 3 并且不写任何文件。报告路径按第 9 节的覆盖规则单独处理，不参与字幕输出的预检。预检顺序不影响结果；只要有一个字幕输出失败就零写入。
- 输出路径解析后与任一输入路径相同：退出 2，错误码 `output_collision`。
- 两个输入产生同一个输出路径：退出 2，错误码 `output_collision`，不写任何文件。
- 先解析并修复全部输入，全部成功后才写文件；任一文件解析失败则一个输出都不写、报告也不写。
- 原子写：同一目录写临时文件 `.cuelint-<pid>-<n>.tmp`，`os.replace` 到目标；失败清理临时文件。
- 报告在字幕文件全部写完后生成；报告写入失败时字幕文件保留，退出 3，`code` 为 `output_unwritable`。
- 报告覆盖规则：`--report` 指向已存在的文件时直接覆盖；使用同一目录的临时文件加 `os.replace`；不提供 `--force`。报告路径解析后与任一输入或输出相同则退出 2，`code` 为 `output_collision`。
- 退出码：修复后按 `--fail-on` 判断，规则同 5.2；全部修好且没有达到阈值的剩余问题为 0。
- 如果任一输出仍含 `invalid-duration`（`end_ms <= start_ms`），本次不写任何字幕文件，退出 1，`code` 为 `unfixable_timing`，错误信息列出文件和 cue 序号。报告也不写。
- 文本输出：

```
episode-07.srt  srt  42 条字幕  profile=cjk
  修复 4 处
  修复后：错误 0  警告 1
  输出：/work/episode-07.fixed.srt
  报告：/work/report.html

合计：修复 4 处  剩余错误 0  剩余警告 1
```

- JSON 输出：4.6 对象，含 `output` 和 `fixes`。

### 5.4 `profiles`

```
cuelint profiles [--format text|json]
```

- 文本：每个内置 profile 一行，字段用两个空格分隔：
  `cjk  行宽 36  行数 2  CPS 9.0  时长 1000–8000 ms  间隔 80 ms`。
- JSON：`{"profiles":[{"name":"cjk","maxLineWidth":36,"maxLines":2,"maxCps":9.0,"minDurationMs":1000,"maxDurationMs":8000,"minGapMs":80}]}`，按 `latin`、`cjk`、`presentation`、`strict` 固定顺序。
- 退出 0。

### 5.5 `rules`

```
cuelint rules [--format text|json]
```

- 文本：每个规则一行，格式 `rule-id  error|warning  可修复|条件可修复|需人工  一句话说明`。
- JSON：`{"rules":[{"id":"cps-too-high","severity":"error","fixability":"auto","description":"..."}]}`，按第 6 节顺序。
- 退出 0。

### 5.6 `explain`

```
cuelint explain RULE_ID
```

- 文本输出：规则编号、严重级别、`fixability`、判定条件、修复动作、失败时行为，各占一行；退出 0。
- `--format json` 输出：`{"id":"...","severity":"error","fixability":"auto","condition":"...","fix":"...","unfixable":"..."}`；退出 0。
- 未知规则：文本模式标准错误 `错误：未知规则 "xxx"。用 cuelint rules 查看全部规则。`；JSON 模式标准输出 `{"error":"未知规则 \"xxx\"。用 cuelint rules 查看全部规则。","code":"unknown_rule"}`；两种都退出 2。

### 5.7 错误输出

- 文本模式：一行到标准错误，以 `错误：` 开头；有文件时加 `文件：<路径>`，有行号时加 `行：<n>`。退出码见下表。
- JSON 模式：标准输出 `{"error":"<中文>","code":"<code>"}`，标准错误为空。错误与具体文件有关时，对象额外带 `"file"`（绝对路径）；有行号时不论文件数都额外带 `"line"`（整数）。字段名不是 `filePath` 或 `lineNumber`。
- 命令行解析本身失败（未知参数、缺参数、`--format` 的值不合法）时，始终把用法写到标准错误并退出 2，即使 argv 里出现 `--format json`；因为没有完成解析，不保证 JSON 输出。
- 不打印 Python traceback；`CUELINT_DEBUG=1` 也不打印（没有这个变量）。

| 退出码 | 含义 | code 示例 |
|---|---|---|
| 0 | 成功，或未达到 `--fail-on` 阈值 | |
| 1 | 达到 `--fail-on` 阈值，或 `fix` 仍有非法时长未写出 | `unfixable_timing` |
| 2 | 参数、配置、输入、解析错误 | `usage_error`、`config_invalid`、`input_not_found`、`input_not_file`、`input_too_large`、`encoding_unsupported`、`parse_error`、`output_collision`、`output_unwritable` |
| 3 | 输出写入失败或已存在 | `output_exists`、`output_unwritable` |
| 70 | 未预期内部错误 | `internal_error` |

## 6. 规则

规则按下列顺序检查和输出。同一 cue 可以有多个规则。严重级别不可由配置修改。

| # | 规则 | 级别 | 可修复 | 条件 | 修复动作 | 修不了时 |
|---|---|---|---|---|---|---|
| 1 | `empty-cue` | error | 是 | 去掉标记和首尾空白后，文本为空 | 删除该 cue | — |
| 2 | `duplicate-cue` | warning | 是 | 两条 cue 的 `start_ms`、`end_ms`、规范化文本完全相同 | 保留第一条，删除后面的 | — |
| 3 | `invalid-duration` | error | 否 | `end_ms <= start_ms` | 无 | 保留原样，报告为需人工；`fix` 整个批次不写输出 |
| 4 | `overlap` | error | 是 | 排序后，后一条 `start_ms` < 前一条 `end_ms` | 先尝试把前一条 `end_ms` 改为后一条 `start_ms - min_gap_ms`；改后必须满足 `end_ms - start_ms >= min_duration_ms`。不满足时尝试把后一条 `start_ms` 改为前一条 `end_ms + min_gap_ms`；改后必须满足 `end_ms > start_ms` 且不超过 `start_ms + max_duration_ms`。两次都不满足则放弃 | 保留原样 |
| 5 | `duration-too-short` | warning | 是 | `end_ms - start_ms < min_duration_ms` | 延长 `end_ms`，上限为 `next.start_ms - min_gap_ms`（没有下一条时用 `start_ms + max_duration_ms`）和 `start_ms + max_duration_ms` 的较小值；改后必须 `end_ms > start_ms` | 上限小于 `start_ms + min_duration_ms` 时保留原样 |
| 6 | `duration-too-long` | warning | 是 | `end_ms - start_ms > max_duration_ms` | 在合法断点拆成多段，段间留 `min_gap_ms`；最多 8 段 | 找不到断点、段数超过 8、或任一段时长 < `min_duration_ms` 时保留原样 |
| 7 | `gap-too-small` | warning | 是 | 排序后，`0 <= 后一条 start_ms - 前一条 end_ms < min_gap_ms` | 缩短前一条 `end_ms` 到后一条 `start_ms - min_gap_ms`；改后必须 `end_ms - start_ms >= min_duration_ms` | 不满足时保留原样 |
| 8 | `cps-too-high` | error | 是 | `visible_chars / (duration_ms/1000) > max_cps` | 先算 `needed_end = start_ms + ceil(visible_chars / max_cps * 1000)`；若 `needed_end <= min(下一条 start_ms - min_gap_ms, start_ms + max_duration_ms)`，把 `end_ms` 延长到 `needed_end`。否则按规则 6 同样的方式拆段 | 延长和拆段都不满足时保留原样 |
| 9 | `line-too-long` | warning | 是（`complex-markup` 为否） | 任一行的 `display_width > max_line_width` | 重新断行；必要时拆段 | 单个不可断 token 超宽、或命中 `complex-markup` 时保留 |
| 10 | `too-many-lines` | warning | 是（`complex-markup` 为否） | `text` 的行数 > `max_lines` | 重新断行；必要时拆段 | 命中 `complex-markup` 或断不开时保留 |
| 11 | `control-char` | error | 是 | 文本含 U+0000–U+0008、U+000B、U+000C、U+000E–U+001F、U+007F–U+009F | 替换为一个半角空格，再压缩连续空格 | — |
| 12 | `unbalanced-markup` | warning | 否 | `<i>`、`<b>`、`<u>` 开闭数量不配对，或嵌套顺序错误 | 无 | 保留原样 |
| 13 | `complex-markup` | warning | 否 | 含 `<i>/<b>/<u>` 之外的 `<...>` 或 `{\...}` 标记 | 不修改该 cue 的排版和拆段，只检查文本宽度 | 保留原样 |

补充定义：

- **规范化文本**：换行统一为 `\n`；每行去掉首尾空格和制表符；去掉零宽空格 U+200B；其余字符不动。
- **可见字符数**：去掉 `<...>`、`{\...}` 标记和所有 Unicode 空白后，Unicode 码点的数量。CJK 一个字算 1，拉丁一个字母算 1。
- **显示宽度**：去掉标记后逐码点计算；East Asian Width 为 `W` 或 `F` 的算 2 列；组合字符（Unicode 类别 `Mn`、`Me`）算 0 列；其他算 1 列。制表符算 1 列。
- **行数**：文本中 `\n` 的数量加 1；空文本为 0。
- **比较边界**：等于阈值不算违规。CPS 用未四舍五入的浮点数比较。
- **规则 8 的结束上限**：有下一条时是 `next.start_ms - min_gap_ms`，没有下一条时是 `start_ms + max_duration_ms`；两个上限取较小值，且不得小于 `start_ms + 1`。
- **规则 8 的前置条件**：`duration_ms <= 0` 或 `visible_chars == 0` 时不报 `cps-too-high`；这两种情况由规则 3 或规则 1 负责。
- **规则 4 的处理顺序**：按 `start_ms` 升序从前往后逐对处理。每对只尝试一次：先修剪前一条；修剪不满足时长条件时回滚，再尝试后移后一条；两次都不满足时保留原样，继续下一对。后移后一条造成的再下一条重叠，留到下一轮重算。每轮最多 3 轮。
- **规则 13 的优先级**：命中 `complex-markup` 的 cue 不做拆段、不做重新断行，避免破坏标记；仍然检查 `line-too-long`，但不自动修。
- **标记配对**：`<i>`、`<b>`、`<u>` 按不区分大小写识别，允许带属性（属性原样保留）；用栈检查嵌套。出现 `</i>` 时栈顶必须是 `i`，否则 `unbalanced-markup`。自闭合的 `<br>`、`<br/>` 视为 complex-markup。`<i/>` 不是合法形式，按 unbalanced 处理。
- **空文本判定**：先去掉 `<i>`、`<b>`、`<u>` 标记和 `{\...}` 标记，再去掉所有 Unicode 空白；结果为空即 `empty-cue`。

### 6.1 Issue.details 键名

| 规则 | `details` 键 | 类型 |
|---|---|---|
| `empty-cue` | 无 | |
| `duplicate-cue` | `keptCue` | 整数 |
| `invalid-duration` | `startMs`、`endMs` | 整数 |
| `overlap` | `overlapMs` | 整数 |
| `duration-too-short` | `actualMs`、`minMs` | 整数 |
| `duration-too-long` | `actualMs`、`maxMs` | 整数 |
| `gap-too-small` | `actualMs`、`minMs` | 整数 |
| `cps-too-high` | `cps`、`limit`、`chars` | 浮点、浮点、整数 |
| `line-too-long` | `line`、`width`、`limit` | 整数 |
| `too-many-lines` | `lines`、`limit` | 整数 |
| `control-char` | `count` | 整数 |
| `unbalanced-markup` | `tags` | 字符串数组 |
| `complex-markup` | `tags` | 字符串数组 |

`Issue.fixable` 是该条问题在当前 cue 上“这次能不能自动修”的布尔值：规则 6、9、10 找不到合法断点或超过 8 段时为 `false`；规则 13 自身为 `false`；其余按规则表。`cuelint rules` 里的 `fixability` 是规则级三态：`auto`（总能修）、`conditional`（看具体 cue）、`manual`（从不修）。

## 7. 修复流水线

按下列顺序执行，最多迭代 3 轮；一轮没有任何修复则停止。每轮结束重新计算全部规则。

1. **清理文本**：应用规则 11，去掉每行首尾空白和零宽空格。
2. **删除空 cue**（规则 1）。
3. **删除重复 cue**（规则 2）：保留原始顺序中第一条。
4. **修正时间**（规则 3、4、7）：先按 `start_ms` 稳定排序；`invalid-duration` 不动；重叠和间隔按规则 4、7 的优先级处理。处理后的 cue 仍保持排序。
5. **补最小时长**（规则 5）：从后往前处理，避免延长后压到下一条。
6. **拆长段和超速段**（规则 6、8）：按 7.1 的合法断点拆；拆出的段按显示宽度比例分配可用时长，段间留 `min_gap_ms`；每段必须 ≥ `min_duration_ms`，否则放弃本次拆分并保留原样。
7. **重新断行**（规则 9、10）：按 7.2 的分行算法；必要时把一段拆成两段，再回到第 6 步的分配逻辑。
8. **重新编号**：按 `start_ms` 升序，`index` 从 1 开始；VTT 保留原 `identifier`，SRT 丢弃原编号。

数字约束：

- 单条 cue 最多拆成 **8** 段；超过则本次拆分放弃，保留原样并报告剩余问题。
- 拆段时每段至少 **1** 个可见字符；空段不产生。
- 每次运行对同一个输入最多做 **3** 轮修复。
- 修复不改变 cue 的总时间范围之外的时间：所有新时间必须落在 `[原 start_ms, 原 end_ms]` 内；补最小时长可以延长 `end_ms`，但不超过下一条 `start_ms - min_gap_ms` 或 `start_ms + max_duration_ms`。

### 7.1 合法断点

拆段和分行只在以下位置断开，优先级从高到低：

1. 句末标点之后：`。`、`！`、`？`、`.`、`!`、`?`，且后面不是数字小数点。
2. 逗号、分号、冒号之后：`，`、`、`、`；`、`：`、`,`、`;`、`:`。
3. 空白处：一个或多个空格/制表符之后。
4. CJK 字符之间：两个字符都不是禁止行首/行尾字符。
5. 拉丁单词之间。

禁止出现在行首的字符：`，。！？、；：,.!?;:)]}」』】》〉”’…`。
禁止出现在行尾的字符：`([{「『【《〈“‘`。

找不到合法断点，且单行宽度超限，或拆段后不满足时长约束：本次不拆，保留原样。

### 7.2 分行算法

- 目标：行数 ≤ `max_lines`，每行 `display_width ≤ max_line_width`，在满足前两条的方案里最小化各行剩余宽度的平方和。
- 用动态规划在合法断点上分行；代价为每行剩余宽度的平方和，加以下惩罚：行尾是禁止行尾字符罚 1000，行首是禁止行首字符罚 1000。
- 如果一行能放下，输出一行。
- 如果动态规划找不到满足宽度和行数的方案，尝试拆成两段 cue 后分别分行；仍失败则保留原样。
- 原有换行只作为候选断点，不强制保留；`complex-markup` 的 cue 原样保留换行。

### 7.3 幂等

对一份已经通过 `fix` 输出、且没有剩余 `error` 的文件再次运行 `fix`，必须不产生任何 `Fix`，输出字幕逐字节相同（报告时间除外）。

### 7.4 输出格式

- SRT：每条 cue 依次写序号（从 1 开始）、换行、`HH:MM:SS,mmm --> HH:MM:SS,mmm`、`settings` 原样（前面加一个空格，若原来有）、换行、文本、空行。文件以 UTF-8 无 BOM 写入，换行固定为 `\n`，最后一条 cue 后保留一个空行。
- VTT：先写 `WEBVTT`，再逐行写 `header_lines`，空行，然后每条 cue 写 `identifier`（若有，单独一行）、`HH:MM:SS.mmm --> HH:MM:SS.mmm`、`settings`（前面加一个空格，若原来有）、换行、文本、空行。最后保留一个空行。
- 输出扩展名由解析出的 `format` 决定：`srt` 写 `.srt`，`vtt` 写 `.vtt`，与输入扩展名无关。
- `fix` 的输出文件权限使用 `0o644`（受 umask 影响），不保留输入文件的权限位。
- 拆段时：第一段保留原 `identifier` 和 `settings`；第 n 段（n≥2）的 `identifier` 为原 identifier 加 `-n`（原 identifier 为 null 时保持 null），`settings` 置空，避免 `line`/`position` 冲突。SRT 的坐标尾缀按 `settings` 处理，拆段后只保留在第一段。

## 8. 内置 profile

| 名称 | `max_line_width` | `max_lines` | `max_cps` | `min_duration_ms` | `max_duration_ms` | `min_gap_ms` |
|---|---:|---:|---:|---:|---:|---:|
| `latin` | 42 | 2 | 17.0 | 1000 | 7000 | 80 |
| `cjk` | 36 | 2 | 9.0 | 1000 | 8000 | 80 |
| `presentation` | 32 | 2 | 15.0 | 1500 | 6000 | 120 |
| `strict` | 37 | 2 | 15.0 | 1200 | 6000 | 120 |

- 默认 profile：`cjk`。
- 这些数字是 CueLint 的默认值，不是任何平台的认证阈值。README 必须写清这一点。
- `--profile` 只接受上表四个名字，大小写敏感。未知值退出 2，错误信息列出四个名字。

## 9. HTML 报告

`--report PATH` 生成一个自包含 HTML 文件：

- UTF-8，单文件，不引用外部 CSS、JavaScript、字体、图片；不发起网络请求。
- `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">`。
- 所有来自字幕的文本必须 HTML 转义（`& < > " '`）。报告里不执行任何字幕内容。
- 内容顺序：
  1. 页头：`CueLint`、`N 个文件`、profile 名、`v0.1.0`、生成时间（UTC）。
  2. 全局摘要：所有文件的修复前错误/警告、修复数、修复后错误/警告、需人工数之和。数字用等宽数字。
  3. 每个文件一节，按命令行顺序：文件名（绝对路径的 basename）、该文件的修复前后计数、问题表、变更预览。文件之间用 2px 分隔线。
  4. 问题表：级别（圆点 + 文字）、规则、cue 序号、时间码、说明、状态。状态按 `initialIssues` 逐条判断：该问题仍出现在 `issues` 中且 `fixable=false` 时为 `需人工`；仍在 `issues` 中且 `fixable=true` 时为 `未处理`；不在 `issues` 中时为 `已修复`。同一 `(rule, cue_index, line, message)` 视为同一条问题。问题超过 20 条时，前 20 条直接显示，其余放进该文件节里的 `<details>`；折叠区不设条数上限。
  5. 变更预览：每个文件最多 50 条有修复的 cue；每条显示修复前时间/文本、修复后时间/文本；超过 50 条时在该文件节末尾显示“本文件还有 N 条变更未在预览中，完整问题见上方表格。”
  6. 页脚：`本报告由 CueLint v0.1.0 在本地生成；没有上传字幕或统计数据。`
- 修复前的问题从 `FileResult.initialIssues` 取，修复后的剩余问题从 `FileResult.issues` 取；报告只展示，不重新计算。
- 报告文件超过 5MB 时仍然写，但终端提示 `报告较大：<字节数> 字节`。
- 报告路径的父目录必须已存在且是目录，否则退出 2，`code` 为 `output_unwritable`。
- 报告路径与任一输入或输出相同：退出 2，`output_collision`。

## 10. 风险与防护

| 风险 | 防护 | 对应测试 |
|---|---|---|
| 覆盖用户原字幕 | 永不原地写；默认 `.fixed` 后缀；目标存在时拒绝，除非 `--force`；先写临时文件再 `os.replace` | `test_fix_never_overwrites_input`、`test_fix_refuses_existing_output`、`test_fix_atomic_on_parse_error` |
| 批量处理一半失败，留下半套输出 | 全部解析、修复成功后才写；任一失败零输出 | `test_fix_batch_all_or_nothing` |
| 字幕里的 HTML/脚本进入报告 | 报告对全部动态文本 HTML 转义；CSP 禁止脚本 | `test_report_escapes_html`、`test_report_has_csp` |
| 字幕里的 ANSI 控制字符污染终端 | 终端输出前替换 C0/C1 控制字符；报告同样转义 | `test_terminal_strips_control_chars` |
| 超大文件/超多 cue 拖垮内存 | 单文件默认 20MiB（可由 `CUELINT_MAX_FILE_BYTES` 调整到 100MiB）、10000 cue、200 万可见字符上限；超限退出 2 | `test_input_too_large`、`test_too_many_cues` |
| 正则灾难性回溯 | 不使用嵌套量词正则；标记解析用线性扫描；有 10000 cue 性能测试 | `test_large_file_performance` |
| 路径冲突或覆盖别的文件 | 所有路径 `resolve()` 后比较；输入/输出/报告相同即拒绝 | `test_output_collision` |
| 时间计算误伤内容 | 修复只动时间、断行、空/重复/控制字符；每次修复记录在 `fixes`；原文件保留 | `test_each_fix_is_reported`、`test_fix_idempotent` |
| 错误断句改变语义 | 只在合法断点断；不删字、不换词、不翻译；拆不了就保留并报告 | `test_no_character_loss`、`test_unbreakable_token_kept` |
| 报告时间不可复现 | 支持 `CUELINT_NOW`；测试固定时间 | `test_generated_at_from_env` |
| 依赖本机时区 | 所有时间计算用毫秒整数；报告时间用 UTC | `test_report_utc` |

## 11. 外部服务与 mock

第一版不调用任何外部服务：没有 HTTP 客户端、没有 DNS、没有模型、没有遥测。因此没有外部服务 mock 开关。

测试和演示的确定性由以下方式保证：

- 所有样本字幕在 `tests/fixtures/`，不联网生成。
- 报告时间通过 `CUELINT_NOW` 固定。
- 测试用 `tmp_path`，每个用例独立目录。
- 有一个测试在进程内把 `socket.socket` 替换成抛异常，运行完整 `fix`，证明没有网络调用。

## 12. 测试要求

全部用 pytest，在临时目录和固定样本上运行，不联网。SPEC 的每条都要有对应用例。

### 12.0 解析的接受与拒绝清单

接受：

- SRT 序号行可选；序号必须是十进制整数，允许前后空格。
- SRT 时间 `H:MM:SS,mmm`、`HH:MM:SS,mmm`、`HHH:MM:SS,mmm`，毫秒分隔符可以是 `,` 或 `.`。
- SRT 时间行末尾的坐标（如 `X1:10 X2:20 Y1:30 Y2:40`）原样放进 `settings`。
- VTT 第一行必须是 `WEBVTT`（允许 BOM）；`WEBVTT` 后同一行的文本作为 header。
- VTT 时间 `MM:SS.mmm` 或 `HH:MM:SS.mmm`，毫秒分隔符可以是 `.` 或 `,`。
- VTT `NOTE`、`STYLE`、`REGION` 块整体跳过；块内不解析时间。
- 空行分隔 cue；行尾 `\r\n`、`\n`、`\r` 都接受。

拒绝（退出 2，`parse_error`）：

- 时间行没有 `-->`；时间戳字段不是 3 段或 4 段；分钟或秒 ≥ 60；毫秒 ≥ 1000；时间超过 3599999999 ms。
- SRT 序号行不是整数；VTT 在 `WEBVTT` 之前出现内容。
- 头部行超过 100 行、单行超过 200 字符；任意行超过 4000 字符。
- 文件为空，或解析后 0 条 cue。
- UTF-16 BOM，或不是合法 UTF-8。

### 12.1 解析

- SRT：标准格式；无序号；多余空行；CRLF；UTF-8 BOM；时间用 `.`；小时 1 位；文本多行；文本含 `<i>`；时间行带坐标。
- VTT：`WEBVTT` 头；头部注释；NOTE/STYLE/REGION 块；cue identifier；cue settings（`align:start position:10%`）；`MM:SS.mmm`；逗号毫秒。
- 失败：空文件；只有 `WEBVTT`；时间行缺 `-->`；时间格式错；分钟 60；毫秒 1000；序号不是整数；负数时间；超过 3599999999ms；UTF-16 BOM；非 UTF-8 字节；文件超过 20MiB；cue 超过 10000；可见字符超过 2000000；头部超过 100 行或单行超过 200 字符。
- 解析错误必须给出行号和 `parse_error`，退出 2，不写输出。

### 12.2 规则

每条规则至少一个命中、一个不命中、一个边界相等不命中。规则 4、5、6、7、8 还要一个“修不了”的用例。规则 11、12、13 要有标记嵌套和复杂标记样本。

### 12.3 修复

- 每条可修复规则都有对应的 `Fix.action`。
- 修复后，对所有没有 `complex-markup`、且修复时找到合法断点的 cue：无重叠；间隔 ≥ `min_gap_ms`；每行宽度 ≤ `max_line_width`；行数 ≤ `max_lines`；CPS ≤ `max_cps`；时长在范围内。无法满足的 cue 必须出现在 `issues` 里，不能静默留下。
- 拆段：2 段、8 段、需要 9 段时放弃；段间有间隔；总时长不越界。
- 分行：纯中文、纯英文、中英混排、CJK 标点、超宽不可断 token、`<i>` 跨行闭合重开。
- 不丢字符：修复前后去掉标记和空白后的可见字符序列必须相同（删除空/重复 cue 的用例除外）。
- 幂等：对输出再跑一次，`fixes` 为空，字幕字节相同。
- 原子性：输出目录不可写时不留下临时文件；第二个文件解析失败时第一个也不写。

### 12.4 CLI

- `--version`、`profiles`、`rules`、`explain` 正常和未知参数。
- `check` 退出码 0/1/2；`--fail-on warning` 和 `never`。
- `fix` 默认输出名、`--out-dir`、`--suffix`、`--force`、输出已存在、输出冲突。
- 多文件顺序、重复参数、空输入、通配符未被展开。
- `--format json` 的字段名、类型、顺序无关但内容完整；错误时是 `{error, code}`。
- 文本输出包含实际数值；无问题时打印“未发现问题。”。
- `CUELINT_COLOR` 三个值；非终端不输出 ANSI；`--format json` 不混入颜色。
- `CUELINT_NOW` 固定报告时间；非法时间退出 2。
- 配置文件：合法覆盖、CLI 覆盖配置、未知键、类型错误、越界、缺文件。
- 报告路径冲突、报告写入失败退出 3。

### 12.5 报告

- 包含输入名、profile、修复前后计数、剩余问题、修复数。
- HTML 转义 `<script>alert(1)</script>`、`&`、引号。
- 有 CSP；没有 `http://`、`https://`、`<script`。
- 375px 宽度下表格不横向溢出（检查 CSS 含 `@media (max-width: 639px)` 和堆叠规则）。
- 深色模式 CSS 变量存在。

### 12.6 安全与性能

- 文件大小上限、cue 数上限、可见字符上限。
- 控制字符、ANSI 转义、NUL 字节。
- 符号链接输入、输出与输入同一真实路径。
- 无网络：socket 被禁用时完整 `fix` 仍成功。
- 10000 条 cue、每条 40 个字符的性能测试：在开发机（Apple M 系列，Python 3.11）上单次 `check` 不超过 5 秒，内存不超过 512MB。只测耗时上限，不把耗时写进 README，除非发布前实测并注明条件。

### 12.7 连续运行

同一套测试连续运行 3 遍全部通过，不允许 skip/xfail。任意一次偶发失败必须找根因修复，不能加重试。

## 13. 发布与版本

- 版本号唯一来源：`src/cuelint/__init__.py` 的 `__version__` 和 `pyproject.toml` 的 `version`，两者必须相同。
- Git 标签 `v0.1.0` 指向本地提交，不推送。
- CI 在 push 和 pull request 时运行全部测试；推 `vX.Y.Z` 标签时先校验标签与两处版本号一致，再跑测试、构建 wheel、建 GitHub Release（只写配置，不执行发布）。
- CHANGELOG 记录 0.1.0 的功能和已知限制。
