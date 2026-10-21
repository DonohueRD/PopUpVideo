import math, subprocess, sys
from pathlib import Path
from PIL import ImageFont

FONTS = Path("/DATA/docker/tunarr/popup-video/fonts")
OUT = Path(__file__).parent
FRAME = OUT / "frame_60.png"
W, H = 1920, 1080
K = 0.5523

FACTS = {
    "name": "Paul Wall's real name is Paul Michael Slayton. He also ran a custom grill business making diamond mouthpieces for the stars.",
    "slab": "Sitting sideways is a Houston slab tradition: recline the seat and lean low to one side while cruising slow.",
    "pokey": "Big Pokey was a member of DJ Screw's legendary Screwed Up Click.",
    "swangas": "Swangas are the wire rims that poke out like elbows. Houston drivers call them elbows, too.",
    "chart": "The album debuted at No. 1 on the Billboard 200. Not bad for a guy who started out handing out flyers.",
}


def ass_color(hex_rgb, alpha=0):
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&"


from fontTools.ttLib import TTFont
_FS = {}


def ass_fs(font_file, em):
    if font_file not in _FS:
        t = TTFont(FONTS / font_file)
        _FS[font_file] = (t["OS/2"].usWinAscent + t["OS/2"].usWinDescent) / t["head"].unitsPerEm
    return em * _FS[font_file]


def measure(font_file, em, text, max_w, lh=1.18):
    font = ImageFont.truetype(str(FONTS / font_file), em)
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    width = max(font.getlength(l) for l in lines)
    return lines, width, len(lines) * em * lh


def f(n):
    return f"{n:.0f}"


def rounded_rect(x, y, w, h, r, tail=None):
    """tail = (edge, base_x, tip_x, tip_y, half_width)"""
    k = K * r
    p = [f"m {f(x+r)} {f(y)}"]
    if tail and tail[0] == "top":
        _, bx, tx, ty, tw = tail
        p += [f"l {f(bx-tw)} {f(y)}", f"b {f(bx-tw*0.3)} {f(y-(y-ty)*0.4)} {f(tx)} {f(ty+ (y-ty)*0.15)} {f(tx)} {f(ty)}",
              f"b {f(bx+tw*0.1)} {f(y-(y-ty)*0.5)} {f(bx+tw*0.6)} {f(y)} {f(bx+tw)} {f(y)}"]
    p += [f"l {f(x+w-r)} {f(y)}", f"b {f(x+w-r+k)} {f(y)} {f(x+w)} {f(y+r-k)} {f(x+w)} {f(y+r)}",
          f"l {f(x+w)} {f(y+h-r)}", f"b {f(x+w)} {f(y+h-r+k)} {f(x+w-r+k)} {f(y+h)} {f(x+w-r)} {f(y+h)}"]
    if tail and tail[0] == "bottom":
        _, bx, tx, ty, tw = tail
        p += [f"l {f(bx+tw)} {f(y+h)}", f"b {f(bx+tw*0.3)} {f(y+h+(ty-y-h)*0.4)} {f(tx)} {f(ty-(ty-y-h)*0.15)} {f(tx)} {f(ty)}",
              f"b {f(bx-tw*0.1)} {f(y+h+(ty-y-h)*0.5)} {f(bx-tw*0.6)} {f(y+h)} {f(bx-tw)} {f(y+h)}"]
    p += [f"l {f(x+r)} {f(y+h)}", f"b {f(x+r-k)} {f(y+h)} {f(x)} {f(y+h-r+k)} {f(x)} {f(y+h-r)}",
          f"l {f(x)} {f(y+r)}", f"b {f(x)} {f(y+r-k)} {f(x+r-k)} {f(y)} {f(x+r)} {f(y)}"]
    return " ".join(p)


def ellipse(cx, cy, rx, ry):
    kx, ky = K * rx, K * ry
    return (f"m {f(cx)} {f(cy-ry)} b {f(cx+kx)} {f(cy-ry)} {f(cx+rx)} {f(cy-ky)} {f(cx+rx)} {f(cy)} "
            f"b {f(cx+rx)} {f(cy+ky)} {f(cx+kx)} {f(cy+ry)} {f(cx)} {f(cy+ry)} "
            f"b {f(cx-kx)} {f(cy+ry)} {f(cx-rx)} {f(cy+ky)} {f(cx-rx)} {f(cy)} "
            f"b {f(cx-rx)} {f(cy-ky)} {f(cx-kx)} {f(cy-ry)} {f(cx)} {f(cy-ry)}")


