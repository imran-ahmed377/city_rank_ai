"""Draw the decorative skyline used as the website background.

Writes city_rank/templates/skyline.svg, which base.html includes inline on every
page. Run it again after changing anything below:

    python scripts/draw_skyline.py

The picture is three layers of flat building silhouettes (far = palest, near =
darkest), the CN Tower, a Ferris wheel and a faded mirror reflection under the
ground line. Shapes carry only CSS classes; the colours come from the
--city-far / --city-mid / --city-near tokens in style.css, so the same drawing
works in light and dark mode.

Building sizes come from a seeded random generator, so the output is the same
on every run. Change SEED for a different skyline.
"""

from __future__ import annotations

import random
from pathlib import Path

SEED = 7
WIDTH = 2000          # viewBox width; wide so big screens are not cropped
GROUND = 300          # y of the ground line; everything below it is the reflection
HEIGHT = 400          # viewBox height (GROUND + 100 for the reflection)
CN_TOWER_X = 860      # both landmarks sit near the centre, which narrow screens keep
WHEEL_X, WHEEL_Y, WHEEL_R = 1110, 172, 70

OUT = Path(__file__).resolve().parent.parent / "city_rank" / "templates" / "skyline.svg"


# ---- Shape helpers: each returns one SVG path fragment ------------------------------

def block(x: float, w: float, top: float, base: float = GROUND) -> str:
    """A rectangle from `top` down to `base`. Every shape is drawn clockwise so
    overlapping shapes in one path merge cleanly (nonzero fill rule)."""
    return f"M{x:.0f} {base:.0f}V{top:.0f}H{x + w:.0f}V{base:.0f}Z"


def slanted(x: float, w: float, top: float, drop: float) -> str:
    """A tower whose roof slopes down from right to left by `drop`."""
    return f"M{x:.0f} {GROUND}V{top + drop:.0f}L{x + w:.0f} {top:.0f}V{GROUND}Z"


def building(rng: random.Random, x: float, w: float, top: float, extras: float) -> list[str]:
    """One building: the main block plus, at random, a setback storey, an antenna
    or small rooftop boxes. `extras` scales how often those details appear."""
    parts = []
    if rng.random() < 0.15 * extras:
        parts.append(slanted(x, w, top, rng.uniform(10, 25)))
    else:
        parts.append(block(x, w, top))
    if rng.random() < 0.45 * extras and w > 30:                 # setback (narrower top floors)
        inset = w * rng.uniform(0.15, 0.3)
        step = rng.uniform(10, 30)
        parts.append(block(x + inset, w - 2 * inset, top - step, top + 1))
        top -= step
    if rng.random() < 0.3 * extras:                             # antenna
        parts.append(block(x + w / 2 - 1, 2, top - rng.uniform(15, 35), top + 1))
    elif rng.random() < 0.4 * extras:                           # rooftop boxes
        parts.append(block(x + w * 0.15, w * 0.25, top - 6, top + 1))
    return parts


def row(rng: random.Random, tops: tuple[float, float], widths: tuple[float, float],
        gaps: tuple[float, float], extras: float, skip: tuple[float, float] | None = None,
        low: tuple[float, float, float] | None = None) -> list[str]:
    """A row of buildings across the full width.

    skip: an x range left empty (room for a landmark).
    low:  (x0, x1, min_top) - buildings in that x range stay at or below min_top,
          so the Ferris wheel stays visible behind them.
    """
    parts: list[str] = []
    x = -20.0
    while x < WIDTH:
        w = rng.uniform(*widths)
        top = rng.uniform(*tops)
        if skip and skip[0] < x + w and x < skip[1]:
            x = skip[1] + rng.uniform(*gaps)
            continue
        if low and low[0] < x + w and x < low[1]:
            top = max(top, low[2])
        parts += building(rng, x, w, top, extras)
        x += w + rng.uniform(*gaps)
    return parts


# ---- Landmarks ----------------------------------------------------------------------

