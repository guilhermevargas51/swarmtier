"""Gera os projetos HyperFrames dos banners e renderiza (1 s) -> PNG via ffmpeg.
Uso: python build_banners.py   (rodar de qualquer pasta)"""
import os, pathlib, shutil, subprocess

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent
HF = os.environ["HF_CMD"]  # path to the hyperframes CLI wrapper
GSAP = pathlib.Path(os.environ["GSAP_JS"])  # path to a local gsap.min.js

THEMES = {
    "dark": dict(bg="#0d1117", fg="#f0f6fc", sub="#9da7b3"),
    "light": dict(bg="#ffffff", fg="#0d1117", sub="#57606a"),
}
VIOLET, AMBER, TEAL = "#a78bfa", "#f59e0b", "#2dd4bf"


def pyramid(s):
    def blk(w, h, c):
        return f'<div style="width:{w*s:.0f}px;height:{h*s:.0f}px;background:{c};border-radius:{5*s:.0f}px"></div>'
    r1 = blk(150, 44, VIOLET)
    r2 = "".join(blk(112, 34, AMBER) for _ in range(3))
    r3 = "".join(blk(34, 26, TEAL) for _ in range(10))
    row = lambda inner, gap: (f'<div style="display:flex;justify-content:center;gap:{gap*s:.0f}px">{inner}</div>')
    return (f'<div style="display:flex;flex-direction:column;gap:{16*s:.0f}px;width:{412*s:.0f}px">'
            f'{row(r1, 0)}{row(r2, 10)}{row(r3, 6)}</div>')


def page(theme, w, h, s, lines, title_px, tag_px, footer):
    t = THEMES[theme]
    tag = "<br>".join(lines)
    foot = (f'<div style="position:absolute;left:72px;bottom:34px;font-size:22px;color:{t["sub"]};'
            f'font-family:Consolas,\'Courier New\',monospace">{footer}</div>') if footer else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width={w}, height={h}"/>
<script src="gsap.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{t['bg']}}}
#root{{position:relative;width:{w}px;height:{h}px;background:{t['bg']};display:flex;align-items:center;
justify-content:space-between;padding:0 72px;font-family:'Segoe UI',Arial,Helvetica,sans-serif}}
h1{{font-size:{title_px}px;font-weight:800;letter-spacing:-2px;color:{t['fg']};line-height:1}}
p{{font-size:{tag_px}px;color:{t['sub']};line-height:1.3;margin-top:{18*s:.0f}px;font-weight:500}}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="1" data-width="{w}" data-height="{h}">
<div><h1>swarmtier</h1><p>{tag}</p></div>
{pyramid(s)}
{foot}
</div>
<script>
const tl = gsap.timeline({{paused:true}});
tl.to("#root",{{opacity:1,duration:1}},0);
window.__timelines["main"] = tl; tl.seek(0);
</script></body></html>"""


JOBS = [
    ("banner-dark", "dark", 1280, 320, 0.8, ["Your Opus plans. Haiku does the volume.", "Your quota lasts the week."], 88, 27, None),
    ("banner-light", "light", 1280, 320, 0.8, ["Your Opus plans. Haiku does the volume.", "Your quota lasts the week."], 88, 27, None),
    ("social-preview", "dark", 1280, 640, 1.15,
     ["Your Opus plans.", "Haiku does the volume.", "Your quota lasts the week."], 112, 34, "Claude Code plugin · MIT"),
]

for name, theme, w, h, s, lines, tpx, gpx, footer in JOBS:
    d = HERE / name
    d.mkdir(exist_ok=True)
    shutil.copy(GSAP, d / "gsap.min.js")
    (d / "index.html").write_text(page(theme, w, h, s, lines, tpx, gpx, footer), encoding="utf-8")
    mp4 = d / "out.mp4"
    subprocess.run([HF, "render", str(d), "--format", "mp4", "-o", str(mp4), "--quiet"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(mp4), "-frames:v", "1",
                    str(ASSETS / f"{name}.png")], check=True)
    print("ok", name)