def tail_poly(bx1, by1, bx2, by2, tx, ty):
    mx, my = (bx1 + bx2) / 2, (by1 + by2) / 2
    return (f"m {f(bx1)} {f(by1)} b {f(mx + (tx-mx)*0.3)} {f(my + (ty-my)*0.6)} {f(tx)} {f(ty)} {f(tx)} {f(ty)} "
            f"b {f(tx)} {f(ty)} {f(mx + (tx-mx)*0.6)} {f(my + (ty-my)*0.2)} {f(bx2)} {f(by2)}")


ZONE_BOX = {  # anchor point for bubble outer box
    "TL": ("left", "top"), "TR": ("right", "top"),
    "BL": ("left", "bottom"), "BR": ("right", "bottom"), "BC": ("center", "bottom"),
}
MARGIN_X, TOP_Y, BOTTOM_Y = 70, 150, 90


def place(zone, bw, bh, tail_len):
    hx, vy = ZONE_BOX[zone]
    x = {"left": MARGIN_X, "right": W - MARGIN_X - bw, "center": (W - bw) / 2}[hx]
    y = TOP_Y if vy == "top" else H - BOTTOM_Y - bh - tail_len
    if vy == "bottom":
        y += tail_len
    return x, y


def tail_for(zone, x, y, bw, bh, tl, tw):
    cx = W / 2
    if zone in ("TL", "TR"):
        bx = x + bw * (0.72 if zone == "TL" else 0.28)
        tx = bx + (tl * 0.6 if zone == "TL" else -tl * 0.6)
        return ("bottom", bx, tx, y + bh + tl, tw)
    bx = x + bw * {"BL": 0.72, "BR": 0.28, "BC": 0.5}[zone]
    tx = bx + {"BL": tl * 0.6, "BR": -tl * 0.6, "BC": tl * 0.35}[zone]
    return ("top", bx, tx, y - tl, tw)


def shape_events(path, s, layer0=0):
    """Two-layer trick: outline+shadow layer underneath, clean fill on top."""
    ev = []
    if s.get("shadow"):
        sx, sy = s["shadow"]
        a = f"&H{s.get('shadow_a', 0):02X}&"
        ev.append((layer0, rf"{{\an7\pos({sx},{sy})\p1\bord{s['outline']}\shad0\1c{ass_color(s['shadow_col'])}\3c{ass_color(s['shadow_col'])}\1a{a}\3a{a}}}{path}"))
    ev.append((layer0 + 1, rf"{{\an7\pos(0,0)\p1\bord{s['outline']}\shad0\1c{ass_color(s['line'])}\3c{ass_color(s['line'])}}}{path}"))
    ev.append((layer0 + 2, rf"{{\an7\pos(0,0)\p1\bord0\shad0\1c{ass_color(s['fill'])}}}{path}"))
    return ev


