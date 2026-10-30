"""Self-contained HTML report. No scripts, no external assets."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .model import FileResult, Issue, Report

CSS = r"""
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --bg-subtle: #fafafa;
  --bg-muted: #f4f4f5;
  --border: #e4e4e7;
  --border-strong: #d4d4d8;
  --text: #18181b;
  --text-muted: #5f5f68;
  --text-faint: #71717a;
  --primary: #0f766e;
  --primary-soft: #ecfdf5;
  --error: #b91c1c;
  --error-soft: #fef2f2;
  --warning: #a16207;
  --warning-soft: #fffbeb;
  --focus: #0f766e;
  --font-body-size: 14px;
  --font-body-line: 22px;
  --font-h1-size: 20px;
  --font-h1-line: 28px;
  --font-h2-size: 15px;
  --font-h2-line: 22px;
  --font-h3-size: 13px;
  --font-h3-line: 20px;
  --font-ui-size: 13px;
  --font-ui-line: 20px;
  --font-caption-size: 12px;
  --font-caption-line: 16px;
  --font-metric-size: 24px;
  --font-metric-line: 32px;
  --radius: 8px;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e0e10;
    --bg-subtle: #161618;
    --bg-muted: #1c1c1f;
    --border: #2a2a2e;
    --border-strong: #3f3f46;
    --text: #f4f4f5;
    --text-muted: #a1a1aa;
    --text-faint: #8b8b94;
    --primary: #5eead4;
    --primary-soft: #12312d;
    --error: #fca5a5;
    --error-soft: #2a1518;
    --warning: #fcd34d;
    --warning-soft: #2a2110;
    --focus: #5eead4;
  }
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  color: var(--text);
  background: var(--bg);
  font-family: var(--sans);
  font-size: var(--font-body-size);
  line-height: var(--font-body-line);
  -webkit-font-smoothing: antialiased;
}
main { max-width: 1100px; margin: 0 auto; padding: 32px 24px 48px; }
.page-head { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--border-strong); }
.brand { font-size: var(--font-h1-size); line-height: var(--font-h1-line); font-weight: 600; letter-spacing: -0.01em; }
.meta { color: var(--text-muted); font-size: var(--font-caption-size); line-height: var(--font-caption-line); text-align: right; }
.summary { display: grid; grid-template-columns: repeat(6, 1fr); margin: 20px 0 28px; background: var(--bg-subtle); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.metric { padding: 10px 12px; border-left: 1px solid var(--border); }
.metric:first-child { border-left: 0; }
.metric .num { font-size: var(--font-metric-size); line-height: var(--font-metric-line); font-weight: 600; font-variant-numeric: tabular-nums; }
.metric .label { color: var(--text-muted); font-size: var(--font-caption-size); line-height: var(--font-caption-line); }
.summary-note { color: var(--text-muted); font-size: var(--font-caption-size); margin: 0 0 var(--space-4); }
.file { padding-top: 24px; }
.file + .file { margin-top: 28px; border-top: 2px solid var(--border-strong); }
.file-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px 16px; }
.file-name { font-size: var(--font-h2-size); line-height: var(--font-h2-line); font-weight: 600; word-break: break-all; }
.file-counts { color: var(--text-muted); font-size: var(--font-ui-size); line-height: var(--font-ui-line); font-variant-numeric: tabular-nums; }
h2 { font-size: var(--font-h3-size); line-height: var(--font-h3-line); font-weight: 600; margin: 20px 0 8px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th { text-align: left; color: var(--text-muted); font-size: var(--font-caption-size); line-height: var(--font-caption-line); font-weight: 500; padding: 6px 8px; border-bottom: 1px solid var(--border-strong); }
td { padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: var(--font-ui-size); line-height: var(--font-ui-line); }
th:first-child, td:first-child { padding-left: 0; }
th:last-child, td:last-child { padding-right: 0; }
.col-sev { width: 76px; }
.col-rule { width: 18%; }
.col-cue { width: 64px; }
.col-time { width: 104px; }
.col-status { width: 76px; }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.sev { white-space: nowrap; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
.dot.error { background: var(--error); }
.dot.warning { background: var(--warning); }
.status { white-space: nowrap; font-size: var(--font-caption-size); }
.status-fixed { color: var(--primary); }
.status-manual { color: var(--warning); }
.status-open { color: var(--text-muted); }
.empty { color: var(--text-muted); padding: 12px 0; }
.preview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.fix { border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 12px; background: var(--bg-subtle); }
.fix + .fix { margin-top: 10px; }
.fix-head { display: flex; justify-content: space-between; gap: 12px; color: var(--text-muted); font-size: var(--font-caption-size); line-height: var(--font-caption-line); margin-bottom: 6px; }
.subtitle { margin: 0; font-size: var(--font-ui-size); line-height: var(--font-ui-line); white-space: pre-wrap; word-break: break-word; }
.removed { color: var(--text-muted); font-style: normal; }
details { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px; }
summary { min-height: 40px; display: flex; align-items: center; cursor: pointer; color: var(--primary); font-size: var(--font-ui-size); }
summary:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid var(--border); color: var(--text-faint); font-size: var(--font-caption-size); line-height: var(--font-caption-line); }
@media (max-width: 1023px) {
  main { max-width: 880px; padding: 24px 24px 40px; }
  .metric .num { font-size: var(--font-h1-size); line-height: var(--font-h1-line); }
}
@media (max-width: 639px) {
  main { padding: 20px 16px 36px; }
  .page-head { display: block; }
  .meta { text-align: left; margin-top: 4px; }
  .summary { grid-template-columns: repeat(2, 1fr); }
  .metric { border-left: 0; border-top: 1px solid var(--border); }
  .metric:nth-child(2n) { border-left: 1px solid var(--border); }
  .metric:nth-child(-n+2) { border-top: 0; }
  .preview-grid { grid-template-columns: 1fr; }
  table, thead, tbody, th, td, tr { display: block; }
  thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  tr { padding: 8px 0; border-bottom: 1px solid var(--border); }
  td { border: 0; padding: 2px 0; }
  td::before { content: attr(data-label); display: inline-block; width: 68px; color: var(--text-muted); font-size: var(--font-caption-size); }
  .col-sev, .col-rule, .col-cue, .col-time, .col-status { width: auto; }
}
@media print {
  main { max-width: none; padding: 0; }
  details { display: block; }
}
"""


def _issue_status(initial: Issue, remaining: dict[tuple[str, int | None], Issue]) -> tuple[str, str]:
    key = (initial.rule, initial.origin_index)
    if key not in remaining:
        return "已修复", "status-fixed"
    return ("需人工", "status-manual") if not remaining[key].fixable else ("未处理", "status-open")


def _issue_rows(file: FileResult) -> list[str]:
    remaining: dict[tuple[str, int | None], Issue] = {}
    for issue in file.issues:
        remaining[(issue.rule, issue.origin_index)] = issue
    rows: list[str] = []
    seen: set[tuple[str, int | None]] = set()
    for issue in file.initial_issues:
        key = (issue.rule, issue.origin_index)
        seen.add(key)
        label, cls = _issue_status(issue, remaining)
        rows.append(_row(issue, label, cls))
    for issue in file.issues:
        key = (issue.rule, issue.origin_index)
        if key in seen:
            continue
        label = "需人工" if not issue.fixable else "未处理"
        rows.append(_row(issue, label, "status-manual" if not issue.fixable else "status-open"))
    return rows


def _table(rows: list[str]) -> str:
    return (
        '<table><thead><tr><th class="col-sev">级别</th><th class="col-rule">规则</th>'
        '<th class="col-cue">cue</th><th class="col-time">时间码</th><th>说明</th>'
        '<th class="col-status">状态</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _row(issue: Issue, status: str, cls: str) -> str:
    sev_text = "错误" if issue.severity == "error" else "警告"
    cue = "—" if issue.cue_index is None else f"#{issue.cue_index}"
    return (
        "<tr>"
        f'<td class="sev" data-label="级别"><span class="dot {escape(issue.severity)}"></span>{sev_text}</td>'
        f'<td class="mono" data-label="规则">{escape(issue.rule)}</td>'
        f'<td class="mono" data-label="cue">{escape(cue)}</td>'
        f'<td class="mono" data-label="时间码">{escape(issue.timecode)}</td>'
        f'<td data-label="说明">{escape(issue.message)}</td>'
        f'<td class="status {cls}" data-label="状态">{status}</td>'
        "</tr>"
    )


def _fix_preview(file: FileResult) -> str:
    if not file.fixes:
        return '<p class="empty">没有改动。</p>'
    blocks: list[str] = []
    for fix in file.fixes[:50]:
        before = fix.before
        after = fix.after
        if after:
            after_html = "<br>".join(
                f'<span class="mono">{escape(_time(s.end_ms))}</span> {escape(s.text)}' for s in after
            )
        else:
            after_html = '<span class="removed">删除该 cue</span>'
        blocks.append(
            '<div class="fix">'
            f'<div class="fix-head"><span class="mono">{escape(fix.action)}</span><span>#{fix.cue_index}</span></div>'
            '<div class="preview-grid">'
            f'<div><div class="fix-head"><span>修复前</span><span class="mono">{escape(_time(before.start_ms))}</span></div><p class="subtitle">{escape(before.text)}</p></div>'
            f'<div><div class="fix-head"><span>修复后</span></div><p class="subtitle">{after_html}</p></div>'
            "</div></div>"
        )
    more = len(file.fixes) - 50
    if more > 0:
        blocks.append(f'<p class="empty">本文件还有 {more} 条变更未在预览中，完整问题见上方表格。</p>')
    return "".join(blocks)


def _time(ms: int) -> str:
    hours, rem = divmod(max(0, ms), 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _manual_count(file: FileResult) -> int:
    return sum(1 for issue in file.issues if not issue.fixable)


def render_report(report: Report) -> str:
    before, after = report.before, report.after
    manual = sum(_manual_count(f) for f in report.files)
    summary = [
        (before.error, "修复前错误"),
        (before.warning, "修复前警告"),
        (report.fix_count, "修复处数"),
        (after.error, "修复后错误"),
        (after.warning, "修复后警告"),
        (manual, "需人工（不可修）"),
    ]
    metrics = "".join(
        f'<div class="metric"><div class="num">{value}</div><div class="label">{label}</div></div>'
        for value, label in summary
    )
    summary_note = (
        '<p class="summary-note">“需人工”只统计规则本身不能自动修的问题；'
        '可自动修但本次未处理的，见下表“未处理”和修复后错误/警告。</p>'
    )
    sections: list[str] = []
    for file in report.files:
        name = Path(file.input).name
        rows = _issue_rows(file)
        if rows:
            if len(rows) > 20:
                table = _table(rows[:20]) + (
                    "<details><summary>还有 %d 条问题，展开查看</summary>%s</details>"
                    % (len(rows) - 20, _table(rows[20:]))
                )
            else:
                table = _table(rows)
        else:
            table = '<p class="empty">未发现问题。</p>'
        sections.append(
            '<section class="file">'
            f'<div class="file-head"><div class="file-name">{escape(name)}</div>'
            f'<div class="file-counts">修复前 错误 {file.before.error} / 警告 {file.before.warning}　'
            f'修复后 错误 {file.after.error} / 警告 {file.after.warning}　{file.cues} 条字幕</div></div>'
            "<h2>问题</h2>"
            f"{table}"
            "<h2>变更预览</h2>"
            f"{_fix_preview(file)}"
            "</section>"
        )
    return (
        "<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:\">"
        f"<title>CueLint 报告</title><style>{CSS}</style></head><body><main>"
        '<header class="page-head"><div class="brand">CueLint</div>'
        f'<div class="meta">{len(report.files)} 个文件　profile={escape(report.profile)}　'
        f"v{escape(report.version)}　{escape(report.generated_at)}</div></header>"
        f'<section class="summary">{metrics}</section>'
        f'{summary_note}'
        + "".join(sections)
        + '<footer>本报告由 CueLint v'
        + escape(report.version)
        + " 在本地生成；没有上传字幕或统计数据。</footer></main></body></html>\n"
    )
