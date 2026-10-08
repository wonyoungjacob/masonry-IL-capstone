"""Plain-text dump of the revised KICEM paper (abstract, body, references) for pasting into the HWP template."""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kicem_e as KE
import paper_text_kicem_e as PT


class T:                         # stands in for a Paragraph: keeps text and style name
    def __init__(self, text, style="body"):
        self.text, self.style = text, style


R = json.load(open(KE.FIG / "summary_nominal.json"))
t = PT.text(R, T)
nofig = {k: (lambda k=k: T(f"[{k}]", "fig")) for k in ("flow_figure", "t_ks", "t_levels", "task_figure", "t_res", "level_figure", "bin_figure", "t_shape")}
names = {"flow_figure": "그림 1", "t_ks": "표 1", "t_levels": "표 2", "task_figure": "그림 2", "t_res": "표 3", "level_figure": "그림 3",
         "bin_figure": "그림 4", "t_shape": "표 4"}
caps = {}
for blk in (KE.OUTDIR / "그림표" / "캡션.txt").read_text(encoding="utf-8").split("\n"):
    if blk.startswith(("그림", "표")):
        cur = blk.split(".")[0]; caps[cur] = "캡션: " + blk
    elif blk.strip() and caps:
        caps[cur] += " / 각주: " + blk.strip()
lines = [KE.TITLE, KE.SUB, KE.ETITLE, KE.ESUB, "", "요 약", t["abstract"], "키워드: " + KE.KEYWORDS, ""]
for f in t["flow"](nofig):
    if f.style == "fig":
        nm = names[f.text.strip('[]')]
        lines.append(f"[{nm} 위치] " + caps.get(nm, ""))
    elif f.style in ("h1", "h2", "h3"):
        lines += ["", f.text]
    else:
        lines.append(re.sub(r"<[^>]+>", "", f.text))
lines += ["", "참고문헌"] + t["refs"]
out = KE.OUTDIR / "본문텍스트_수정본.txt"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out)