def bubble(s, zone, text):
    if s.get("upper"):
        text = text.upper()
    lines, tw_, th_ = measure(s["font"], s["fs"], text, s["max_w"])
    pad_x, pad_y = s["pad"]
    shape = s["shape"]
    if shape == "oval":
        bw, bh = tw_ * 1.25 + pad_x * 2, th_ * 1.35 + pad_y * 2
    elif shape == "cloud":
        bw, bh = tw_ * 1.15 + pad_x * 2, th_ * 1.2 + pad_y * 2
    else:
        bw, bh = tw_ + pad_x * 2, th_ + pad_y * 2
    tl = s.get("tail_len", 60)
    x, y = place(zone, bw, bh, tl)
    ev = []
    if shape == "rect":
        tail = tail_for(zone, x, y, bw, bh, tl, s.get("tail_w", 26))
        ev += shape_events(rounded_rect(x, y, bw, bh, s["radius"], tail), s)
    elif shape == "oval":
        _, bx, tx, ty, _ = tail_for(zone, x, y, bw, bh, tl, 0)
        cx, cy, rx, ry = x + bw / 2, y + bh / 2, bw / 2, bh / 2
        by = cy + (ry * 0.75 if ty > cy else -ry * 0.75)
        hw = 42 if ty < cy else -42
        path = ellipse(cx, cy, rx, ry) + " " + tail_poly(bx - hw, by, bx + hw, by, tx, ty)
        ev += shape_events(path, s)
    elif shape == "cloud":
        cx, cy, rx, ry = x + bw / 2, y + bh / 2, bw / 2, bh / 2
        parts = [ellipse(cx, cy, rx * 0.92, ry * 0.85)]
        n = 14
        for i in range(n):
            a = 2 * math.pi * i / n
            px, py = cx + math.cos(a) * rx * 0.86, cy + math.sin(a) * ry * 0.80
            r = min(rx, ry) * (0.30 if i % 2 else 0.36)
            parts.append(ellipse(px, py, r * 1.15, r))
        _, bx, tx, ty, _ = tail_for(zone, x, y, bw, bh, tl + 30, 0)
        start_y = cy + (ry if ty > cy else -ry)
        for t, rr in ((0.35, 16), (0.7, 10), (1.0, 6)):
            parts.append(ellipse(bx + (tx - bx) * t, start_y + (ty - start_y) * t, rr * 1.2, rr))
        ev += shape_events(" ".join(parts), s)
    tx_c, ty_c = x + bw / 2, y + bh / 2
    rot = rf"\frz{s['rot']}" if s.get("rot") else ""
    fs = ass_fs(s["font"], s["fs"])
    step = s["fs"] * 1.18
    y0 = ty_c - step * (len(lines) - 1) / 2 + s["fs"] * s.get("nudge", 0)
    for i, line in enumerate(lines):
        ev.append((9, rf"{{\an5\q2\pos({tx_c:.0f},{y0 + i * step:.0f})\fn{s['family']}\fs{fs:.1f}\1c{ass_color(s['text'])}\bord0\shad0\fsp{s.get('fsp', 0)}{rot}}}{line}"))
    if s.get("rot"):
        ev = [(l, t.replace(r"\pos(", rf"\frz{s['rot']}\org({tx_c:.0f},{ty_c:.0f})\pos(", 1)) for l, t in ev]
    return ev


BLUE, ORANGE = "1E5BD8", "F7931E"


def poly(pts):
    """pts must be in clockwise (screen) order."""
    return f"m {f(pts[0][0])} {f(pts[0][1])} " + " ".join(f"l {f(x)} {f(y)}" for x, y in pts[1:])


def rect(x, y, w, h):
    return poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def fill_event(layer, path, col, extra=""):
    return (layer, rf"{{\an7\pos(0,0)\p1\bord0\shad0\1c{ass_color(col)}{extra}}}{path}")


def icon_events(cat, cx, cy, s, layer=6):
    """Vector icon centred on (cx, cy), roughly 2s across."""
    ev = []
    if cat == "cultural":  # globe
        ev += shape_events(ellipse(cx, cy, s, s), {"outline": 3, "line": "0B2E6B", "fill": "3D8BFF"}, layer - 1)
        ev.append(fill_event(layer + 2, " ".join([ellipse(cx - .3*s, cy - .25*s, .38*s, .3*s),
                                                  ellipse(cx + .35*s, cy + .3*s, .3*s, .38*s),
                                                  ellipse(cx + .2*s, cy - .55*s, .2*s, .12*s)]), "3FB34F"))
    elif cat == "recording":  # beamed eighth notes
        col = "4A2206"
        parts = [ellipse(cx - .4*s, cy + .5*s, .3*s, .22*s), ellipse(cx + .45*s, cy + .32*s, .3*s, .22*s),
                 rect(cx - .2*s, cy - .55*s, .14*s, 1.05*s), rect(cx + .65*s, cy - .75*s, .14*s, 1.07*s),
                 poly([(cx - .2*s, cy - .55*s), (cx + .79*s, cy - .78*s), (cx + .79*s, cy - .52*s),
                       (cx - .2*s, cy - .29*s)])]
        ev.append(fill_event(layer, " ".join(parts), col))
    elif cat == "artist":  # star
        pts = [(cx + math.cos(math.radians(-90 + 36 * i)) * (s * 1.05 if i % 2 == 0 else s * .44),
                cy + .06*s + math.sin(math.radians(-90 + 36 * i)) * (s * 1.05 if i % 2 == 0 else s * .44))
               for i in range(10)]
        ev += shape_events(poly(pts), {"outline": 3, "line": "7A1A10", "fill": "FFD23F"}, layer - 1)
    elif cat == "production":  # film camera
        col = "111111"
        parts = [rect(cx - .75*s, cy - .1*s, 1.05*s, .7*s), ellipse(cx - .45*s, cy - .42*s, .3*s, .3*s),
                 ellipse(cx + .08*s, cy - .48*s, .34*s, .34*s),
                 poly([(cx + .3*s, cy + .08*s), (cx + .85*s, cy - .15*s), (cx + .85*s, cy + .75*s),
                       (cx + .3*s, cy + .5*s)])]
        ev.append(fill_event(layer, " ".join(parts), col))
        ev.append(fill_event(layer + 1, ellipse(cx - .45*s, cy - .42*s, .1*s, .1*s) + " " +
                             ellipse(cx + .08*s, cy - .48*s, .11*s, .11*s), "FFD23F"))
    elif cat == "chart":  # ascending bars
        base = cy + .7*s
        bars = [rect(cx + dx*s, base - hh*s, .42*s, hh*s) for dx, hh in ((-.72, .55), (-.21, .95), (.3, 1.4))]
        ev += shape_events(" ".join(bars), {"outline": 3, "line": "0F4D1F", "fill": "2EAA4A"}, layer - 1)
        ev.append(fill_event(layer + 2, rect(cx - .9*s, base, 1.8*s, .12*s), "0F4D1F"))
    else:  # trivia
        LG = "LuckiestGuy-Regular.ttf"
        ev.append((layer + 2, rf"{{\an5\pos({cx:.0f},{cy + .12*s:.0f})\fnLuckiest Guy\fs{ass_fs(LG, s*1.9):.0f}"
                              rf"\1c&HFFFFFF&\bord3\3c{ass_color('5A0E33')}\shad0}}?"))
    return ev


