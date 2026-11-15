#!/usr/bin/env python3
"""Render the animated SVG cards for the GitHub profile README.

Reads config.json and data/contributions.json, writes cards/*.svg.
Every card is shown through an <img> tag, so it only uses what works there:
an inline <style> with CSS keyframes, SMIL, and fonts embedded as base64 WOFF2.

    python scripts/render_readme_cards.py            # animated cards
    STATIC=1 python scripts/render_readme_cards.py   # final frame only, for screenshots
"""
import base64
import calendar
import datetime as dt
import json
import os
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
DATA = json.loads((ROOT / "data" / "contributions.json").read_text())
STATIC = os.environ.get("STATIC") == "1"
C = CFG["colors"]
OUT = ROOT / "cards"
OUT.mkdir(exist_ok=True)

# Timeline (seconds after load). Each card is its own <img>, so they all start
# together; staggering the delays makes the page play top to bottom.
T_HERO, T_GRAPH, T_ACTIVITY, T_TILES, T_REPOS = 0.0, 0.9, 1.7, 2.5, 3.3

LANG_COLORS = {"Python": "#3572A5", "TypeScript": "#3178C6", "JavaScript": "#F1E05A",
               "HTML": "#E34C26", "Java": "#B07219", "Jupyter Notebook": "#DA5B0B"}

# --------------------------------------------------------------------------- fonts
FONTS = {
    "serif": ("JG Serif", "serif-400.woff2", "normal", 400),
    "serif-i": ("JG Serif", "serif-400i.woff2", "italic", 400),
    "mono": ("JG Mono", "mono-500.woff2", "normal", 500),
    "sans": ("JG Sans", "sans-400.woff2", "normal", 400),
    "sans-b": ("JG Sans", "sans-600.woff2", "normal", 600),
}


@lru_cache(None)
def _b64(name):
    return base64.b64encode((ROOT / "fonts" / name).read_bytes()).decode()


def font_css(*keys):
    out = []
    for k in keys:
        fam, file, style, weight = FONTS[k]
        out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
                   f"src:url(data:font/woff2;base64,{_b64(file)}) format('woff2')}}")
    return "".join(out)


SERIF = "font-family:'JG Serif',Georgia,serif"
MONO = "font-family:'JG Mono',ui-monospace,monospace"
SANS = "font-family:'JG Sans',system-ui,sans-serif"

# --------------------------------------------------------------------------- animation
KEYFRAMES = """
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(0)}70%{opacity:1;transform:scale(1.3)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes swing{0%{opacity:0;transform:translateY(70px) rotate(-8deg)}55%{opacity:1;transform:translateY(-9px) rotate(1.5deg)}78%{transform:translateY(3px) rotate(-.6deg)}100%{opacity:1;transform:none}}
@keyframes ring{0%{opacity:.8;transform:scale(1)}100%{opacity:0;transform:scale(4)}}
@keyframes nudge{0%,72%,100%{transform:none}82%{transform:translate(3px,-3px)}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
@keyframes sweep{0%{transform:translateX(0) skewX(-18deg)}22%,100%{transform:translateX(560px) skewX(-18deg)}}
@keyframes draw{from{stroke-dashoffset:200}to{stroke-dashoffset:0}}
@keyframes au1{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(140px,30px) scale(1.15)}66%{transform:translate(60px,-40px) scale(.9)}}
@keyframes au2{0%,100%{transform:translate(0,0) scale(1)}40%{transform:translate(-120px,-60px) scale(1.2)}75%{transform:translate(90px,-20px) scale(.95)}}
@keyframes au3{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(220px,-90px) scale(1.25)}}
.a{transform-box:fill-box;transform-origin:center}
.gb{transform-origin:50% 100%}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.motion,.cf{display:none!important}.cfinal{visibility:visible!important}}
"""


