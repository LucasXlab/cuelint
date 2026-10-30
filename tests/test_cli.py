import json
from pathlib import Path

from cuelint.parser import parse_bytes

GOOD = "1\n00:00:01,000 --> 00:00:03,000\nHi\n"


def make(tmp_path, text=GOOD, name="a.srt"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_version_and_usage(run):
    code, out, err = run(["--version"])
    assert (code, out.strip(), err) == (0, "cuelint 0.1.0", "")
    code, out, err = run([])
    assert code == 2 and err


def test_profiles_text_and_json(run):
    code, out, _ = run(["profiles"])
    assert code == 0
    assert out.splitlines()[0].startswith("latin  行宽 42")
    assert "cjk  行宽 36  行数 2  CPS 9.0  时长 1000–8000 ms  间隔 80 ms" in out
    code, out, _ = run(["profiles", "--format", "json"])
    data = json.loads(out)
    assert [p["name"] for p in data["profiles"]] == ["latin", "cjk", "presentation", "strict"]


def test_rules_and_explain(run):
    code, out, _ = run(["rules"])
    assert code == 0 and "cps-too-high  error  条件可修复" in out
    code, out, _ = run(["rules", "--format", "json"])
    data = json.loads(out)
    assert data["rules"][0]["id"] == "empty-cue"
    assert data["rules"][0]["fixability"] == "auto"
    code, out, _ = run(["explain", "cps-too-high"])
    assert code == 0 and "延长结束时间" in out
    code, out, _ = run(["explain", "cps-too-high", "--format", "json"])
    assert json.loads(out)["severity"] == "error"
    code, out, err = run(["explain", "nope", "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "unknown_rule" and err == ""


def test_check_text_and_exit_codes(run, tmp_path):
    p = make(tmp_path)
    code, out, _ = run(["check", str(p)])
    assert code == 0
    assert "未发现问题。" in out and "合计：错误 0  警告 0" in out

    bad = make(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n", "bad.srt")
    code, out, _ = run(["check", str(bad)])
    assert code == 1
    assert "[错误] invalid-duration" in out
    code, _, _ = run(["check", str(bad), "--fail-on", "never"])
    assert code == 0


def test_check_json_contract(run, tmp_path):
    p = make(tmp_path)
    code, out, err = run(["check", str(p), "--format", "json"])
    assert code == 0 and err == ""
    data = json.loads(out)
    assert data["tool"] == "cuelint" and data["version"] == "0.1.0"
    assert data["summary"]["files"] == 1
    f = data["files"][0]
    assert f["output"] is None and f["fixes"] == []
    assert f["before"] == f["after"]
    assert f["initialIssues"] == f["issues"] == []


def test_fix_creates_output_and_json(run, tmp_path):
    p = make(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n")
    out_path = tmp_path / "a.fixed.srt"
    code, out, _ = run(["fix", str(p), "--format", "json"])
    assert code == 1
    data = json.loads(out)
    assert data["code"] == "unfixable_timing"
    assert "仍有非法时长" in data["error"]
    assert not out_path.exists()


def test_fix_writes_and_is_idempotent(run, tmp_path):
    p = make(tmp_path, "1\n00:00:00,000 --> 00:00:06,000\nThis is a very long line that should be wrapped because it is wider than forty two columns for sure.\n")
    code, out, _ = run(["fix", str(p), "--profile", "latin"])
    assert code == 0
    out_path = tmp_path / "a.fixed.srt"
    assert out_path.exists()
    assert "输出：" in out
    first = out_path.read_text()
    code, out, _ = run(["fix", str(out_path), "--force", "--profile", "latin"])
    assert code == 0
    assert out_path.read_text() == first


def test_fix_exists_force_and_out_dir(run, tmp_path):
    p = make(tmp_path)
    target = tmp_path / "a.fixed.srt"
    target.write_text("old")
    code, out, err = run(["fix", str(p)])
    assert code == 3 and "already" not in err and "--force" in err
    assert target.read_text() == "old"
    code, out, _ = run(["fix", str(p), "--force"])
    assert code == 0 and target.read_text().startswith("1\n")
    outdir = tmp_path / "out"
    code, _, _ = run(["fix", str(p), "--out-dir", str(outdir), "--force"])
    assert code == 0 and (outdir / "a.fixed.srt").exists()


def test_fix_custom_suffix_and_invalid(run, tmp_path):
    p = make(tmp_path)
    code, _, _ = run(["fix", str(p), "--suffix", "v2"])
    assert code == 0 and (tmp_path / "a.v2.srt").exists()
    for bad in ("", ".x", "a/b", "x" * 21):
        code, _, _ = run(["fix", str(p), "--suffix", bad])
        assert code == 2


def test_output_collision_and_duplicate_inputs(run, tmp_path):
    p = make(tmp_path)
    code, out, _ = run(["check", str(p), str(p), "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "usage_error"
    code, _, _ = run(["fix", str(p), "--out-dir", str(tmp_path), "--force"])
    assert code == 0


def test_report_written_and_json(run, tmp_path):
    p = make(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHello\n")
    report = tmp_path / "report.html"
    code, _, _ = run(["check", str(p), "--report", str(report), "--format", "json"])
    assert code == 1 and report.exists()
    html = report.read_text()
    assert "<!doctype html>" in html and "Content-Security-Policy" in html
    assert "invalid-duration" in html


def test_report_parent_missing_aborts_fix(run, tmp_path):
    p = make(tmp_path)
    code, out, _ = run(["fix", str(p), "--report", str(tmp_path / "missing" / "r.html"), "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "output_unwritable"
    assert not (tmp_path / "a.fixed.srt").exists()


def test_missing_and_bad_file_errors(run, tmp_path):
    code, out, err = run(["check", str(tmp_path / "nope.srt"), "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "input_not_found" and err == ""
    code, out, err = run(["check", str(tmp_path / "nope.srt")])
    assert code == 2 and "文件不存在" in err
    bad = make(tmp_path, "not a subtitle\n")
    code, out, _ = run(["check", str(bad), "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "parse_error"


def test_color_modes(run, tmp_path):
    p = make(tmp_path, "1\n00:00:02,000 --> 00:00:01,000\nHi\n")
    code, out, _ = run(["check", str(p)], env={"CUELINT_COLOR": "always"})
    assert code == 1 and "\x1b[31m" in out
    code, out, _ = run(["check", str(p)], env={"CUELINT_COLOR": "never"})
    assert "[" not in out
    code, out, _ = run(["check", str(p), "--format", "json"], env={"CUELINT_COLOR": "always"})
    assert "\x1b[" not in out


def test_config_and_env(run, tmp_path):
    p = make(tmp_path)
    config = tmp_path / "c.toml"
    config.write_text("[profile]\nmax_line_width = 10\n")
    code, out, _ = run(["check", str(p), "--config", str(config), "--format", "json"])
    assert code == 0
    code, out, _ = run(["check", str(p), "--config", str(config), "--format", "json"], env={"CUELINT_NOW": "2026-01-02T03:04:05+08:00"})
    assert json.loads(out)["generatedAt"] == "2026-01-01T19:04:05Z"
    bad = tmp_path / "bad.toml"
    bad.write_text("[profile]\nmax_line_width = 5\n")
    code, out, _ = run(["check", str(p), "--config", str(bad), "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "config_invalid"
    code, out, _ = run(["check", str(p), "--format", "json"], env={"CUELINT_MAX_FILE_BYTES": "1"})
    assert code == 2 and json.loads(out)["code"] == "config_invalid"
    big = tmp_path / "big.srt"
    big.write_text("1\n00:00:01,000 --> 00:00:02,000\n" + "x" * 2048 + "\n")
    code, out, _ = run(["check", str(big), "--format", "json"], env={"CUELINT_MAX_FILE_BYTES": "1024"})
    assert code == 2 and json.loads(out)["code"] == "input_too_large"
    code, _, _ = run(["check", str(p)], env={"CUELINT_COLOR": "sometimes"})
    assert code == 2


def test_cli_overrides(run, tmp_path):
    p = make(tmp_path, "1\n00:00:01,000 --> 00:00:02,000\n" + "a" * 20 + "\n")
    code, out, _ = run(["check", str(p), "--max-line-width", "10", "--format", "json"])
    assert code == 1
    data = json.loads(out)
    assert any(i["rule"] == "line-too-long" for i in data["files"][0]["issues"])


def test_check_does_not_write_subtitles(run, tmp_path):
    p = make(tmp_path)
    before = p.read_text()
    run(["check", str(p), "--report", str(tmp_path / "r.html")])
    assert p.read_text() == before
    assert not (tmp_path / "a.fixed.srt").exists()


def test_batch_zero_output_on_parse_error(run, tmp_path):
    good = make(tmp_path)
    bad = make(tmp_path, "not a subtitle\n", "bad.srt")
    code, out, _ = run(["fix", str(good), str(bad), "--format", "json"])
    assert code == 2
    assert not (tmp_path / "a.fixed.srt").exists()


def test_warning_only_default_zero_and_warning_mode(run, tmp_path):
    p = make(tmp_path, "1\n00:00:01,000 --> 00:00:05,000\n" + "中" * 20 + "\n")
    code, _, _ = run(["check", str(p)])
    assert code == 0
    code, _, _ = run(["check", str(p), "--fail-on", "warning"])
    assert code == 1


def test_report_overwrites_existing(run, tmp_path):
    p = make(tmp_path)
    report = tmp_path / "r.html"
    report.write_text("old")
    code, _, _ = run(["check", str(p), "--report", str(report)])
    assert code == 0
    assert report.read_text().startswith("<!doctype html>")


def test_vtt_comma_and_srt_dot(run, tmp_path):
    vtt = make(tmp_path, "WEBVTT\n\n00:00:01,000 --> 00:00:02,000\nHi\n", "a.vtt")
    srt = make(tmp_path, "1\n00:00:01.000 --> 00:00:02.000\nHi\n", "b.srt")
    code, out, _ = run(["check", str(vtt), str(srt)])
    assert code == 0 and "未发现问题。" in out


def test_json_usage_error_is_text(run):
    code, out, err = run(["check", "--format", "json"])
    assert code == 2 and out == "" and err


def test_suffix_dot_rejected(run, tmp_path):
    p = make(tmp_path)
    code, out, _ = run(["fix", str(p), "--suffix", ".x", "--format", "json"])
    assert code == 2 and json.loads(out)["code"] == "usage_error"


def test_all_empty_cues_abort_without_output(run, tmp_path):
    p = make(tmp_path, "1\n00:00:01,000 --> 00:00:02,000\n<i></i>\n\n2\n00:00:03,000 --> 00:00:04,000\n   \n")
    code, out, _ = run(["fix", str(p), "--format", "json"])
    assert code == 1
    data = json.loads(out)
    assert data["code"] == "all_cues_removed"
    assert not (tmp_path / "a.fixed.srt").exists()



def test_config_huge_integer_is_config_invalid(run, tmp_path):
    p = make(tmp_path)
    cfg = tmp_path / "c.toml"
    cfg.write_text("[profile]\nmax_lines = 1" + "0" * 400 + "\n")
    code, out, _ = run(["check", str(p), "--config", str(cfg), "--format", "json"])
    assert code == 2
    assert json.loads(out)["code"] == "config_invalid"