BADGE_FILL = {"cultural": "FFFFFF", "recording": "F28A2E", "artist": "E2342D",
              "production": "FFD23F", "chart": "FFFFFF", "trivia": "E23D8C"}
VH1 = dict(font="ArchivoBlack-Regular.ttf", family="Archivo Black", fs=31, max_w=440, lh=1.2,
           badge_r=60, arrow=34, outline=7, pad=(28, 34, 26))  # pad = (gap after badge, right, top/bottom)


def vh1_bubble(zone, cat, text, s=VH1):
    R, A = s["badge_r"], s["arrow"]
    gap, pad_r, pad_y = s["pad"]
    lines, tw_, th_ = measure(s["font"], s["fs"], text, s["max_w"], s["lh"])
    bw = R + gap + tw_ + pad_r
    bh = max(th_ + pad_y * 2, R * 1.7)
    ox, y = place(zone, bw + R + A, bh, 0)
    x = ox + R + A  # bubble's left edge = badge centre
    ev = shape_events(rounded_rect(x, y, bw, bh, 26),
                      {"outline": s["outline"], "line": BLUE, "fill": "FFFFFF",
                       "shadow": (8, 8), "shadow_col": "000000", "shadow_a": 0x88})
    bcx, bcy = x, y + bh * 0.46
    ev += shape_events(ellipse(bcx, bcy, R, R), {"outline": 6, "line": BLUE, "fill": BADGE_FILL[cat]}, 3)
    # orange pointer at ~10 o'clock, aimed at the badge centre
    a = math.radians(200)
    tip = (bcx + math.cos(a) * (R + 5), bcy + math.sin(a) * (R + 5))
    d = a + math.pi  # direction the arrow points
    L, hl, hw, sw = A + 8, 24, 20, 8
    local = [(0, 0), (-hl, hw), (-hl, sw), (-L, sw), (-L, -sw), (-hl, -sw), (-hl, -hw)]
    pts = [(tip[0] + px * math.cos(d) - py * math.sin(d), tip[1] + px * math.sin(d) + py * math.cos(d))
           for px, py in local]
    ev += shape_events(poly(pts), {"outline": 3, "line": BLUE, "fill": ORANGE}, 3)
    ev += icon_events(cat, bcx, bcy, R * 0.6)
    fs = ass_fs(s["font"], s["fs"])
    step = s["fs"] * s["lh"]
    tx = x + R + gap
    y0 = y + bh / 2 - step * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        ev.append((9, rf"{{\an4\q2\pos({tx:.0f},{y0 + i * step:.0f})\fn{s['family']}\fs{fs:.1f}"
                      rf"\1c&H111111&\bord0\shad0}}{line}"))
    return ev