def anim(name, dur, delay, ease="cubic-bezier(.2,.8,.2,1)", extra="both"):
    """Inline animation style; nothing in STATIC mode (elements sit at their end state)."""
    if STATIC:
        return ""
    return f' style="animation:{name} {dur}s {ease} {delay:.3f}s {extra}"'


def loop(name, dur, delay=0.0, ease="ease-in-out"):
    if STATIC:
        return ""
    return f' style="animation:{name} {dur}s {ease} {delay:.3f}s infinite both"'


def svg(w, h, body, fonts, defs="", label=""):
    style = font_css(*fonts) + ("" if STATIC else KEYFRAMES)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(label)}"><style>{style}</style><defs>{defs}</defs>{body}</svg>')


def frame(w, h, rx=18):
    return f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="{C["card"]}" stroke="{C["line"]}"/>'


def text(x, y, s, size, font, fill, extra=""):
    return f'<text x="{x}" y="{y}" style="{font};font-size:{size}px" fill="{fill}" {extra}>{escape(str(s))}</text>'


def wrap(s, n):
    lines, cur = [], ""
    for word in s.split():
        if len(cur) + len(word) + (1 if cur else 0) > n:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    return lines + ([cur] if cur else [])


# --------------------------------------------------------------------------- stats
def stats():
    days = [(dt.date.fromisoformat(d["date"]), int(d["count"])) for d in DATA["days"]]
    total = sum(c for _, c in days)
    active = sum(1 for _, c in days if c)
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    for i, (_, c) in enumerate(reversed(days)):
        if c:
            current += 1
        elif i > 0:  # today with zero doesn't break the streak yet
            break
    busiest = max(days, key=lambda x: x[1])
    last = days[-1][0]
    months = []
    y, m = last.year, last.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    per = {k: 0 for k in months}
    for d, c in days:
        if (d.year, d.month) in per:
            per[(d.year, d.month)] += c
    return dict(days=days, total=total, active=active, longest=longest, current=current,
                busiest=busiest, months=[(k, per[k]) for k in months])


S = stats()

