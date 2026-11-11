# -*- coding: utf-8 -*-
"""KSARC 포스터 g판: 문장 문체 + 학회 양식 파일의 제목 · 저자 · 그림 · 표 제목 규칙 (2026-11-12, 윈도우 전용: PowerPoint 필요).

사용자 지시(11-12)
- "내용은 좋은데 말투가 처참할 정도로 클로드 냄새가 난다" (예: "이렇게는 알 수 없는 것:", "(효과 없음이 아님)").
  → 숫자 · 내용은 그대로, 문장을 레퍼런스 포스터(ksarc_포스터_v12.pdf) 문체로: 개조식 "~함 / ~임", "• 머리말: 내용",
    학술 용어(기여도 · 유의차 · 신뢰구간 · 대응 비교 · 제거). 그림 1 · 2 · 4 · 5 · 6 속 글자도 같은 문체로 다시 그린다.
- "기본 pptx에 양식 적혀 있잖아. 그림 표나 첫 대제목 양식" → 학회 양식 파일(ksarc-포스터 PPT 양식.pptx)에 적힌 대로:
  국문 제목 48 pt 굵게 · 영문 제목 40 pt · 가운데, 저자 "이름*, 이름*" 32 pt · 영문 이름 32 pt, 소속 "*소속" 한 줄,
  표 제목은 표 위 왼쪽 정렬, 그림 제목은 그림 아래 가운데 정렬.
- 양식 · 배치 함수는 f판 스크립트(poster_restyle_ksarc_20261111f.py)의 restyle · layout을 쓰고, 그 뒤에 제목 · 저자 · 그림/표 제목만 다시 꾸민다.
- e판 · f판 파일은 고치지 않는다. 출력이 이미 있으면 멈춘다.

실행 (저장소 루트, PowerShell):
  $env:PYTHONUTF8 = "1"
  python sim\\wall3\\poster_rewrite_ksarc_20261112g.py --tag 20261112g
"""
import argparse, copy, json, os, re, shutil, sys, tempfile

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM = os.path.join(ROOT, "sim")
if SIM not in sys.path:
    sys.path.insert(0, SIM)
from wall3 import poster_restyle_ksarc_20261111f as F  # noqa: E402

B_, N_ = True, False

# ───────────────────────────── 학회 양식 파일 값
TITLE_KO_PT, TITLE_EN_PT, NAME_PT, NAME_EN_PT, AFFIL_PT = 48, 40, 32, 32, 24
TITLE_KO = "모방학습 조적 로봇의 검측 단계별 효과: 3단 벽체의 완성률과 시방 합격"
AUTHORS_KO = "정원영*, 강현준*, 김홍조*"
AUTHORS_EN = "Jung, Wonyoung, Kang, Hyunjoon, Kim, Hongjo"
AFFIL = "*연세대학교 건설환경공학과"

