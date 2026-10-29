from pathlib import Path

from cuelint.report import render_report
from cuelint.service import run, RunOptions
from cuelint.profiles import BUILTINS


def build_report(tmp_path, text, name="a.srt", mode="check"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    opts = RunOptions(mode=mode, profile=BUILTINS["cjk"], profile_name="cjk", max_bytes=20 * 1024 * 1024)
    bundle = run([str(p)], opts)
    return bundle.report


def test_report_csp_and_no_script(tmp_path):
    report = build_report(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n")
    html = render_report(report)
    assert 'Content-Security-Policy' in html
    assert "default-src 'none'" in html
    assert "<script" not in html
    assert "style-src 'unsafe-inline'" in html


def test_report_escapes_subtitle_html(tmp_path):
    text = "<script>alert(1)</script>\n"
    report = build_report(tmp_path, f"1\n00:00:02,000 --> 00:00:01,000\n{text}\n")
    html = render_report(report)
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_report_has_summary_and_file_section(tmp_path):
    report = build_report(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n")
    html = render_report(report)
    for label in ("修复前错误", "修复前警告", "修复处数", "修复后错误", "修复后警告", "需人工"):
        assert label in html
    assert "a.srt" in html
    assert "本报告由 CueLint" in html


def test_report_dark_light_and_mobile_css(tmp_path):
    report = build_report(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n")
    html = render_report(report)
    assert "prefers-color-scheme: dark" in html
    assert "@media (max-width: 639px)" in html
    assert "--bg: #ffffff" in html and "--bg: #0e0e10" in html


def test_report_folds_more_than_twenty_issues(tmp_path):
    blocks = []
    for i in range(30):
        blocks.append(f"{i+1}\n00:00:{i:02d},000 --> 00:00:{i:02d},500\nHello there")
    text = "\n\n".join(blocks) + "\n"
    report = build_report(tmp_path, text)
    html = render_report(report)
    assert "还有" in html and "展开查看" in html


def test_report_status_fixed(tmp_path):
    # fix mode: a 20-char cue at 1s is too fast and can be extended because the next cue leaves room.
    text = "1\n00:00:00,000 --> 00:00:01,000\n一二三四五六七八九十\n\n2\n00:00:05,000 --> 00:00:06,000\n好\n"
    report = build_report(tmp_path, text, mode="fix")
    html = render_report(report)
    assert "已修复" in html or "需人工" in html
