"""
WORKER 3: THE ARTIST
Reads data.json (made by collector.py) and draws a "Market Wrap" scoreboard
picture, saved as card.png (1080 x 1350, a good size for LinkedIn on phones).

Needs:   pip install pillow
Run:     python artist.py
"""

import json
import sys
from collections import Counter
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# ---- SETTINGS YOU CAN CHANGE ------------------------------------------
TITLE = "MARKET WRAP"
BYLINE = ""          # for example "by Aaditya Agarwal" (leave empty for none)
# -----------------------------------------------------------------------

W, H = 1080, 1350
BG = (11, 31, 58)
TILE = (19, 41, 75)
WHITE = (255, 255, 255)
GRAY = (148, 163, 184)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
BLUE = (96, 165, 250)

# Rates and currencies: "up" is not simply good or bad, so they get a neutral colour.
NEUTRAL_TICKERS = {"USDINR=X", "DX-Y.NYB", "^TNX"}

SHORT_NAMES = {"US 10Y yield (%)": "US 10Y yield"}

BOLD_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
REGULAR_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def nice_date(iso_date):
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%a %d %b %Y")
    except ValueError:
        return iso_date


def colour_for(row):
    if row["ticker"] in NEUTRAL_TICKERS:
        return BLUE
    return GREEN if row["change"] >= 0 else RED


def change_text(row):
    if row["kind"] == "yield":
        if abs(row["change"] - round(row["change"])) < 1e-9:
            return f"{row['change']:+.0f} bps"
        return f"{row['change']:+.1f} bps"
    return f"{row['change']:+.2f}%"


def level_text(row):
    if row["kind"] == "yield":
        return f"{row['last']:.2f}%"
    return f"{row['last']:,.2f}"


def draw_triangle(draw, cx, cy, up, colour):
    if up:
        points = [(cx, cy - 11), (cx - 11, cy + 9), (cx + 11, cy + 9)]
    else:
        points = [(cx, cy + 11), (cx - 11, cy - 9), (cx + 11, cy - 9)]
    draw.polygon(points, fill=colour)


def latest_session_date(markets):
    """Use India's date if available, otherwise the most common date."""
    for row in markets:
        if row["ticker"] == "^NSEI":
            return row["as_of"]
    return Counter(r["as_of"] for r in markets).most_common(1)[0][0]


def biggest_move(markets):
    candidates = [r for r in markets if r["kind"] == "price" and r["ticker"] not in NEUTRAL_TICKERS]
    if not candidates:
        return None
    return max(candidates, key=lambda r: abs(r["change"]))


def main():
    try:
        with open("data.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit("data.json not found. Run  python collector.py  first.")

    markets = data["markets"]
    if not markets:
        sys.exit("data.json has no market numbers. Run  python collector.py  again.")

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = font(BOLD_FONTS, 74)
    f_sub = font(REGULAR_FONTS, 32)
    f_sub_bold = font(BOLD_FONTS, 32)
    f_tag = font(BOLD_FONTS, 19)
    f_name = font(BOLD_FONTS, 28)
    f_level = font(REGULAR_FONTS, 24)
    f_foot = font(REGULAR_FONTS, 22)

    # ---- header
    draw.text((50, 48), TITLE, font=f_title, fill=WHITE)
    draw.text((50, 150), f"Last trading session: {nice_date(latest_session_date(markets))}",
              font=f_sub, fill=GRAY)
    mover = biggest_move(markets)
    if mover:
        label = "Biggest move: "
        draw.text((50, 196), label, font=f_sub, fill=GRAY)
        x = 50 + draw.textlength(label, font=f_sub)
        draw.text((x, 196), f"{mover['name']} {change_text(mover)}", font=f_sub_bold, fill=colour_for(mover))
    if BYLINE:
        draw.text((W - 50, 70), BYLINE, font=f_sub, fill=GRAY, anchor="ra")

    # ---- tiles (two columns)
    margin, gap_x, gap_y = 50, 20, 14
    tile_w = (W - 2 * margin - gap_x) // 2
    tile_h = 118
    top = 270

    for i, row in enumerate(markets):
        col, line = i % 2, i // 2
        x = margin + col * (tile_w + gap_x)
        y = top + line * (tile_h + gap_y)
        colour = colour_for(row)

        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=18, fill=TILE)
        draw.rounded_rectangle((x, y + 14, x + 8, y + tile_h - 14), radius=4, fill=colour)

        name = SHORT_NAMES.get(row["name"], row["name"])
        draw.text((x + 30, y + 16), row["group"].upper(), font=f_tag, fill=GRAY)
        draw.text((x + 30, y + 42), name, font=f_name, fill=WHITE)
        draw.text((x + 30, y + 80), level_text(row), font=f_level, fill=GRAY)

        # Draw the change figure; shrink it a little if it would touch the name.
        text = change_text(row)
        right = x + tile_w - 26
        name_end = x + 30 + draw.textlength(name, font=f_name)
        size = 38
        while True:
            f_fit = font(BOLD_FONTS, size)
            text_w = draw.textlength(text, font=f_fit)
            if right - text_w - 33 > name_end + 14 or size <= 24:
                break
            size -= 2
        draw.text((right, y + 44), text, font=f_fit, fill=colour, anchor="rm")
        draw_triangle(draw, right - text_w - 22, y + 44, row["change"] >= 0, colour)

    # ---- footer
    footer_y = H - 118
    draw.text((50, footer_y), "Latest closing figures. Markets close at different times, so dates can differ.",
              font=f_foot, fill=GRAY)
    draw.text((50, footer_y + 36), "Data: Yahoo Finance. Educational content, not investment advice.",
              font=f_foot, fill=GRAY)

    img.save("card.png")
    print(f"Saved card.png ({W} x {H}) with {len(markets)} markets.")


if __name__ == "__main__":
    main()