# ───────────────────────────── 본문 글: 도형 이름 → 문단마다 [(글, 굵게)]
TEXT = {
    "1절 연구 배경": [[("숙련 인력이 감소하는 조적 공사에서 기존 조적 로봇은 현장마다 경로 · 계측 재설정이 필요함[4]. "
                    "대안으로 사람의 시연을 학습하는 모방학습(ACT[1])이 활용됨.", N_)]],
    "1절 문제 정의": [[("성공 시연만 학습한 정책은 실패를 인지하지 못하며, 16장 연속 시공에서는 한 장의 실패로 작업 전체가 중단됨(", N_),
                   ("정책 단독: 벽당 2.0장 · 완성 0벽", B_),
                   ("). 검토한 범위의 선행연구는 검측 단계를 일괄 적용하고 전체 성공률만 보고하여 다음을 판단하기 어려움.", N_)]],
    "1절 빈틈 카드 1": [[("(1)  ", B_), ("한정된 센서 · 시간을 투입할 검측 단계", N_)]],
    "1절 빈틈 카드 2": [[("(2)  ", B_), ("검측이 오히려 역효과를 내는 경우", N_)]],
    "1절 빈틈 카드 3": [[("(3)  ", B_), ("성공률만으로는 알 수 없는 시방 합격 여부", N_)]],
    "1절 연구 목적": [[("동일 정책에서 검측 단계를 하나씩 제거하여 ", N_), ("단계별 벽 완성 · 시방 합격 기여도", B_), ("와 ", N_),
                   ("검측 효과의 발현 조건", B_), ("을 KCS 41 34 00[3] 기준으로 규명함.", N_)]],
    "1절 연구 방법": [[("MuJoCo[2] 3단 16장 벽체에서 ACT 정책(재학습 없음)에 검측 6단계를 적용한 Full과, 한 단계씩 제거한 6개 조건을 비교함.", N_)]],
    "1절 검증 계획": [[("전 조건을 동일 100벽에서 실행하여 벽 단위로 대응 비교함. 차이의 95 % 신뢰구간이 0 미만이면 기여 있음, "
                    "0을 포함하면 유의차 없음으로 판정함.", N_)]],
    "1절 기여 카드 1": [[("(1)  ", B_), ("시방 기준으로 측정한 검측 단계별 기여도", N_)]],
    "1절 기여 카드 2": [[("(2)  ", B_), ("측정 정확도보다 파지 벽돌 식별이 우선한다는 관찰(실패 분석에서 도출한 질문)", N_)]],
    "1절 기여 카드 3": [[("(3)  ", B_), ("현장 검측 자원 배분의 우선순위", N_)]],
    "환경 글": [
        [("환경: ", B_), ("MuJoCo · UR10e + Robotiq 2F-140 · 벽돌 190 × 90 × 57 mm · 3단 16자리(온장 14 · 반장 2) · 줄눈 10 mm", N_)],
        [("공급: ", B_), ("16칸 고정 공급대, 칸 중심 기준 ±10 mm · ±10° 무작위 배치", N_)],
        [("정책: ", B_), ("ACT, 시연 1,000벽 · 10만 스텝 학습 후 고정, 실행 시 정답 좌표 미사용(카메라 3대 · 관절값 · 손목 힘)", N_)],
        [("평가 배치: ", B_), ("전 조건 동일 개발 배치 100벽(시작값 700300 ~ 700399), 최종 평가 전", N_)]],
    "결과 표 각주": [
        [("차이: 조건 – Full (동일 100벽의 완성 벽 수). 95 % 신뢰구간: 벽 단위 부트스트랩 10000회.", N_)],
        [("구간 전체가 0 미만이면 ‘유의한 감소’, 0을 포함하면 ‘유의차 없음’. 참값 (진단): 카메라 대신 정답 좌표를 입력한 진단 조건"
          "(실제 로봇 불가, 실패 분석에서 도출한 탐색 질문으로 사전 기준 없음).", N_)]],
    "고찰 글": [
        [("파지 벽돌 식별 우선: ", B_),
         ("H 제거 시 벽당 1.82장으로 검측 없음(2.00장)보다 낮음. 정책이 한 차례에 여러 장을 집어 차례 번호와 파지 벽돌이 어긋나면 "
          "검측이 잘못된 위치로 보정함. 반면 정답 좌표를 입력해도 완성률 차이 –7 [–19, +4]로 유의하지 않음(실패 분석에서 도출한 질문).", N_)],
        [("단계 간 상호 의존: ", B_),
         ("한 장의 실패로 벽 전체가 중단되므로 G1 · H는 하나만 제거해도 완성 0벽임. 단계별 기여도는 다른 단계가 모두 작동할 때의 값으로, "
          "합산하여 해석하지 않음.", N_)],
        [("G3와 시방 합격: ", B_),
         ("채움 판정이 느슨하여 G3 없이도 23벽이 완성되었으나 시방 합격은 2벽임. 동일 벽 비교 시 선 및 면 +7.3 mm, 수직도 +6.4 mm(대응 19벽).", N_)],
        [("현장 시사점: ", B_),
         ("검측 자원은 (1) 파지 자재 식별(공급 순서 · 공급대 등록), (2) 배치 후 검측 순으로 우선 배분함. "
          "G1 · G2 · G3는 시공 검측(자체 점검 → 보완 → 재검측)에 대응함.", N_)]],
    "결론 글": [
        [("검측 효과: ", B_), ("정책 재학습 없이 검측 6단계로 3단 16장 벽의 완성률 0 → 60 %, 시방 합격률 0 → 60 % 달성.", N_)],
        [("단계별 기여: ", B_), ("G0 · G1 · G2 · G3 · H는 각각 유의한 기여가 있고, G2w는 본 배치 규모에서 유의차 없음. 시방 합격은 G3가 담당함.", N_)],
        [("한계 및 향후 연구: ", B_),
         ("시뮬레이션 · 단일 벽 형상 · 정책 1개 조건이며, Full 구성과 문턱값을 같은 개발 배치에서 정하여 결과가 낙관적일 수 있음. "
          "동일 검측의 Diffusion 정책 적용 시 벽당 2.47장 · 완성 0벽으로 타 정책으로 일반화하지 않음. "
          "놓기 확약(G2c) 추가는 –0.09 [–1.03, +0.85]장으로 유의차가 없어 Full에서 제외함. "
          "독립 시험 배치 · 학습 seed 추가 · 실제 로봇 실험으로 확인 예정.", N_)]],
    "핵심 메시지": [[("정책 재학습 없이, 파지 벽돌 식별 기반 검측 적용으로", B_)],
                [("완성률 0 → 60 % · 시방 합격률 0 → 60 % (100벽)", B_)]],
}

