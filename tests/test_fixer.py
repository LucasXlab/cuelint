from cuelint.fixer import fix_document
from cuelint.parser import parse_bytes, serialize
from cuelint.profiles import BUILTINS
from cuelint.rules import check_document

CJK = BUILTINS["cjk"]


def fix(text, profile=CJK):
    doc = parse_bytes(text.encode())
    out, fixes = fix_document(doc, profile)
    return out, fixes


def test_remove_empty_duplicate_and_control():
    out, fixes = fix("1\n00:00:01,000 --> 00:00:02,000\n<i></i>\n\n2\n00:00:03,000 --> 00:00:04,000\nhi\x07\n\n3\n00:00:03,000 --> 00:00:04,000\nhi\x07\n")
    assert [c.text for c in out.cues] == ["hi"]
    actions = [f.action for f in fixes]
    assert "remove-empty" in actions
    assert "remove-duplicate" in actions
    assert "remove-control" in actions


def test_overlap_shift_and_extend():
    out, fixes = fix("1\n00:00:01,000 --> 00:00:02,000\nHello world\n\n2\n00:00:01,500 --> 00:00:03,000\nHello there\n")
    assert out.cues[1].start_ms >= out.cues[0].end_ms + 80
    assert "trim-overlap" in [f.action for f in fixes]


def test_gap_and_min_duration():
    out, fixes = fix("1\n00:00:01,000 --> 00:00:01,500\nHi\n\n2\n00:00:02,200 --> 00:00:03,000\nThere\n")
    assert out.cues[0].end_ms - out.cues[0].start_ms >= 1000
    assert out.cues[1].start_ms - out.cues[0].end_ms >= 80


def test_split_long_duration():
    text = "一" * 30
    out, fixes = fix(f"1\n00:00:00,000 --> 00:00:20,000\n{text}\n")
    assert len(out.cues) > 1
    assert sum(len(c.text) for c in out.cues) == 30
    assert "split-cue" in [f.action for f in fixes]


def test_rewrap_long_lines():
    text = "This is a long line that needs to be wrapped into two lines without losing any word at all."
    out, fixes = fix(f"1\n00:00:00,000 --> 00:00:08,000\n{text}\n", BUILTINS["latin"])
    assert "\n" in out.cues[0].text
    assert " ".join(" ".join(c.text.split()) for c in out.cues) == text


def test_idempotent_bytes():
    first, _ = fix("1\n00:00:00,000 --> 00:00:03,000\nThis is a line that is long enough to need a wrap at forty two columns for sure.\n", BUILTINS["latin"])
    text = serialize(first)
    second, fixes = fix(text, BUILTINS["latin"])
    assert fixes == []
    assert serialize(second) == text


def test_no_character_loss_on_split():
    text = "一二三四五六七八九十" * 4
    out, _ = fix(f"1\n00:00:00,000 --> 00:00:12,000\n{text}\n")
    assert "".join(c.text for c in out.cues).replace("\n", "") == text


def test_invalid_duration_left_untouched():
    out, fixes = fix("1\n00:00:02,000 --> 00:00:01,000\nHello there\n")
    assert out.cues[0].start_ms == 2000 and out.cues[0].end_ms == 1000
    assert [i.rule for i in check_document(out, CJK)] == ["invalid-duration"]


def test_fix_reports_snapshots():
    out, fixes = fix("1\n00:00:00,000 --> 00:00:10,000\nThis is a long sentence that is definitely too fast for nine characters per second.\n")
    assert fixes
    f = fixes[0]
    assert f.before.start_ms == 0
    assert f.after and f.after[0].text
    assert f.after[0].start_ms >= f.before.start_ms


def test_cps_extension():
    out, fixes = fix("1\n00:00:00,000 --> 00:00:01,000\n一二三四五六七八九十\n\n2\n00:00:03,000 --> 00:00:04,000\n好\n")
    assert out.cues[0].end_ms > 1000
    assert "extend-duration" in [f.action for f in fixes]


def test_second_pass_no_fix_even_with_remaining_issues():
    out, _ = fix("1\n00:00:00,000 --> 00:00:01,000\n一二三四五六七八九十\n")
    text = serialize(out)
    again, fixes = fix(text)
    assert fixes == []
    assert serialize(again) == text


def test_unfixable_short_and_gap():
    # 500ms cue followed immediately by another; neither trim nor shift can keep 1000ms.
    out, fixes = fix("1\n00:00:00,000 --> 00:00:00,500\nHi\n\n2\n00:00:00,550 --> 00:00:02,000\nThere\n")
    assert any(i.rule in {"duration-too-short", "gap-too-small"} for i in check_document(out, CJK))


def test_unfixable_long_unbreakable_token():
    out, _ = fix("1\n00:00:00,000 --> 00:00:20,000\n" + "x" * 100 + "\n", BUILTINS["latin"])
    assert len(out.cues) == 1
    assert "duration-too-long" in [i.rule for i in check_document(out, BUILTINS["latin"])]


def test_unfixable_cps_no_room():
    out, _ = fix("1\n00:00:00,000 --> 00:00:01,000\n一二三四五六七八九十\n\n2\n00:00:01,080 --> 00:00:02,000\n好\n")
    assert "cps-too-high" in [i.rule for i in check_document(out, CJK)]


def test_inline_markup_reopened_across_lines():
    text = "<i>" + "一二三四五六七八九十" * 3 + "</i>"
    out, _ = fix(f"1\n00:00:00,000 --> 00:00:12,000\n{text}\n")
    for cue in out.cues:
        assert cue.text.count("<i>") == cue.text.count("</i>")
        assert cue.text.startswith("<i>") and cue.text.endswith("</i>")


def test_split_at_most_eight_segments():
    # 100 seconds needs at most 8 pieces under the 8000ms cap, so the splitter
    # must not create more than 8 cues from one source cue.
    text = "一二三四五六七八九十" * 10
    out, _ = fix(f"1\n00:00:00,000 --> 00:01:40,000\n{text}\n")
    assert len(out.cues) <= 8
