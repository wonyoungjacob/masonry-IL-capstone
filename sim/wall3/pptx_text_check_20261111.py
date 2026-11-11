"""두 pptx의 슬라이드 글이 같은지 본다 (2026-11-11). 양식만 다듬은 새 판이 내용을 바꾸지 않았는지 점검하는 도구.

- 글: 슬라이드 XML의 문단(a:p)마다 a:t를 이어 붙인 문자열. 공백은 모두 빼고 비교한다(줄바꿈 · 띄어쓰기는 형식이므로).
- 문단이 어느 도형에 있는지, 어떤 순서인지는 보지 않는다(배치를 바꾸면 달라진다). 사라진 문단과 새로 생긴 문단만 센다.
- 숫자: 글 전체에서 숫자(부호 포함, 예: 60, –37, 13.65)를 모아 묶음으로 비교한다. 문단을 나누거나 합쳐도 숫자 묶음은 같아야 한다.
- 볼 수 없는 것: 그림(PNG) 안의 글자, 글자 크기 · 색 · 위치. --media를 주면 넣은 그림 파일의 sha256 묶음도 비교한다(참고용).
- 표준 라이브러리만 쓴다. 두 파일을 읽기만 한다.

실행: cd sim && PYTHONPATH=. python -m wall3.pptx_text_check_20261111 <기준.pptx> <새.pptx> [--media]
끝 코드: 0 = 글 같음 · 숫자 같음, 1 = 다름
"""
import argparse, hashlib, re, sys, zipfile
from collections import Counter
from xml.etree import ElementTree as ET

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NUM = re.compile(r"[–−+\-]?\d+(?:\.\d+)?")


def norm(s):
    return "".join(s.split())


def slide_names(z):
    key = lambda n: int(re.search(r"(\d+)\.xml$", n).group(1))
    return sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=key)


def paragraphs(pptx):
    """모든 슬라이드의 문단 글(공백 뺀 것, 빈 문단 제외)을 문서 순서대로."""
    out = []
    with zipfile.ZipFile(pptx) as z:
        for name in slide_names(z):
            for p in ET.fromstring(z.read(name)).iter(A + "p"):
                t = norm("".join(x.text or "" for x in p.iter(A + "t")))
                if t:
                    out.append(t)
    return out


def numbers(paras):
    return Counter(n for p in paras for n in NUM.findall(p))


def media(pptx):
    with zipfile.ZipFile(pptx) as z:
        return Counter(hashlib.sha256(z.read(n)).hexdigest()[:16] for n in z.namelist() if n.startswith("ppt/media/"))


def diff(pa, pb):
    """(기준에만 있는 문단, 새 판에만 있는 문단, 기준에만 있는 숫자, 새 판에만 있는 숫자). 같은 문단이 여러 번이면 횟수까지 센다."""
    ca, cb = Counter(pa), Counter(pb)
    gone = [p for p in dict.fromkeys(pa) for _ in range((ca - cb)[p])]
    new = [p for p in dict.fromkeys(pb) for _ in range((cb - ca)[p])]
    na, nb = numbers(pa), numbers(pb)
    return gone, new, na - nb, nb - na


def main():
    ap = argparse.ArgumentParser(description="두 pptx의 슬라이드 글 · 숫자를 비교한다")
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--media", action="store_true", help="넣은 그림 파일의 sha256 묶음도 비교한다")
    a = ap.parse_args()
    pa, pb = paragraphs(a.base), paragraphs(a.new)
    gone, new, ngone, nnew = diff(pa, pb)
    print(f"기준: {a.base} (문단 {len(pa)}개)")
    print(f"새 판: {a.new} (문단 {len(pb)}개)")
    for title, items in (("기준에만 있는 문단", gone), ("새 판에만 있는 문단", new)):
        if items:
            print(f"\n[{title}] {len(items)}개")
            for p in items:
                print("  -", p if len(p) <= 150 else p[:150] + " …")
    for title, c in (("기준에만 있는 숫자", ngone), ("새 판에만 있는 숫자", nnew)):
        if c:
            print(f"\n[{title}] " + ", ".join(f"{k} × {v}" if v > 1 else k for k, v in sorted(c.items())))
    if a.media:
        ma, mb = media(a.base), media(a.new)
        print(f"\n그림 파일: 기준 {sum(ma.values())}개 · 새 판 {sum(mb.values())}개 · 같은 파일 {sum((ma & mb).values())}개")
    same_text, same_num = not gone and not new, not ngone and not nnew
    print(f"\n결과: 글 {'같음' if same_text else '다름'} · 숫자 {'같음' if same_num else '다름'}"
          " (그림 안의 글자와 글자 크기 · 색 · 위치는 보지 않음)")
    sys.exit(0 if same_text and same_num else 1)


if __name__ == "__main__":
    main()