# 표 칸: (표 이름 머리, 줄, 열) → 문단마다 [(글, 굵게)]
CELLS = {
    ("검측 단계 표", 0, 1): [[("기능", B_)]],
    ("검측 단계 표", 0, 2): [[("사용 정보", B_)]],
    ("검측 단계 표", 1, 1): [[("공급칸 하강 시 정책 대신 도면상 칸 중심에서 파지", N_)]],
    ("검측 단계 표", 2, 1): [[("1.5 cm 들어 올려 파지 판정, 실패 시 재시도", N_)]],
    ("검측 단계 표", 3, 1): [[("파지 벽돌을 측정해 설계 위치에 배치", N_)]],
    ("검측 단계 표", 4, 1): [[("G2 개입 거리 확대 (15 → 40 cm)", N_)]],
    ("검측 단계 표", 5, 1): [[("배치된 벽돌을 측정해 어긋나면 재배치", N_)]],
    ("검측 단계 표", 6, 1): [[("파지 시점 최근접 공급칸의 벽돌을 G2 · G3 기준으로 사용", N_)]],
    ("연구 질문 표", 0, 1): [[("비교 (동일 정책 · 동일 100벽)", B_)]],
    ("연구 질문 표", 0, 2): [[("판정 기준", B_)]],
    ("연구 질문 표", 1, 0): [[("RQ1 단계별 기여도", B_)], [("(사전 계획 질문)", B_)]],
    ("연구 질문 표", 1, 1): [[("Full 대 Full – 해당 단계 (6쌍)", N_)]],
    ("연구 질문 표", 1, 2): [[("완성률 대응 차이 95 % 신뢰구간", N_)], [("< 0 이면 기여 있음", N_)]],
    ("연구 질문 표", 2, 0): [[("RQ2 검측 효과의 발현 조건", B_)], [("(실패 분석에서 도출한 질문)", B_)]],
    ("연구 질문 표", 2, 1): [[("Full 대 참값 (진단): 카메라 대신 정답 좌표", N_)], [("Full 대 Full – H: 차례 번호 기준", N_)]],
    ("연구 질문 표", 2, 2): [[("사전 판정 기준 없음", N_)], [("→ 대응 차이만 보고", N_)]],
    ("결과 표", 0, 1): [[("완성 벽", B_)], [("(100벽 중)", B_)]],
    ("결과 표", 0, 2): [[("Full 대비 차이", B_)], [("(완성 벽 수)", B_)]],
    ("결과 표", 0, 3): [[("95 % 신뢰구간", B_)], [("(벽 수)", B_)]],
}
VERDICT = {"몫 있음": "유의한 감소", "구별 못 함": "유의차 없음", "몫 있음 (검측 전체)": "유의한 감소 (검측 전체)",
           "구별 못 함 (탐색)": "유의차 없음 (탐색)"}