VH1_FACTS = {
    "chart": "The People's Champ debuted at No. 1 on the Billboard 200.",
    "recording": "Paul Wall cut this track for his major-label debut.",
    "artist": "Paul Wall's real name is Paul Michael Slayton.",
    "production": "The video was shot on the streets of Houston.",
    "trivia": "Swangas are wire rims that poke out like elbows.",
    "cultural": "Sitting sideways is a Houston slab move: lean low, cruise slow.",
}


def lockup_events(kind, artist, song):
    ev = []
    LG, AB, BG = "LuckiestGuy-Regular.ttf", "ArchivoBlack-Regular.ttf", "Bungee-Regular.ttf"
    yel = ass_color("FFE14D")
    if kind == "intro_a":
        ev.append((20, rf"{{\an1\pos(92,842)\fnLuckiest Guy\fs{ass_fs(LG, 34):.0f}\bord3\3c&H000000&\shad0\1c{yel}}}HUEY {{\1c&HFFFFFF&}}POP UP VIDEO"))
        ev.append((20, rf"{{\an1\pos(84,958)\fnLuckiest Guy\fs{ass_fs(LG, 100):.0f}\1c&HFFFFFF&\bord7\3c&H000000&\shad6\4c&H000000&}}{artist.upper()}"))
        _, sw, _ = measure(AB, 40, song, 2000)
        ev += shape_events(rounded_rect(90, 982, sw + 64, 68, 34), {"outline": 5, "line": "000000", "fill": "FFE14D"}, 18)
        ev.append((21, rf"{{\an5\pos({90 + (sw + 64) / 2:.0f},1016)\fnArchivo Black\fs{ass_fs(AB, 40):.0f}\1c&H000000&\bord0\shad0}}{song}"))
    elif kind == "intro_b":
        _, aw, _ = measure(BG, 64, artist.upper(), 3000)
        _, sw, _ = measure(AB, 40, song, 3000)
        bw = max(aw, sw) + 150
        sky, ice = ass_color("4FA3FF"), ass_color("A9D6FF")
        ev.append((18, r"{\an7\pos(0,0)\p1\bord0\shad0\1c" + ass_color("061633") + r"\1a&H30&}" + rounded_rect(0, 840, bw, 180, 0)))
        ev.append((19, rf"{{\an7\pos(0,0)\p1\bord0\shad0\1c{ass_color('4FA3FF')}}}" + rounded_rect(0, 840, 22, 180, 0)))
        ev.append((20, rf"{{\an4\pos(72,808)\fnBungee\fs{ass_fs(BG, 26):.0f}\1c&HFFFFFF&\bord0\shad2\4c&H000000&}}HUEY {{\1c{sky}}}POP UP {{\1c&HFFFFFF&}}VIDEO"))
        ev.append((20, rf"{{\an4\pos(70,900)\fnBungee\fs{ass_fs(BG, 64):.0f}\1c&HFFFFFF&\bord0\shad0}}{artist.upper()}"))
        ev.append((20, rf"{{\an4\pos(72,972)\fnArchivo Black\fs{ass_fs(AB, 40):.0f}\1c{ice}\bord0\shad0}}{song}"))
    elif kind == "bug":
        navy, ice = ass_color("061633"), ass_color("A9D6FF")
        ev.append((20, rf"{{\an7\pos(60,44)\fnBungee\fs{ass_fs(BG, 30):.0f}\1c&HFFFFFF&\bord4\3c{navy}\shad3\4c&H000000&\4a&H60&}}{artist.upper()}"))
        ev.append((20, rf"{{\an7\pos(62,88)\fnArchivo Black\fs{ass_fs(AB, 24):.0f}\1c{ice}\bord3\3c{navy}\shad0}}{song}"))
    return ev


def write_ass(path, events):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: D,Archivo Black,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: {l},0:00:00.00,0:00:10.00,D,,0,0,0,,{t}\n" for l, t in events)
    Path(path).write_text(head + body)


def render(name, events):
    ass = OUT / f"{name}.ass"
    write_ass(ass, events)
    jpg = OUT / f"{name}.jpg"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(FRAME), "-vf",
                        f"ass={ass}:fontsdir={FONTS},scale=1280:-1", "-q:v", "3", str(jpg)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    print(jpg)


