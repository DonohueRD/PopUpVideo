import os
import re
import tempfile

import pytest

from subtitles import ZONES, CATEGORIES, build_timing, build_ass, layout_bubble, measure, BUBBLE_FONT

FACTOIDS_8 = [{"text": f"Fact {i}", "category": "trivia"} for i in range(8)]
LONG = ("Paul Wall's real name is Paul Michael Slayton. He also ran a custom grill business "
        "making diamond mouthpieces for the stars, and once sold one to a chart-topping pop act.")


def _ass(timed, **kw):
    with tempfile.TemporaryDirectory() as d:
        path = build_ass(timed, os.path.join(d, "test.ass"), **kw)
        return open(path).read()


def _dialogues(content):
    return [l for l in content.splitlines() if l.startswith("Dialogue:")]


# --- timing -----------------------------------------------------------------

def test_first_factoid_at_15s():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    assert timed[0]["start"] == 15.0


def test_each_factoid_displays_5s():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    for f in timed:
        assert f["end"] - f["start"] == pytest.approx(5.0, abs=1e-9)


def test_no_factoid_in_final_30s():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    for f in timed:
        assert f["end"] <= 270.0  # 300 - 30


def test_gap_at_least_25s():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    for i in range(1, len(timed)):
        gap = timed[i]["start"] - timed[i - 1]["start"]
        # gap = display_duration(5) + inter-factoid spacing(>=25)
        assert gap >= 30.0  # 5s display + 25s minimum gap


def test_short_video_stops_before_tail():
    # 2-min video can't fit 8 factoids — should fit as many as possible
    timed = build_timing(FACTOIDS_8, duration_seconds=120.0)
    assert len(timed) < 8
    for f in timed:
        assert f["end"] <= 90.0  # 120 - 30


def test_no_consecutive_same_zone():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    for i in range(1, len(timed)):
        assert timed[i]["zone_index"] != timed[i - 1]["zone_index"]


def test_five_zones_with_center_clear():
    assert ZONES == ["TL", "TR", "BL", "BR", "BC"]
    timed = build_timing(FACTOIDS_8 * 3, duration_seconds=2000.0)
    assert {f["zone_index"] for f in timed} <= set(range(5))


def test_timing_carries_category():
    facts = [{"text": "A", "category": "chart"}, {"text": "B", "category": "recording"}]
    timed = build_timing(facts, duration_seconds=300.0)
    assert [f["category"] for f in timed] == ["chart", "recording"]


def test_timing_defaults_missing_category_to_trivia():
    timed = build_timing([{"text": "A"}], duration_seconds=300.0)
    assert timed[0]["category"] == "trivia"


# --- layout -----------------------------------------------------------------

@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("text", ["Short one.", LONG])
@pytest.mark.parametrize("w", [1920, 1440])
def test_bubble_stays_inside_frame(zone, text, w):
    b = layout_bubble(zone, text, w=w)
    x0, y0, x1, y1 = b["bbox"]
    assert 0 <= x0 < x1 <= w
    assert 0 <= y0 < y1 <= 1080


@pytest.mark.parametrize("zone", ["TL", "TR"])
def test_top_bubbles_sit_below_corner_tag(zone):
    assert layout_bubble(zone, LONG)["bbox"][1] >= 150


def test_bubble_lines_fit_text_column():
    b = layout_bubble("TL", LONG)
    for line in b["lines"]:
        assert measure(BUBBLE_FONT, b["em"], line) <= b["text_w"] + 1


def test_long_factoid_stays_readable():
    b = layout_bubble("BR", LONG)
    assert len(b["lines"]) <= 5
    assert b["em"] >= 26


# --- ASS output -------------------------------------------------------------

def test_build_ass_creates_file():
    timed = build_timing(FACTOIDS_8[:3], duration_seconds=300.0)
    content = _ass(timed)
    assert "[Script Info]" in content
    assert "Fact 0" in content


def test_build_ass_contains_all_factoids():
    timed = build_timing(FACTOIDS_8, duration_seconds=300.0)
    content = _ass(timed)
    for i in range(len(timed)):
        assert f"Fact {i}" in content