# 그림 · 표 제목 (양식 파일: 표 제목은 표 위 왼쪽, 그림 제목은 그림 아래 가운데). 도형 이름 → (번호, 제목)
CAPTIONS = {
    "그림 1 제목": ("그림 1.", "정책 단독과 검측 6단계 적용(Full)의 완성률"),
    "그림 2 제목": ("그림 2.", "벽돌 1장의 작업 순서와 검측 단계"),
    "환경 그림 설명": ("그림 3.", "실험 환경과 카메라 시야 (카메라 형상은 위치 표시용이며, 시뮬레이터 내 카메라는 형상 없음)"),
    "그림 4 제목": ("그림 4.", "평가 기준: 자리 채움 → 벽 완성 → 시방 합격"),
    "그림 5 제목": ("그림 5.", "조건별 자리 채움 벽 수 (조건별 100벽)"),
    "그림 6 제목": ("그림 6.", "Full과 Full – G3의 시방 항목 측정값"),
    "표 1 제목": ("표 1.", "검측 단계별 기능과 사용 정보"),
    "표 2 제목": ("표 2.", "연구 질문과 판정 기준"),
    "표 3 제목": ("표 3.", "검측 단계 제거에 따른 완성 벽 수 차이와 신뢰구간 (동일 100벽 비교)"),
}

# ───────────────────────────── 그림 속 글자 (e판 그림 함수가 쓰는 글 → 새 글)
FIG_EXACT = {
    "검측 단계를 하나만 끄면": "검측 단계 1개 제거 시",
    "G2w는 구별되지 않음": "G2w는 유의차 없음",
    "벽 그림의 색 = 그 자리를 채운 벽 수 (100벽 중, 진할수록 많음)": "벽 그림 색: 자리별 채움 벽 수 (100벽 중, 진할수록 많음)",
    "G1 순간 손 위치(관절값) → 가장 가까운 공급칸 = 어느 벽돌인가\n→ G2 · G3가 맞출 자리 = 그 벽돌의 설계 자리":
        "G1 시점 손 위치(관절값)의 최근접 공급칸 벽돌을 파지 벽돌로 판단\nG2 · G3는 해당 벽돌의 설계 위치를 목표로 보정",
    "정책(ACT) = 학습한 동작\n검측 G = 정책 밖 규칙\n(재학습 없음)": "정책(ACT): 모방학습 동작\n검측(G): 정책 외부 규칙\n(정책 재학습 없음)",
    "설계 자리 중심에서 수평 45 mm, 높이 28.5 mm,\n기울기 45° 안이면 채움 (느슨한 존재 확인)":
        "설계 위치 중심 기준 수평 45 mm, 높이 28.5 mm,\n기울기 45° 이내면 채움 (존재 확인 수준)",
    "완성 + KCS 41 34 00 ①~⑤ 모두\n(②③④ 6 mm, ① 줄눈 10 ± 3 mm)": "완성 + KCS 41 34 00 ①~⑤ 모두 만족\n(②③④ 6 mm, ① 줄눈 10 ± 3 mm)",
    "주 지표 2 = 완성된 벽의 시방 항목 ①~⑤ 측정값 (mm, 연속값)  ·  채움 판정은 시방보다 훨씬 느슨하다":
        "주 지표 2: 완성 벽의 시방 항목 ①~⑤ 측정값 (mm, 연속값)  ·  채움 판정 기준은 시방 기준보다 훨씬 느슨함",
    "자리별 채운 벽 수 (조건마다 100벽)": "자리별 채움 벽 수 (조건별 100벽)",
    "쌓는 벽": "대상 벽체",
    "번호 = 쌓는 순서": "번호: 시공 순서",
    "칸 색 = 채운 벽 수": "칸 색: 채움 벽 수",
    "칸의 숫자 = 그 자리를 채운 벽 수 · 완성 = 16자리를 모두 채운 벽 · 시방 합격 = 완성한 벽 가운데 KCS 41 34 00 허용오차를 모두 지킨 벽":
        "칸 숫자: 해당 자리를 채운 벽 수 · 완성: 16자리를 모두 채운 벽 · 시방 합격: 완성 벽 중 KCS 41 34 00 허용오차를 모두 만족한 벽",
    "검측 6단계 모두": "검측 6단계 전체",
    "넓게 받기 끔": "넓게 받기 제거", "놓은 뒤 재배치 끔": "놓은 뒤 재배치 제거", "놓기 전 보정 끔": "놓기 전 보정 제거",
    "집기 정렬 끔": "집기 정렬 제거", "집기 확인 끔": "집기 확인 제거", "손에 든 벽돌 기준 끔": "손에 든 벽돌 기준 제거",
    "G3(놓은 뒤 재배치)를 끄면 완성한 벽도 허용오차 6 mm를 넘는다": "G3(놓은 뒤 재배치) 제거 시 완성 벽도 허용오차 6 mm 초과",
    "벽 앞면이 평평한가,\n단 윗면이 수평인가": "벽 앞면의 평탄 정도,\n각 단 윗면의 수평 정도",
    "위 단이 1단 앞면의 수직선에서\n벗어난 거리": "1단 앞면 수직선에서\n위 단까지의 이격 거리",
    "1단이 바닥 기준선에서\n벗어난 거리": "바닥 기준선에서\n1단까지의 이격 거리",
    "허용오차 6 mm 안": "허용오차 6 mm 이내",
    "허용오차 밖": "허용오차 초과",
    "6 mm 넘은 벽": "6 mm 초과 벽 수",
    "기준에서 어긋난 크기 (mm)": "기준 대비 편차 (mm)",
}
FIG_PART = [("점 하나 = 완성한 벽 하나 (", "점: 완성 벽 1개 ("), ("· 굵은 세로줄 = 중앙값", "· 굵은 세로선: 중앙값")]