# --------------------------------------------------------------------------- hero
def hero():
    W, H = 1000, 300
    defs = (f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            f'<circle cx="1" cy="1" r="1" fill="{C["faint"]}" opacity=".35"/></pattern>'
            f'<linearGradient id="fadeR" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".55" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>'
            f'<mask id="dotmask"><rect width="{W}" height="{H}" fill="url(#fadeR)"/></mask>'
            f'<linearGradient id="shine" gradientUnits="objectBoundingBox" x1="0" x2="1">'
            f'<stop offset="0" stop-color="{C["blue"]}" stop-opacity="0"/>'
            f'<stop offset=".45" stop-color="{C["blue"]}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#BFD3FF" stop-opacity="1"/>'
            f'<stop offset=".55" stop-color="{C["blue"]}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{C["blue"]}" stop-opacity="0"/>'
            + ('' if STATIC else '<animateTransform attributeName="gradientTransform" type="translate" '
               'values="-1 0;1 0;1 0" keyTimes="0;.3;1" dur="5s" begin="1.6s" repeatCount="indefinite"/>')
            + '</linearGradient>'
            # aurora: soft radial blobs that drift slowly behind the name
            + ''.join(f'<radialGradient id="au{k}"><stop offset="0" stop-color="{C[col]}" stop-opacity="{op}"/>'
                      f'<stop offset=".45" stop-color="{C[col]}" stop-opacity="{op * .4:.3f}"/>'
                      f'<stop offset="1" stop-color="{C[col]}" stop-opacity="0"/></radialGradient>'
                      for k, col, op in ((1, "blue", .30), (2, "coral", .22), (3, "mint", .12)))
            + f'<clipPath id="cardclip"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17"/></clipPath>')
    blobs = [  # (gradient, cx, cy, rx, ry, keyframes, seconds, delay)
        (1, 230, 150, 330, 170, "au1", 18, 0),
        (2, 560, 220, 320, 150, "au2", 23, -6),
        (3, 120, 280, 240, 120, "au3", 29, -11),
    ]
    aurora = "".join(
        f'<g class="a"{loop(kf, dur, delay)}><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#au{g})"/></g>'
        for g, cx, cy, rx, ry, kf, dur, delay in blobs)
    b = [frame(W, H),
         f'<g clip-path="url(#cardclip)"><g{anim("fade", 2.4, T_HERO + .3, "ease-out")}>{aurora}</g></g>',
         f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17" fill="url(#dots)" mask="url(#dotmask)"/>']

    b.append(f'<g class="a"{anim("rise", .6, T_HERO)}>{text(48, 64, CFG["handle"], 13, MONO, C["muted"])}</g>')
    b.append(f'<g class="a"{anim("rise", .8, T_HERO + .15)}>{text(42, 158, CFG["name_first"], 96, SERIF, C["ink"], "letter-spacing=\"-2\"")}</g>')
    last = text(42, 244, CFG["name_last"], 96, SERIF, C["ink"], 'font-style="italic" letter-spacing="-1"')
    shine = text(42, 244, CFG["name_last"], 96, SERIF, "url(#shine)", 'font-style="italic" letter-spacing="-1" class="motion"')
    b.append(f'<g class="a"{anim("rise", .8, T_HERO + .35)}>{last}{"" if STATIC else shine}</g>')
    return svg(W, H, "".join(b), ["serif", "serif-i", "mono"], defs,
               f'{CFG["name_first"]} {CFG["name_last"]}')


# --------------------------------------------------------------------------- contribution graph
def graph():
    W, H = 1000, 236
    days = S["days"]
    mx = max([c for _, c in days] + [1])
    shades = ["#161C27", "#1E3A78", "#2E5BC9", C["blue"], "#AFC7FF"]

    def level(c):
        if c == 0:
            return 0
        return 1 if mx == 1 else min(4, 1 + round(3 * (c - 1) / (mx - 1)))

    x0, y0, step, size = 66, 86, 17, 13
    b = [frame(W, H)]
    b.append(f'<g class="a"{anim("rise", .6, T_GRAPH)}>'
             + text(32, 42, "CONTRIBUTIONS · LAST 12 MONTHS", 12, MONO, C["muted"], 'letter-spacing="1"')
             + text(968, 43, f'{S["total"]} contributions', 15, SANS, C["ink"], 'text-anchor="end" font-weight="600"')
             + '</g>')
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(f'<g class="a"{anim("fade", .5, T_GRAPH + .2)}>{text(32, y0 + r*step + 10, lab, 10, MONO, C["faint"])}</g>')
    last_label = -9
    for i, (d, c) in enumerate(days):
        col, row = divmod(i, 7)
        x, y = x0 + col * step, y0 + row * step
        if d.day == 1 and col - last_label > 2:
            last_label = col
            b.append(f'<g class="a"{anim("fade", .5, T_GRAPH + .2)}>'
                     f'{text(x, y0 - 10, calendar.month_abbr[d.month], 10, MONO, C["faint"])}</g>')
        b.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="3" fill="{shades[level(c)]}" class="a"'
                 f'{anim("pop", .35, T_GRAPH + .3 + col*.02 + row*.012)}><title>{d.isoformat()}: {c}</title></rect>')
    lx = 968 - 5 * step - 34
    leg = text(lx - 8, 222, "less", 10, MONO, C["faint"], 'text-anchor="end"')
    for k in range(5):
        leg += f'<rect x="{lx + k*step}" y="{212}" width="{size}" height="{size}" rx="3" fill="{shades[k]}"/>'
    leg += text(lx + 5 * step + 4, 222, "more", 10, MONO, C["faint"])
    b.append(f'<g class="a"{anim("fade", .5, T_GRAPH + 1.4)}>{leg}</g>')
    return svg(W, H, "".join(b), ["mono", "sans-b"], label=f'{S["total"]} contributions in the last year')


# --------------------------------------------------------------------------- monthly activity
def activity():
    W, H = 1000, 280
    months = S["months"]
    best_i = max(range(len(months)), key=lambda i: (months[i][1], i))  # ties: most recent
    mx = max(months[best_i][1], 1)
    base, maxh, bx, bw, bstep = 226, 132, 40, 30, 46
    b = [frame(W, H)]
    b.append(f'<g class="a"{anim("rise", .6, T_ACTIVITY)}>{text(32, 42, "MONTHLY ACTIVITY", 12, MONO, C["muted"], "letter-spacing=\"1\"")}</g>')
    b.append(f'<g class="a"{anim("fade", .5, T_ACTIVITY + .1)}><line x1="{bx - 8}" x2="{bx + 11*bstep + bw + 8}" y1="{base + .5}" y2="{base + .5}" stroke="{C["line"]}"/>'
             f'<line x1="618" x2="618" y1="70" y2="244" stroke="{C["line"]}"/></g>')
    for i, ((y, m), c) in enumerate(months):
        x = bx + i * bstep
        h = max(3, maxh * c / mx) if c else 3
        fill = C["blue"] if (i == best_i and c) else ("#2A3345" if c else "#1A202C")
        b.append(f'<rect x="{x}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="{fill}" class="a gb"'
                 f'{anim("grow", .7, T_ACTIVITY + .2 + i*.06)}><title>{calendar.month_abbr[m]} {y}: {c}</title></rect>')
        b.append(f'<g class="a"{anim("fade", .4, T_ACTIVITY + .2 + i*.06)}>'
                 + text(x + bw/2, base + 22, calendar.month_abbr[m], 11, MONO,
                        C["ink"] if i == best_i else C["faint"], 'text-anchor="middle"') + '</g>')
        if c and i != best_i:
            b.append(f'<g class="a"{anim("fade", .4, T_ACTIVITY + .9 + i*.06)}>'
                     f'{text(x + bw/2, base - h - 8, c, 11, MONO, C["muted"], "text-anchor=\"middle\"")}</g>')
    if months[best_i][1]:
        x = bx + best_i * bstep
        b.append(f'<g class="a"{anim("pop", .5, T_ACTIVITY + 1.1)}>'
                 f'{text(x + bw/2, base - maxh - 12, months[best_i][1], 26, SERIF, C["ink"], "text-anchor=\"middle\"")}</g>')

    bd, bc = S["busiest"]
    items = [("TOTAL", str(S["total"])), ("ACTIVE DAYS", str(S["active"])),
             ("LONGEST STREAK", f'{S["longest"]} day{"s" if S["longest"] != 1 else ""}'),
             ("BUSIEST DAY", f'{bd.strftime("%b")} {bd.day}' if bc else "-")]
    for i, (lab, val) in enumerate(items):
        x, y = 656 + (i % 2) * 170, 100 + (i // 2) * 92
        sub = text(x, y + 62, f"{bc} contributions", 11, MONO, C["muted"]) if lab == "BUSIEST DAY" and bc else ""
        b.append(f'<g class="a"{anim("rise", .6, T_ACTIVITY + .5 + i*.1)}>'
                 f'{text(x, y, lab, 11, MONO, C["muted"], "letter-spacing=\"1\"")}'
                 f'{text(x - 2, y + 42, val, 38, SERIF, C["ink"])}{sub}</g>')
    return svg(W, H, "".join(b), ["serif", "mono"], label="Monthly contributions and streak stats")


# --------------------------------------------------------------------------- tiles
def tile(t, i):
    W, H = 330, 220
    col = C[t["color"]]
    delay = T_TILES + i * .18
    defs = (f'<clipPath id="clip"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="15"/></clipPath>'
            f'<radialGradient id="glow" cx="1" cy="0" r="1"><stop offset="0" stop-color="{col}" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="gl" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".09"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    inner = [frame(W, H, 16), f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="15" fill="url(#glow)"/>',
             f'<rect x="24" y="1" width="46" height="3" rx="1.5" fill="{col}"/>',
             text(26, 44, t["label"], 13, MONO, col, 'letter-spacing="2"'),
             f'<g class="a"{loop("nudge", 2.6, delay + 1)}>{text(304, 46, "↗", 18, SANS, col, "text-anchor=\"end\"")}</g>']

    v, suf = int(t["value"]), t.get("suffix", "")
    num = lambda s, extra="": text(22, 136, s, 80, SERIF, C["ink"], f'letter-spacing="-2" {extra}')
    if STATIC:
        inner.append(num(f"{v}{suf}"))
    else:
        n, start, fs = 18, delay + .45, .045
        vals = [round(v * (1 - (1 - k / (n - 1)) ** 3)) for k in range(n)]
        for k, val in enumerate(vals[:-1]):
            inner.append(num(f"{val}{suf}", f'class="cf" visibility="hidden"').replace(
                "</text>", f'<set attributeName="visibility" to="visible" begin="{start + k*fs:.3f}s" dur="{fs}s"/></text>'))
        inner.append(num(f"{v}{suf}", 'class="cfinal" visibility="hidden"').replace(
            "</text>", f'<set attributeName="visibility" to="visible" begin="{start + (n-1)*fs:.3f}s" fill="freeze"/></text>'))

    for j, line in enumerate(t["caption"]):
        inner.append(text(26, 172 + j * 21, line, 14, SANS, C["muted"]))
    inner.append(f'<circle cx="300" cy="190" r="4" fill="{col}"/>')
    inner.append(f'<circle cx="300" cy="190" r="4" fill="none" stroke="{col}" stroke-width="1.5" class="a motion"'
                 f'{loop("ring", 2.4, delay + 1.2, "ease-out")}/>')
    if not STATIC:
        inner.append(f'<g clip-path="url(#clip)" class="motion"><rect x="-140" y="-20" width="90" height="{H+40}" '
                     f'fill="url(#gl)" style="animation:sweep 7s ease-in-out {delay + 1.6 + i*.7:.2f}s infinite both"/></g>')
    body = f'<g class="a"{anim("swing", 1.0, delay)}>{"".join(inner)}</g>'
    return svg(W, H, body, ["serif", "mono", "sans"], defs, f'{t["label"]}: {v}{suf} {" ".join(t["caption"])}')


# --------------------------------------------------------------------------- repo cards
def repo(r, i):
    W, H = 490, 150
    delay = T_REPOS + i * .12
    lang_col = LANG_COLORS.get(r["lang"], C["muted"])
    lines = wrap(r["desc"], 58)[:2]
    b = [frame(W, H, 14),
         f'<rect x="1" y="20" width="3" height="34" rx="1.5" fill="{lang_col}"/>',
         text(24, 46, r["title"], 15, MONO, C["ink"]),
         f'<g class="a"{loop("nudge", 2.6, delay + 1.2)}>{text(466, 47, "↗", 16, SANS, C["muted"], "text-anchor=\"end\"")}</g>']
    for j, line in enumerate(lines):
        b.append(text(24, 80 + j * 21, line, 14, SANS, C["muted"]))
    b.append(f'<circle cx="30" cy="{H - 26}" r="5" fill="{lang_col}"/>')
    b.append(text(42, H - 21, r["lang"], 12, SANS, C["muted"]))
    body = f'<g class="a"{anim("rise", .7, delay)}>{"".join(b)}</g>'
    return svg(W, H, body, ["mono", "sans"], label=f'{r["title"]}: {r["desc"]}')


# --------------------------------------------------------------------------- main
def main():
    files = {"hero.svg": hero(), "graph.svg": graph(), "activity.svg": activity()}
    for i, t in enumerate(CFG["tiles"]):
        files[f'{t["key"]}.svg'] = tile(t, i)
    for i, r in enumerate(CFG["repos"]):
        files[f"repo-{i+1}.svg"] = repo(r, i)
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"cards/{name:14s} {len(content)/1024:6.1f} KB")


if __name__ == "__main__":
    main()