STYLES = {
    "A_classic_balloon": dict(shape="oval", font="ArchivoBlack-Regular.ttf", family="Archivo Black", fs=30,
                              max_w=560, pad=(26, 22), text="111111", fill="FFFFFF", line="000000", outline=5,
                              tail_len=70, shadow=(8, 8), shadow_col="000000", shadow_a=0x90),
    "B_comic_panel": dict(shape="rect", font="Bangers-Regular.ttf", family="Bangers", fs=40, upper=True, fsp=1.5,
                          max_w=520, pad=(34, 24), radius=14, text="111111", fill="FFFFFF", line="000000",
                          outline=6, tail_len=70, tail_w=30, shadow=(12, 12), shadow_col="000000"),
    "C_thought_cloud": dict(shape="cloud", font="ArchivoBlack-Regular.ttf", family="Archivo Black", fs=30,
                            max_w=420, pad=(40, 34), text="111111", fill="FFFFFF", line="000000", outline=4,
                            tail_len=60),
    "D_yellow_tilt": dict(shape="rect", font="LuckiestGuy-Regular.ttf", family="Luckiest Guy", fs=34,
                          max_w=520, pad=(44, 30), radius=28, text="111111", fill="FFE14D", line="000000",
                          outline=6, tail_len=65, tail_w=28, rot=3, shadow=(10, 10), shadow_col="000000",
                          shadow_a=0x60),
    "E_neon_pop": dict(shape="rect", font="Bungee-Regular.ttf", family="Bungee", fs=30, max_w=620,
                       pad=(36, 26), radius=40, text="FFFFFF", fill="FF2E88", line="FFFFFF", outline=6,
                       tail_len=60, tail_w=28, shadow=(10, 10), shadow_col="000000", shadow_a=0x50),
    "F_marker_note": dict(shape="oval", font="PermanentMarker-Regular.ttf", family="Permanent Marker", fs=34,
                          max_w=440, pad=(24, 20), text="111111", fill="FFFFFF", line="111111", outline=4,
                          tail_len=60),
}
PLAN = [("A_classic_balloon", "TL", "name"), ("B_comic_panel", "TR", "chart"),
        ("C_thought_cloud", "BL", "pokey"), ("D_yellow_tilt", "BR", "swangas"),
        ("E_neon_pop", "BC", "slab"), ("F_marker_note", "TR", "pokey")]

ARTIST, SONG = "Paul Wall", "Sittin' Sidewayz ft. Big Pokey"
if __name__ == "__main__" and sys.argv[1:] == ["vh1"]:
    bug = lockup_events("bug", ARTIST, SONG)
    render("V1_vh1_TL_BR", bug + vh1_bubble("TL", "artist", VH1_FACTS["artist"])
           + vh1_bubble("BR", "chart", VH1_FACTS["chart"]))
    render("V2_vh1_TR_BL", bug + vh1_bubble("TR", "cultural", VH1_FACTS["cultural"])
           + vh1_bubble("BL", "production", VH1_FACTS["production"]))
    render("V3_vh1_BC", bug + vh1_bubble("BC", "recording", VH1_FACTS["recording"]))
    render("V4_vh1_trivia", bug + vh1_bubble("TR", "trivia", VH1_FACTS["trivia"]))
    render("T2_intro_lowerthird_blue", lockup_events("intro_b", ARTIST, SONG))
elif __name__ == "__main__":
    for name, zone, fact in PLAN:
        render(name, lockup_events("bug", ARTIST, SONG) + bubble(STYLES[name], zone, FACTS[fact]))
    render("T1_intro_cartoon", lockup_events("intro_a", ARTIST, SONG))
    render("T2_intro_lowerthird", lockup_events("intro_b", ARTIST, SONG))
    zones = []
    for z in ("TL", "TR", "BL", "BR", "BC"):
        x, y = place(z, 520, 200, 0)
        zones += shape_events(rounded_rect(x, y, 520, 200, 20), {"outline": 4, "line": "FFE14D", "fill": "000000"})
        zones = [(l, t.replace(r"\1c&H00000000&", r"\1c&H000000&\1a&HA0&")) for l, t in zones]
        zones.append((9, rf"{{\an5\pos({x+260:.0f},{y+100:.0f})\fnLuckiest Guy\fs60\1c" + ass_color("FFE14D") + rf"\bord4\3c&H000000&}}{z}"))
    render("Z_zone_map", lockup_events("bug", ARTIST, SONG) + zones)