FIGS = {"그림 116": ("그림1_정책만_대_검측6단계.png", 3.8), "그림 122": ("그림2_검측단계_흐름도.png", F.REFIG["그림 122"][2]),
        "그림 131": ("그림4_평가기준_채움_완성_시방.png", F.REFIG["그림 131"][2]), "그림 133": ("그림5_자리별_채운벽수_조건별.png", 16.0),
        "그림 137": ("그림6_시방항목_Full_FullG3.png", F.REFIG["그림 137"][2])}

# 배치 순서 (f판 순서 + 그림 · 표 제목)
LEFT = [("bar", "절 제목 101", 0.0, False), ("s1", None, 0.30, False),
        ("bar", "절 제목 121", 0.40, True), ("pic", "그림 122", 0.30, False), ("txt", "그림 2 제목", 0.05, False),
        ("txt", "표 1 제목", 0.22, True), ("tbl", "검측 단계 표 123", 0.05, False),
        ("txt", "표 2 제목", 0.25, True), ("tbl", "연구 질문 표 124", 0.05, False),
        ("bar", "절 제목 125", 0.40, True), ("sub", "소제목 3.1", 0.22, False), ("pic", "그림 127", 0.05, False),
        ("txt", "환경 그림 설명", 0.03, False), ("txt", "환경 글", 0.15, True), ("sub", "소제목 3.2", 0.20, True),
        ("pic", "그림 131", 0.05, False), ("txt", "그림 4 제목", 0.05, False)]
RIGHT = [("sub", "소제목 3.3", 0.0, False), ("pic", "그림 133", 0.05, False), ("txt", "그림 5 제목", 0.05, False),
         ("txt", "표 3 제목", 0.22, True), ("tbl", "결과 표 135", 0.05, False), ("txt", "결과 표 각주", 0.05, False),
         ("pic", "그림 137", 0.22, True), ("txt", "그림 6 제목", 0.05, False),
         ("bar", "절 제목 138", 0.40, True), ("txt", "고찰 글", 0.28, False),
         ("bar", "절 제목 140", 0.40, True), ("txt", "결론 글", 0.28, False), ("txt", "핵심 메시지", 0.22, True),
         ("bar", "절 제목 143", 0.40, True), ("txt", "감사의 글", 0.25, False), ("txt", "참고문헌", 0.12, True)]
S1_ROWS = [r if r[0] != "결과" else ("결과", [("pic", "그림 116"), ("txt", "그림 1 제목")]) for r in F.S1_ROWS]


def ptext(p):
    return "".join(t.text or "" for t in p.iter(qn("a:t")))


def set_par(p, segs):
    """문단의 글 조각을 segs로 바꾼다. 서식은 원래 조각(보통 · 굵게)의 rPr을 복사."""
    rs = p.findall(qn("a:r"))
    assert rs, "빈 문단"
    tpl = {}
    for r in rs:
        rp = r.find(qn("a:rPr"))
        tpl.setdefault(rp is not None and rp.get("b") == "1", rp)
    base = next(iter(tpl.values()))
    for e in list(p):
        if etree.QName(e).localname in ("r", "br"):
            p.remove(e)
    end = p.find(qn("a:endParaRPr"))
    for text, bold in segs:
        r = p.makeelement(qn("a:r"), {})
        src = tpl.get(bold, base)
        rp = copy.deepcopy(src) if src is not None else p.makeelement(qn("a:rPr"), {})
        rp.set("b", "1" if bold else "0")
        r.append(rp)
        etree.SubElement(r, qn("a:t")).text = text
        if end is not None:
            end.addprevious(r)
        else:
            p.append(r)