def cn_tower(x: float) -> list[str]:
    """CN Tower silhouette: tapering shaft, main pod, sky pod and spire."""
    return [
        f"M{x - 13} {GROUND}L{x - 4} 118H{x + 4}L{x + 13} {GROUND}Z",   # shaft
        f"M{x - 18} 120L{x - 14} 104H{x + 14}L{x + 18} 120Z",            # main pod
        block(x - 5, 10, 78, 106),                                        # upper shaft
        block(x - 7, 14, 70, 80),                                         # sky pod
        f"M{x - 2} 72L{x} 12L{x + 2} 72Z",                                # spire
    ]


def ferris_wheel(cx: float, cy: float, r: float) -> str:
    """Ferris wheel drawn with strokes: rim, spokes, hub, cabins and A-frame legs."""
    import math
    spokes = " ".join(
        f"M{cx:.0f} {cy:.0f}L{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}"
        for a in (i * math.pi / 8 for i in range(16))
    )
    cabins = "".join(
        f'<circle cx="{cx + r * math.cos(a):.1f}" cy="{cy + r * math.sin(a):.1f}" r="4"/>'
        for a in (i * math.pi / 8 + math.pi / 16 for i in range(16))
    )
    return (
        f'<g class="wheel">'
        f'<circle class="rim" cx="{cx}" cy="{cy}" r="{r}"/>'
        f'<path class="spokes" d="{spokes}"/>'
        f'<path class="legs" d="M{cx - 32} {GROUND}L{cx} {cy}L{cx + 32} {GROUND}"/>'
        f'<g class="cabins">{cabins}<circle cx="{cx}" cy="{cy}" r="6"/></g>'
        f"</g>"
    )


# ---- Assemble -----------------------------------------------------------------------

def main() -> None:
    """Build the three layers and write the SVG file."""
    rng = random.Random(SEED)
    far = row(rng, tops=(55, 160), widths=(45, 100), gaps=(10, 70), extras=1.0,
              skip=(CN_TOWER_X - 30, CN_TOWER_X + 30)) + cn_tower(CN_TOWER_X)
    mid = row(rng, tops=(125, 205), widths=(35, 90), gaps=(0, 40), extras=1.0,
              skip=(CN_TOWER_X - 20, CN_TOWER_X + 20),
              low=(WHEEL_X - WHEEL_R - 10, WHEEL_X + WHEEL_R + 10, 215))
    near = row(rng, tops=(185, 258), widths=(25, 75), gaps=(0, 6), extras=0.8,
               low=(WHEEL_X - WHEEL_R, WHEEL_X + WHEEL_R, 245))
    near.append(block(0, WIDTH, GROUND - 10))                   # podium strip along the ground

    svg = f"""<svg class="skyline" viewBox="0 0 {WIDTH} {HEIGHT}" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
  <!-- Generated by scripts/draw_skyline.py - edit that script, not this file. -->
  <defs>
    <!-- Reflection fades out downwards -->
    <linearGradient id="skyline-fade" x1="0" y1="{GROUND}" x2="0" y2="{HEIGHT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#fff" stop-opacity="0.3"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <mask id="skyline-mask" maskUnits="userSpaceOnUse" x="0" y="{GROUND}" width="{WIDTH}" height="{HEIGHT - GROUND}">
      <rect x="0" y="{GROUND}" width="{WIDTH}" height="{HEIGHT - GROUND}" fill="url(#skyline-fade)"/>
    </mask>
  </defs>
  <g id="skyline-city">
    <path class="far" d="{''.join(far)}"/>
    <path class="mid" d="{''.join(mid)}"/>
    {ferris_wheel(WHEEL_X, WHEEL_Y, WHEEL_R)}
    <path class="near" d="{''.join(near)}"/>
  </g>
  <!-- Mirror image below the ground line. The mask sits on a wrapper group so it
       is not flipped along with the copy. -->
  <g mask="url(#skyline-mask)">
    <use href="#skyline-city" transform="matrix(1 0 0 -1 0 {2 * GROUND})"/>
  </g>
</svg>
"""
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
