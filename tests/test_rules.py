from cuelint.model import Cue, Document
from cuelint.parser import parse_bytes
from cuelint.profiles import BUILTINS
from cuelint.rules import check_document


def doc(*items):
    cues = [Cue(index=i, start_ms=s, end_ms=e, text=t, source_line=i, origin_index=i) for i, (s, e, t) in enumerate(items, 1)]
    return Document(format="srt", cues=cues)


def by_rule(d, profile="cjk"):
    return [i for i in check_document(d, BUILTINS[profile])]


def test_empty_duplicate_and_control():
    d = doc((0, 1000, "<i>  </i>"), (1000, 2000, "x\x07y"), (3000, 4000, "same"), (3000, 4000, "same"))
    rules = [i.rule for i in by_rule(d, "latin")]
    assert "empty-cue" in rules
    assert "control-char" in rules
    assert rules.count("duplicate-cue") == 1


def test_invalid_duration_skips_cps_and_duration():
    d = doc((1000, 1000, "hello"))
    rules = [i.rule for i in by_rule(d)]
    assert "invalid-duration" in rules
    assert "cps-too-high" not in rules
    assert "duration-too-short" not in rules


def test_overlap_and_gap_zero_are_separate():
    d = doc((0, 1000, "a"), (950, 2000, "b"), (2050, 3000, "c"))
    issues = by_rule(d)
    overlaps = [i for i in issues if i.rule == "overlap"]
    gaps = [i for i in issues if i.rule == "gap-too-small"]
    assert len(overlaps) == 1
    assert gaps and gaps[0].details["actualMs"] == 50


def test_gap_exactly_zero_is_gap_too_small():
    d = doc((0, 1000, "a"), (1000, 2000, "b"))
    assert [i.rule for i in by_rule(d)].count("gap-too-small") == 1


def test_duration_and_cps_limits():
    d = doc((0, 500, "short"), (1000, 10001, "a" * 20))
    issues = by_rule(d, "cjk")
    rules = [i.rule for i in issues]
    assert "duration-too-short" in rules
    assert "duration-too-long" in rules
    assert "cps-too-high" in rules


def test_line_width_and_lines_cjk_width():
    d = doc((0, 5000, "中" * 19 + "\n" + "中" * 19))
    rules = [i.rule for i in by_rule(d, "cjk")]
    assert "line-too-long" in rules
    assert "too-many-lines" not in rules
    d2 = doc((0, 5000, "a\nb\nc"))
    assert "too-many-lines" in [i.rule for i in by_rule(d2, "cjk")]


def test_markup_balanced_complex_unbalanced():
    assert [i.rule for i in by_rule(doc((0, 2000, "<i>hi</i>")), "latin")] == []
    assert "unbalanced-markup" in [i.rule for i in by_rule(doc((0, 2000, "<i>hi")), "latin")]
    assert "complex-markup" in [i.rule for i in by_rule(doc((0, 2000, "<font color=red>hi</font>")), "latin")]


def test_control_c1_and_tab_are_handled():
    assert "control-char" in [i.rule for i in by_rule(doc((0, 2000, "a\x9bb")), "latin")]
    assert "control-char" not in [i.rule for i in by_rule(doc((0, 2000, "a\tb")), "latin")]


def test_order_is_rule_then_cue():
    d = doc((0, 500, "a"), (450, 2000, "b"))
    rules = [i.rule for i in by_rule(d)]
    assert rules.index("overlap") < rules.index("duration-too-short")


def test_parser_rule_integration_vtt():
    d = parse_bytes(b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n" + "中".encode() * 20 + b"\n")
    assert "line-too-long" in [i.rule for i in check_document(d, BUILTINS["cjk"])]


def test_self_closing_markup_is_manual():
    assert "complex-markup" in [i.rule for i in by_rule(doc((0, 2000, "<br/>hi")), "latin")]
    assert "unbalanced-markup" in [i.rule for i in by_rule(doc((0, 2000, "<i/>hi")), "latin")]


def test_layout_fixability_reflects_whether_a_fix_exists():
    long_token = doc((0, 20000, "x" * 100))
    issues = {i.rule: i for i in by_rule(long_token, "latin")}
    assert issues["duration-too-long"].fixable is False
    assert issues["line-too-long"].fixable is False
    splittable = doc((0, 20000, "一" * 40))
    issues = {i.rule: i for i in by_rule(splittable, "cjk")}
    assert issues["duration-too-long"].fixable is True


def test_cjk_corner_brackets_are_cjk_tokens():
    from cuelint.layout import tokenize

    assert [t.kind for t in tokenize("「a」")] == ["cjk", "word", "cjk"]