def rewrite(src, dst):
    """e판을 복사해 글만 바꾸고, 그림 · 표 제목 상자를 더한다. 바꾼 문단마다 (자리, 전, 후)를 돌려준다."""
    prs = Presentation(src); sl = prs.slides[0]
    log, done = [], set()
    by = {sh.name: sh for sh in sl.shapes}
    for sh in sl.shapes:
        if sh.name in TEXT:
            ps = sh._element.find(qn("p:txBody")).findall(qn("a:p"))
            new = TEXT[sh.name]
            assert len(ps) == len(new), (sh.name, len(ps), len(new))
            for p, segs in zip(ps, new):
                before = ptext(p); set_par(p, segs); log.append((sh.name, before, "".join(s for s, _ in segs)))
            done.add(sh.name)
        elif getattr(sh, "has_table", False) and sh.has_table:
            key = next(k for k in ("검측 단계 표", "연구 질문 표", "결과 표") if sh.name.startswith(k))
            for i, tr in enumerate(sh._element.findall(".//" + qn("a:tr"))):
                for j, tc in enumerate(tr.findall(qn("a:tc"))):
                    ps = tc.find(qn("a:txBody")).findall(qn("a:p"))
                    before = [ptext(p) for p in ps]
                    new = CELLS.get((key, i, j))
                    if new is None and key == "결과 표" and j == 4 and before[0] in VERDICT:
                        bold = any(r.find(qn("a:rPr")) is not None and r.find(qn("a:rPr")).get("b") == "1" for r in ps[0].findall(qn("a:r")))
                        new = [[(VERDICT[before[0]], bold)]]
                    if new is None:
                        continue
                    assert len(ps) == len(new), (key, i, j)
                    for p, segs in zip(ps, new):
                        set_par(p, segs)
                    log.append((f"{key} {i}줄 {j}칸", " / ".join(before), " / ".join("".join(s for s, _ in sg) for sg in new)))
                    done.add((key, i, j))
    miss = [k for k in TEXT if k not in done] + [k for k in CELLS if k not in done]
    assert not miss, f"바꿀 자리를 못 찾음: {miss}"
    # 머리 영역 (양식 파일 형식): 국문 제목 한 줄(부제는 콜론으로 붙임), 저자 별표, 소속 한 줄
    tps = by["직사각형 8"]._element.find(qn("p:txBody")).findall(qn("a:p"))
    log.append(("제목", ptext(tps[0]) + " / " + ptext(tps[1]), TITLE_KO))
    set_par(tps[0], [(TITLE_KO, B_)])                     # 부제 문단(tps[1])은 f판 restyle 뒤 post_style에서 지운다
    aps = by["Text Box 274"]._element.find(qn("p:txBody")).findall(qn("a:p"))
    log.append(("저자", ptext(aps[0]) + " / " + ptext(aps[1]), AUTHORS_KO + " / " + AUTHORS_EN))
    set_par(aps[0], [(AUTHORS_KO, N_)]); set_par(aps[1], [(AUTHORS_EN, N_)])
    fps = by["Text Box 275"]._element.find(qn("p:txBody")).findall(qn("a:p"))
    log.append(("소속", " / ".join(ptext(p) for p in fps), AFFIL))
    set_par(fps[0], [(AFFIL, N_)])
    for p in fps[1:]:
        p.getparent().remove(p)
    # 그림 · 표 제목: 원래 '표 1 제목'(결과 표)은 '표 3 제목'으로, 나머지는 그 상자를 복사해 만든다
    proto = by["표 1 제목"]._element
    proto.find(".//" + qn("p:cNvPr")).set("name", "표 3 제목")
    tree = proto.getparent()
    nid = max(int(e.get("id")) for e in tree.iter(qn("p:cNvPr")))
    for name, (num, title) in CAPTIONS.items():
        if name == "환경 그림 설명":
            el = by[name]._element
        elif name == "표 3 제목":
            el = proto
        else:
            el = copy.deepcopy(proto); nid += 1
            c = el.find(".//" + qn("p:cNvPr")); c.set("name", name); c.set("id", str(nid))
            tree.append(el)
        p = el.find(qn("p:txBody")).findall(qn("a:p"))[0]
        log.append((name, ptext(p) if el is not None and name in ("환경 그림 설명", "표 3 제목") else "(없음)", f"{num} {title}"))
        set_par(p, [(num, B_), (" " + title, N_)])
    prs.save(dst)
    return log


