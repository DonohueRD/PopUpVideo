"""VH1-style Pop Up Video graphics as an ASS subtitle file.

Everything is laid out on a 1080-high canvas (PlayResX follows the video's aspect).
Shapes are ASS vector drawings (\\p1). Each filled outline is two stacked events:
an outline layer underneath and a borderless fill on top. Sub-paths must wind
clockwise or overlapping parts punch holes.
"""
import math
import random
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import ImageFont

FONTS_DIR = Path(__file__).parent / "fonts"
BUBBLE_FONT, BUBBLE_FAMILY = "ArchivoBlack-Regular.ttf", "Archivo Black"
TITLE_FONT, TITLE_FAMILY = "Bungee-Regular.ttf", "Bungee"
GLYPH_FONT, GLYPH_FAMILY = "LuckiestGuy-Regular.ttf", "Luckiest Guy"

H = 1080
ZONES = ["TL", "TR", "BL", "BR", "BC"]  # frame centre stays clear for the artist
CATEGORIES = ["chart", "recording", "artist", "production", "trivia", "cultural"]
MARGIN_X, TOP_Y, BOTTOM_Y = 70, 150, 90  # TOP_Y keeps bubbles under the corner tag

BLUE, ORANGE, SKY, ICE, NAVY = "1E5BD8", "F7931E", "4FA3FF", "A9D6FF", "061633"
BADGE_FILL = {"cultural": "FFFFFF", "recording": "F28A2E", "artist": "E2342D",
              "production": "FFD23F", "chart": "FFFFFF", "trivia": "E23D8C"}
BADGE_R, ARROW, OUTLINE, SHADOW = 60, 34, 7, 8
BADGE_Y = 0.46  # badge centre, as a fraction of bubble height
GAP, PAD_R, PAD_Y, LH = 28, 34, 26, 1.2
# (em, text column width) tried in order until the factoid fits the line budget
SIZES = [(31, 440, 4), (31, 560, 4), (28, 560, 5), (26, 620, 5)]

INTRO_START, INTRO_END, TAG_START = 0.4, 6.5, 6.2
POP_MS, SETTLE_MS, OUT_MS = 160, 80, 180


# --- fonts ------------------------------------------------------------------

@lru_cache(maxsize=None)
def _font(font_file, em):
    return ImageFont.truetype(str(FONTS_DIR / font_file), em)


@lru_cache(maxsize=None)
def _line_box(font_file):
    t = TTFont(FONTS_DIR / font_file)
    return (t["OS/2"].usWinAscent + t["OS/2"].usWinDescent) / t["head"].unitsPerEm


def ass_fs(font_file, em):
    """libass \\fs sizes the whole line box; convert from a true em size."""
    return em * _line_box(font_file)


def measure(font_file, em, text):
    return _font(font_file, round(em)).getlength(text)


