"""Gera assets/cost-chart.svg (numeros de docs/cost-map.md, secao 'work per unit of quota')."""
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "cost-chart.svg"
GREY = "#8b949e"
ROWS = [("Opus", 1, "#a78bfa", "1x"), ("Sonnet", 2, "#f59e0b", "about 2x"),
        ("Haiku, context above 100k", 5.5, "#2dd4bf", "about 5.5x"),
        ("Haiku, context up to 100k", 27, "#2dd4bf", "about 27x")]
W, H, X0, MAXW, BH = 800, 360, 250, 430, 40
p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
     f'aria-label="Work per unit of quota, relative to Opus = 1x">',
     f'<text x="{W/2}" y="34" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="20" '
     f'font-weight="700" fill="{GREY}">Work per unit of quota, relative to Opus = 1x</text>']
for i, (name, v, c, label) in enumerate(ROWS):
    y = 70 + i * 55
    w = max(4, MAXW * v / 27)
    p.append(f'<text x="{X0-14}" y="{y+BH*0.64}" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" '
             f'font-size="16" fill="{GREY}">{name}</text>')
    p.append(f'<rect x="{X0}" y="{y}" width="{w:.1f}" height="{BH}" rx="5" fill="{c}"/>')
    p.append(f'<text x="{X0+w+10:.1f}" y="{y+BH*0.64}" font-family="Consolas,Courier New,monospace" '
             f'font-size="16" font-weight="700" fill="{GREY}">{label}</text>')
p.append(f'<text x="{W/2}" y="{H-22}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="14" '
         f'fill="{GREY}">measured on one account over 30 days — see docs/cost-map.md</text>')
p.append("</svg>")
OUT.write_text("\n".join(p), encoding="utf-8")
print(OUT.stat().st_size)