def post_style(path, B):
    """f판 restyle 뒤에: 머리 영역 글자 크기(양식 파일 값)와 그림 · 표 제목(굵은 번호 + 보통 글, 표는 왼쪽 · 그림은 가운데)."""
    C = round(B * 0.8 * 2) / 2
    prs = Presentation(path); sl = prs.slides[0]
    for sh in sl.shapes:
        n = sh.name
        if not sh.has_text_frame:
            continue
        ps = F.paras(sh)
        if n == "직사각형 8":
            if len(ps) == 3:
                ps[1].getparent().remove(ps[1]); ps = [ps[0], ps[2]]
            for p, sz, b in zip(ps, (TITLE_KO_PT, TITLE_EN_PT), (True, False)):
                F.style_par(p, ln=100, end_size=sz, algn="ctr")
                for r in F.runs(p):
                    F.style_run(r, sz, b)
            r = F.runs(ps[0])[0]; t = r.find(qn("a:t")); k = t.text.find(": ")   # 국문 제목도 영문처럼 콜론 뒤에서 줄바꿈 (로고와 겹치지 않게)
            if k > 0 and len(F.runs(ps[0])) == 1:
                r2 = copy.deepcopy(r); r2.find(qn("a:t")).text = t.text[k + 2:]; t.text = t.text[:k + 1]
                br = r.makeelement(qn("a:br"), {}); br.append(copy.deepcopy(r.find(qn("a:rPr"))))
                r.addnext(br); br.addnext(r2)
        elif n == "Text Box 274":
            for p, sz in zip(ps, (NAME_PT, NAME_EN_PT)):
                F.style_par(p, ln=110, end_size=sz, algn="ctr")
                for r in F.runs(p):
                    F.style_run(r, sz)
        elif n == "Text Box 275":
            for p in ps:
                F.style_par(p, ln=105, end_size=AFFIL_PT, algn="ctr")
                for r in F.runs(p):
                    F.style_run(r, AFFIL_PT)
        elif n in CAPTIONS:
            for p in ps:
                F.style_par(p, ln=100, end_size=C, algn="l" if n.startswith("표") else "ctr")
                for k, r in enumerate(F.runs(p)):
                    F.style_run(r, C, k == 0, F.BODY)
    prs.save(path)
    return C