def test_bubble_is_white_box_with_blue_outline():
    timed = build_timing(FACTOIDS_8[:1], duration_seconds=300.0)
    content = _ass(timed)
    assert r"\3c&HD85B1E&" in content  # #1E5BD8 in ASS BGR
    assert r"\1c&HFFFFFF&" in content
    assert r"\fnArchivo Black" in content


def test_bubble_has_pop_animation():
    timed = build_timing(FACTOIDS_8[:1], duration_seconds=300.0)
    content = _ass(timed)
    assert r"\fscx0\fscy0" in content
    assert r"\t(" in content


def test_bubble_shapes_animate_from_their_own_centre():
    """Shapes are drawn in local coords so the pop scales from the bubble, not the frame corner."""
    timed = build_timing(FACTOIDS_8[:1], duration_seconds=300.0)
    shapes = [l for l in _dialogues(_ass(timed)) if r"\p1" in l and r"\fscx0" in l]
    assert shapes
    for l in shapes:
        assert r"\pos(0,0)" not in l


def test_each_category_gets_its_own_icon():
    drawings = {}
    for cat in CATEGORIES:
        timed = [{"text": "X", "start": 15.0, "end": 20.0, "zone_index": 0, "category": cat}]
        drawings[cat] = "\n".join(l.split(",", 9)[9] for l in _dialogues(_ass(timed)))
    assert len(set(drawings.values())) == len(CATEGORIES)


def test_unknown_category_falls_back():
    timed = [{"text": "X", "start": 15.0, "end": 20.0, "zone_index": 0, "category": "weird"}]
    assert "X" in _ass(timed)


def test_text_cannot_inject_override_tags():
    timed = [{"text": r"Hit {\fs200} big \N now", "start": 15.0, "end": 20.0, "zone_index": 0,
              "category": "chart"}]
    content = _ass(timed)
    assert r"{\fs200}" not in content
    assert r"\N now" not in content


def test_playres_follows_video_aspect():
    content = _ass([], width=1440, height=1080)
    assert "PlayResX: 1440" in content
    assert "PlayResY: 1080" in content


# --- title card + corner tag ------------------------------------------------

def _lines_with(content, needle):
    return [l for l in _dialogues(content) if needle in l]


def test_intro_card_shows_artist_and_song_then_fades():
    content = _ass([], artist="Paul Wall", song="Sittin' Sidewayz", duration_seconds=200.0)
    assert "HUEY" in content
    intro_artist = [l for l in _lines_with(content, "PAUL WALL") if "0:00:00" in l.split(",")[1]]
    assert intro_artist, "artist name should appear on the opening card"
    assert r"\fad(" in intro_artist[0]
    end = intro_artist[0].split(",")[2]
    assert end.startswith("0:00:06") or end.startswith("0:00:07")


def test_corner_tag_takes_over_until_the_end():
    content = _ass([], artist="Paul Wall", song="Sittin' Sidewayz", duration_seconds=200.0)
    tags = [l for l in _lines_with(content, "Sittin' Sidewayz") if l.split(",")[1].startswith("0:00:06")]
    assert tags, "corner tag should start as the opening card fades"
    assert all(l.split(",")[2] == "0:03:20.00" for l in tags)


def test_no_title_events_without_artist():
    content = _ass(build_timing(FACTOIDS_8[:1], duration_seconds=300.0))
    assert "HUEY" not in content


def test_long_artist_name_shrinks_to_fit():
    long_artist = "The Notorious B.I.G. featuring Puff Daddy and Mase"
    content = _ass([], artist=long_artist, song="Mo Money Mo Problems", duration_seconds=200.0)
    line = _lines_with(content, long_artist.upper())[0]
    short = _lines_with(_ass([], artist="Mase", song="X", duration_seconds=200.0), "MASE")[0]
    fs = lambda l: float(re.search(r"\\fs([\d.]+)", l).group(1))
    assert fs(line) < fs(short)