def wrap(font_file, em, text, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if measure(font_file, em, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def fit_em(font_file, em, text, max_w):
    w = measure(font_file, em, text)
    return em if w <= max_w else em * max_w / w


# --- ASS helpers ------------------------------------------------------------

def ass_color(hex_rgb):
    return f"&H{hex_rgb[4:6]}{hex_rgb[2:4]}{hex_rgb[0:2]}&"


def escape(text):
    """Plain text only: no override blocks, no \\N-style escapes."""
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _seconds_to_ass(s: float) -> str:
    cs_total = round(s * 100)
    h, rem = divmod(cs_total, 360000)
    m, rem = divmod(rem, 6000)
    sec, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def _n(v):
    return f"{v:.0f}"


# --- vector paths (clockwise on screen) -------------------------------------

K = 0.5523  # bezier circle constant


def rounded_rect(x, y, w, h, r):
    k = K * r
    return " ".join([
        f"m {_n(x+r)} {_n(y)}", f"l {_n(x+w-r)} {_n(y)}",
        f"b {_n(x+w-r+k)} {_n(y)} {_n(x+w)} {_n(y+r-k)} {_n(x+w)} {_n(y+r)}",
        f"l {_n(x+w)} {_n(y+h-r)}",
        f"b {_n(x+w)} {_n(y+h-r+k)} {_n(x+w-r+k)} {_n(y+h)} {_n(x+w-r)} {_n(y+h)}",
        f"l {_n(x+r)} {_n(y+h)}",
        f"b {_n(x+r-k)} {_n(y+h)} {_n(x)} {_n(y+h-r+k)} {_n(x)} {_n(y+h-r)}",
        f"l {_n(x)} {_n(y+r)}",
        f"b {_n(x)} {_n(y+r-k)} {_n(x+r-k)} {_n(y)} {_n(x+r)} {_n(y)}",
    ])


def ellipse(cx, cy, rx, ry):
    kx, ky = K * rx, K * ry
    return (f"m {_n(cx)} {_n(cy-ry)} b {_n(cx+kx)} {_n(cy-ry)} {_n(cx+rx)} {_n(cy-ky)} {_n(cx+rx)} {_n(cy)} "
            f"b {_n(cx+rx)} {_n(cy+ky)} {_n(cx+kx)} {_n(cy+ry)} {_n(cx)} {_n(cy+ry)} "
            f"b {_n(cx-kx)} {_n(cy+ry)} {_n(cx-rx)} {_n(cy+ky)} {_n(cx-rx)} {_n(cy)} "
            f"b {_n(cx-rx)} {_n(cy-ky)} {_n(cx-kx)} {_n(cy-ry)} {_n(cx)} {_n(cy-ry)}")


def poly(pts):
    return f"m {_n(pts[0][0])} {_n(pts[0][1])} " + " ".join(f"l {_n(x)} {_n(y)}" for x, y in pts[1:])


def rect(x, y, w, h):
    return poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


# A "part" is one vector-drawing event: its layer, border width, colour tags, path and \pos offset.

def _part(layer, path, tags, bord=0, off=(0, 0)):
    return {"layer": layer, "path": path, "tags": tags, "bord": bord, "off": off}


def outlined(path, line, fill, bord, layer):
    return [_part(layer, path, rf"\1c{ass_color(line)}\3c{ass_color(line)}", bord),
            _part(layer + 1, path, rf"\1c{ass_color(fill)}")]


def filled(path, fill, layer):
    return [_part(layer, path, rf"\1c{ass_color(fill)}")]


def icon_parts(cat, cx, cy, s, layer=6):
    """Vector icon centred on (cx, cy), roughly 2s across."""
    if cat == "cultural":  # globe
        return (outlined(ellipse(cx, cy, s, s), "0B2E6B", "3D8BFF", 3, layer)
                + filled(" ".join([ellipse(cx - .3*s, cy - .25*s, .38*s, .3*s),
                                   ellipse(cx + .35*s, cy + .3*s, .3*s, .38*s),
                                   ellipse(cx + .2*s, cy - .55*s, .2*s, .12*s)]), "3FB34F", layer + 2))
    if cat == "recording":  # beamed eighth notes
        return filled(" ".join([
            ellipse(cx - .4*s, cy + .5*s, .3*s, .22*s), ellipse(cx + .45*s, cy + .32*s, .3*s, .22*s),
            rect(cx - .2*s, cy - .55*s, .14*s, 1.05*s), rect(cx + .65*s, cy - .75*s, .14*s, 1.07*s),
            poly([(cx - .2*s, cy - .55*s), (cx + .79*s, cy - .78*s), (cx + .79*s, cy - .52*s),
                  (cx - .2*s, cy - .29*s)])]), "4A2206", layer)
    if cat == "artist":  # star
        pts = []
        for i in range(10):
            a, r = math.radians(-90 + 36 * i), s * (1.05 if i % 2 == 0 else .44)
            pts.append((cx + math.cos(a) * r, cy + .06*s + math.sin(a) * r))
        return outlined(poly(pts), "7A1A10", "FFD23F", 3, layer)
    if cat == "production":  # film camera
        return (filled(" ".join([
            rect(cx - .75*s, cy - .1*s, 1.05*s, .7*s), ellipse(cx - .45*s, cy - .42*s, .3*s, .3*s),
            ellipse(cx + .08*s, cy - .48*s, .34*s, .34*s),
            poly([(cx + .3*s, cy + .08*s), (cx + .85*s, cy - .15*s), (cx + .85*s, cy + .75*s),
                  (cx + .3*s, cy + .5*s)])]), "111111", layer)
            + filled(ellipse(cx - .45*s, cy - .42*s, .1*s, .1*s) + " "
                     + ellipse(cx + .08*s, cy - .48*s, .11*s, .11*s), "FFD23F", layer + 1))
    if cat == "chart":  # ascending bars
        base = cy + .7*s
        bars = [rect(cx + dx*s, base - hh*s, .42*s, hh*s) for dx, hh in ((-.72, .55), (-.21, .95), (.3, 1.4))]
        return (outlined(" ".join(bars), "0F4D1F", "2EAA4A", 3, layer)
                + filled(rect(cx - .9*s, base, 1.8*s, .12*s), "0F4D1F", layer + 2))
    return []  # trivia: a "?" glyph, emitted as text by the caller


# --- bubble layout ----------------------------------------------------------

def _place(zone, w_total, h_total, w):
    x = {"TL": MARGIN_X, "BL": MARGIN_X, "TR": w - MARGIN_X - w_total,
         "BR": w - MARGIN_X - w_total, "BC": (w - w_total) / 2}[zone]
    y = TOP_Y if zone in ("TL", "TR") else H - BOTTOM_Y - h_total
    return x, y


def layout_bubble(zone, text, w=1920, h=H):
    """Size and position one bubble. Coordinates are on the 1080-high canvas."""
    for em, text_w, max_lines in SIZES:
        lines = wrap(BUBBLE_FONT, em, text, text_w)
        if len(lines) <= max_lines:
            break
    used_w = max(measure(BUBBLE_FONT, em, l) for l in lines)
    bw = BADGE_R + GAP + used_w + PAD_R
    bh = max(len(lines) * em * LH + PAD_Y * 2, BADGE_R * 1.7)
    # how far the badge, arrow, outline and shadow reach past the box itself
    badge_reach = BADGE_R + 6
    left = BADGE_R + ARROW + 14  # bubble's left edge runs through the badge centre
    right = OUTLINE + SHADOW
    top = max(OUTLINE, badge_reach - bh * BADGE_Y)
    bottom = max(OUTLINE + SHADOW, badge_reach - bh * (1 - BADGE_Y))
    w_total, h_total = left + bw + right, top + bh + bottom
    ox, oy = _place(zone, w_total, h_total, w)
    x, y = ox + left, oy + top
    return {
        "lines": lines, "em": em, "text_w": text_w,
        "x": x, "y": y, "bw": bw, "bh": bh, "cx": x + bw / 2, "cy": y + bh / 2,
        "bbox": (ox, oy, ox + w_total, oy + h_total),
    }


def bubble_parts(b, cat):
    """Shape parts in coordinates local to the bubble centre, so the pop scales from there."""
    hw, hh = b["bw"] / 2, b["bh"] / 2
    box = rounded_rect(-hw, -hh, b["bw"], b["bh"], 26)
    parts = [_part(0, box, r"\1c&H000000&\3c&H000000&\1a&H88&\3a&H88&", OUTLINE, (SHADOW, SHADOW))]
    parts += outlined(box, BLUE, "FFFFFF", OUTLINE, 1)
    bcx, bcy = -hw, -hh + b["bh"] * BADGE_Y
    parts += outlined(ellipse(bcx, bcy, BADGE_R, BADGE_R), BLUE, BADGE_FILL.get(cat, BADGE_FILL["trivia"]), 6, 3)
    # orange pointer at ~10 o'clock, aimed at the badge centre
    a = math.radians(200)
    tip = (bcx + math.cos(a) * (BADGE_R + 5), bcy + math.sin(a) * (BADGE_R + 5))
    d = a + math.pi
    L, hl, hwid, sw = ARROW + 8, 24, 20, 8
    local = [(0, 0), (-hl, hwid), (-hl, sw), (-L, sw), (-L, -sw), (-hl, -sw), (-hl, -hwid)]
    pts = [(tip[0] + px * math.cos(d) - py * math.sin(d), tip[1] + px * math.sin(d) + py * math.cos(d))
           for px, py in local]
    parts += outlined(poly(pts), BLUE, ORANGE, 3, 3)
    parts += icon_parts(cat, bcx, bcy, BADGE_R * 0.6)
    return parts, (bcx, bcy)


def _pop(dur_ms, bord):
    grow = rf"\fscx0\fscy0\bord0\t(0,{POP_MS},\fscx112\fscy112\bord{bord})"
    settle = rf"\t({POP_MS},{POP_MS + SETTLE_MS},\fscx100\fscy100)"
    out = rf"\t({dur_ms - OUT_MS},{dur_ms},\fscx0\fscy0\bord0)"
    return grow + settle + out


def bubble_events(f, w):
    cat = f.get("category", "trivia")
    cat = cat if cat in CATEGORIES else "trivia"
    b = layout_bubble(ZONES[f["zone_index"]], escape(f["text"]), w)
    start, end = _seconds_to_ass(f["start"]), _seconds_to_ass(f["end"])
    dur = round((f["end"] - f["start"]) * 1000)
    parts, (bcx, bcy) = bubble_parts(b, cat)
    ev = []
    for p in parts:
        dx, dy = p["off"]
        ev.append((p["layer"], start, end,
                   rf"{{\an7\pos({_n(b['cx'] + dx)},{_n(b['cy'] + dy)})\shad0{p['tags']}"
                   rf"{_pop(dur, p['bord'])}\p1}}{p['path']}"))
    if cat == "trivia":
        gx, gy = b["cx"] + bcx, b["cy"] + bcy + BADGE_R * 0.07
        ev.append((8, start, end,
                   rf"{{\an5\pos({_n(gx)},{_n(gy)})\fn{GLYPH_FAMILY}\fs{ass_fs(GLYPH_FONT, BADGE_R * 1.14):.0f}"
                   rf"\1c&HFFFFFF&\3c{ass_color('5A0E33')}\shad0{_pop(dur, 3)}}}?"))
    fs = ass_fs(BUBBLE_FONT, b["em"])
    step = b["em"] * LH
    tx = b["x"] + BADGE_R + GAP
    y0 = b["cy"] - step * (len(b["lines"]) - 1) / 2
    fade = rf"\alpha&HFF&\t({POP_MS},{POP_MS + 120},\alpha&H00&)\t({dur - OUT_MS - 100},{dur - OUT_MS},\alpha&HFF&)"
    for i, line in enumerate(b["lines"]):
        ev.append((9, start, end,
                   rf"{{\an4\q2\pos({_n(tx)},{_n(y0 + i * step)})\fn{BUBBLE_FAMILY}\fs{fs:.1f}"
                   rf"\1c&H111111&\bord0\shad0{fade}}}{line}"))
    return ev


# --- title card + corner tag ------------------------------------------------

def title_events(artist, song, duration_seconds, w):
    artist, song = escape(artist).upper(), escape(song)
    ev = []
    # opening lower third: slides in from the left, fades out into the corner tag
    a_em = fit_em(TITLE_FONT, 64, artist, w * 0.62)
    s_em = fit_em(BUBBLE_FONT, 40, song, w * 0.62)
    bar_w = max(measure(TITLE_FONT, a_em, artist), measure(BUBBLE_FONT, s_em, song)) + 150
    start, end = _seconds_to_ass(INTRO_START), _seconds_to_ass(INTRO_END)
    slide, fad = 400, r"\fad(400,600)"

    def mv(x, y):
        return rf"\move({_n(x - 60)},{_n(y)},{_n(x)},{_n(y)},0,{slide})"

    ev.append((18, start, end, rf"{{\an7{mv(0, 840)}\p1\bord0\shad0\1c{ass_color(NAVY)}\1a&H30&{fad}}}"
                               + rect(0, 0, bar_w, 180)))
    ev.append((19, start, end, rf"{{\an7{mv(0, 840)}\p1\bord0\shad0\1c{ass_color(SKY)}{fad}}}" + rect(0, 0, 22, 180)))
    ev.append((20, start, end, rf"{{\an4{mv(72, 808)}\fn{TITLE_FAMILY}\fs{ass_fs(TITLE_FONT, 26):.0f}"
                               rf"\1c&HFFFFFF&\bord0\shad2\4c&H000000&{fad}}}HUEY {{\1c{ass_color(SKY)}}}POP UP "
                               rf"{{\1c&HFFFFFF&}}VIDEO"))
    ev.append((20, start, end, rf"{{\an4{mv(70, 900)}\fn{TITLE_FAMILY}\fs{ass_fs(TITLE_FONT, a_em):.1f}"
                               rf"\1c&HFFFFFF&\bord0\shad0{fad}}}{artist}"))
    ev.append((20, start, end, rf"{{\an4{mv(72, 972)}\fn{BUBBLE_FAMILY}\fs{ass_fs(BUBBLE_FONT, s_em):.1f}"
                               rf"\1c{ass_color(ICE)}\bord0\shad0{fad}}}{song}"))
    # corner tag for the rest of the video
    start, end = _seconds_to_ass(TAG_START), _seconds_to_ass(duration_seconds)
    ta_em = fit_em(TITLE_FONT, 30, artist, w * 0.42)
    ts_em = fit_em(BUBBLE_FONT, 24, song, w * 0.42)
    navy = ass_color(NAVY)
    ev.append((20, start, end, rf"{{\an7\pos(60,44)\fn{TITLE_FAMILY}\fs{ass_fs(TITLE_FONT, ta_em):.1f}"
                               rf"\1c&HFFFFFF&\bord4\3c{navy}\shad3\4c&H000000&\4a&H60&\fad(600,0)}}{artist}"))
    ev.append((20, start, end, rf"{{\an7\pos(62,88)\fn{BUBBLE_FAMILY}\fs{ass_fs(BUBBLE_FONT, ts_em):.1f}"
                               rf"\1c{ass_color(ICE)}\bord3\3c{navy}\shad0\fad(600,0)}}{song}"))
    return ev


# --- public API -------------------------------------------------------------

def build_timing(
    factoids: list[dict],
    duration_seconds: float,
    first_factoid_at: float = 15.0,
    display_duration: float = 5.0,
    min_gap: float = 25.0,
    max_gap: float = 35.0,
    tail_reserve: float = 30.0,
) -> list[dict]:
    """Assign start/end times and screen zones to factoids."""
    result = []
    t = first_factoid_at
    last_zone = -1

    for factoid in factoids:
        end = t + display_duration
        if end > duration_seconds - tail_reserve:
            break

        # Pick zone that differs from previous
        zone = random.choice([z for z in range(len(ZONES)) if z != last_zone])
        last_zone = zone

        result.append({
            "text": factoid["text"],
            "category": factoid.get("category", "trivia"),
            "start": t,
            "end": end,
            "zone_index": zone,
        })

        t += display_duration + random.uniform(min_gap, max_gap)

    return result


def build_ass(
    timed_factoids: list[dict],
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    artist: str | None = None,
    song: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    """Write an ASS file with the title card, corner tag and VH1-style bubbles."""
    w = round(H * width / height)
    events = []
    if artist and duration_seconds:
        events += title_events(artist, song or "", duration_seconds, w)
    for f in timed_factoids:
        events += bubble_events(f, w)

    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {H}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Pop,{BUBBLE_FAMILY},40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    body = [f"Dialogue: {layer},{start},{end},Pop,,0,0,0,,{text}" for layer, start, end, text in events]
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head + body) + "\n")
    return output_path