def draw_figures(figd):
    """e판 그림 함수로 그림 1 · 2 · 4 · 5 · 6을 다시 그린다. 그리는 동안 matplotlib 글자만 FIG_EXACT · FIG_PART로 바꾼다."""
    os.environ.setdefault("WALL3_OUT", os.path.join(ROOT, "02_KSARC2026", "원자료_포스터d_20261111", "wall3"))
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))
    from matplotlib.axes import Axes
    from wall3 import poster_ksarc_20261111e as E
    from wall3 import primary_metrics_20261111 as pm
    used = set()

    def tr(s):
        if not isinstance(s, str):
            return s
        if s in FIG_EXACT:
            used.add(s); return FIG_EXACT[s]
        for a, b in FIG_PART:
            if a in s:
                used.add(a); s = s.replace(a, b)
        return s

    o_text, o_xl = Axes.text, Axes.set_xlabel
    Axes.text = lambda self, x, y, s, *a, **k: o_text(self, x, y, tr(s), *a, **k)
    Axes.set_xlabel = lambda self, s, *a, **k: o_xl(self, tr(s), *a, **k)
    try:
        res = pm.compute(); R = {r["label"]: r for r in res["rows"]}
        data, _ = E.load_all(); S = {lab: E.summarize(ws) for lab, ws in data.items()}
        for lab in E.ORDER:
            assert S[lab]["complete"] == R[lab]["complete"] and S[lab]["spec"] == R[lab]["spec_pass"], lab
        loo = [R[k] for k in E.ORDER[1:7]]
        drops = [-r["vs_full"]["complete_pp"] for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
        sig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
        unsig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] >= 0]
        order = ["G0", "G1", "G2", "G3", "H"]
        sig_s = " · ".join(sorted(sig, key=lambda s: order.index(s) if s in order else 9))
        plt = E.mpl_setup()
        os.makedirs(figd)
        out = {}
        for shape, (fname, h) in FIGS.items():
            f = os.path.join(figd, fname)
            if fname.startswith("그림1"):
                E.fig_summary(S, R, sig_s, drops, unsig, f, F.CW - F.TAG_W - F.TAG_GAP, h, plt)
            elif fname.startswith("그림2"):
                E.fig_flow(f, F.CW, h, plt)
            elif fname.startswith("그림4"):
                E.fig_eval(f, F.CW, h, plt)
            elif fname.startswith("그림5"):
                E.fig_main(S, f, F.CW, h, plt)
            else:
                E.fig_items(res, f, F.CW, h, plt)
            out[shape] = (f, h)
    finally:
        Axes.text, Axes.set_xlabel = o_text, o_xl
    miss = [k for k in list(FIG_EXACT) + [a for a, _ in FIG_PART] if k not in used]
    assert not miss, f"그림에서 못 찾은 글: {miss}"
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--src", default=F.SRC)
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "02_KSARC2026"))
    ap.add_argument("--body", type=float, default=None)
    ap.add_argument("--max-body", type=float, default=20.0)
    ap.add_argument("--min-body", type=float, default=12.0)
    a = ap.parse_args()
    out = os.path.join(a.out_dir, f"KSARC2026_포스터_초안_{a.tag}.pptx")
    png = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_PowerPoint.png")
    js = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_배치.json")
    figd = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_그림")
    for f in (out, png, js, figd):
        if os.path.exists(f):
            sys.exit(f"이미 있음(덮어쓰지 않음): {f}")
    F.LEFT, F.RIGHT, F.S1_ROWS = LEFT, RIGHT, S1_ROWS
    tmp = tempfile.mkdtemp(prefix="poster_rewrite_")
    src2 = os.path.join(tmp, "e_rewritten.pptx")
    log = rewrite(a.src, src2)
    figs = draw_figures(figd)
    trials = []

    def build(B, f):
        sizes = F.restyle(src2, f, B, figs)
        sizes["그림·표 제목"] = post_style(f, B)
        sizes.update({"국문 제목": TITLE_KO_PT, "영문 제목": TITLE_EN_PT, "저자·영문 이름·소속": [NAME_PT, NAME_EN_PT, AFFIL_PT]})
        for k in ("제목·부제·영문 제목",):
            sizes.pop(k, None)
        return sizes

    def trial(B):
        f = os.path.join(tmp, f"try_{B:.1f}.pptx")
        build(B, f)
        rep = F.layout(f)
        trials.append({"본문": B, "단 끝": rep["단 끝 cm (왼쪽, 오른쪽)"], "들어감": F.fits(rep)})
        print(f"  본문 {B:4.1f} pt → 단 끝 {rep['단 끝 cm (왼쪽, 오른쪽)']} · 머리 {rep['머리 영역 글 끝 cm']} → "
              f"{'들어감' if F.fits(rep) else '넘침'}", flush=True)
        return rep

    if a.body is not None:
        B = a.body
    else:
        B = a.max_body
        while B >= a.min_body:
            if F.fits(trial(B)):
                break
            B -= 0.5
        else:
            sys.exit("들어가는 크기를 찾지 못함")
    f = os.path.join(tmp, "final_in.pptx")
    sizes = build(B, f)
    rep = F.layout(f, save_as=out, png=png)
    rep["글자 크기 pt"] = sizes; rep["시험한 크기"] = trials
    rep["다시 그린 그림 (파일, 높이 cm)"] = {k: [os.path.basename(v[0]), v[1]] for k, v in figs.items()}
    rep["바꾼 문장 (자리, 전, 후)"] = log
    json.dump(rep, open(js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"본문 {B} pt · 단 끝 {rep['단 끝 cm (왼쪽, 오른쪽)']} · {'들어감' if F.fits(rep) else '넘침'}\n{out}\n{png}\n{js}")


if __name__ == "__main__":
    main()
