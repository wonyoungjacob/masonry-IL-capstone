# -*- coding: utf-8 -*-
"""도식 7장: HTML/CSS/SVG → Edge headless 스크린샷(2배 해상도)."""
import subprocess, time, os, sys
SP = r"C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop----/be685ff9-f10f-46a4-892d-1862ceb8f949/scratchpad/media/html"
OUT = r"C:/Users/user/Desktop/사기설/01_사기설/중간발표1/그림"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
os.makedirs(SP, exist_ok=True)

CSS = """<meta charset="utf-8"><style>
*{box-sizing:border-box} body{margin:0;background:#fff;font-family:'Malgun Gothic','Noto Sans KR',sans-serif;color:#243549}
.wrap{padding:18px} h3{margin:0 0 10px;font-size:22px;color:#143a50}
.row{display:flex;align-items:stretch;gap:0}
.box{border:2.5px solid #147c85;background:#edf5f6;border-radius:8px;padding:10px 14px;font-size:17px;line-height:1.35}
.box b{display:block;font-size:19px;color:#143a50;margin-bottom:4px}
.red{border-color:#b0412a;background:#fff1ec} .blue{border-color:#2a5fb0;background:#eef3fb} .grey{border-color:#8a98a3;background:#f4f6f8}
.arrow{display:flex;align-items:center;justify-content:center;font-size:30px;color:#5b6973;padding:0 8px}
.cap{font-size:15px;color:#5b6973;margin-top:8px}
.tag{display:inline-block;padding:2px 9px;border-radius:12px;font-size:14px;font-weight:bold;color:#fff;margin-right:6px}
.tb{background:#2a5fb0} .tr{background:#b0412a} .tg{background:#1d7a3e}
</style>"""

FIGS = {}

FIGS["fig_pipeline"] = (1600, 600, CSS + """<div class="wrap">
<h3>연구 전체 파이프라인 — 로봇이 아는 것(파랑)과 연구자만 아는 것(빨강)</h3>
<div class="row">
 <div class="box red" style="width:300px"><b>시뮬레이터 정답 좌표</b>벽돌 위치·방향 (MuJoCo 상태)<br><span class="tag tr">연구자</span>로봇은 모름</div>
 <div class="arrow">→</div>
 <div class="box red" style="width:300px"><b>IK 스크립트 교사</b>좌표를 알고 집기·운반·놓기 실행<br>성공한 시연만 자동 선별 (454 → 240)</div>
 <div class="arrow">→</div>
 <div class="box blue" style="width:330px"><b>학습 정책 (학생)</b>ACT · Diffusion Policy<br>입력: 카메라 3대 128×128 + 관절 6<br>출력: 관절 목표 6 (20 Hz)<br><span class="tag tb">로봇</span>좌표 입력 없음</div>
 <div class="arrow">→</div>
 <div class="box blue" style="width:330px"><b>실행 중 로봇 = 정책 + 탑재 검측</b>정책: 접근·파지·운반<br>G1 집게 각도·손목 하중<br>G2·G3 탑재 카메라 추정 좌표<br><span class="tag tb">로봇</span>탑재 감각만</div>
</div>
<div class="row" style="margin-top:22px">
 <div class="box red" style="width:1500px;display:flex;gap:30px;align-items:center"><div><b style="display:inline">채점</b> — 놓인 벽돌 3개의 실제 좌표로 위치 4.5 mm · 높이 4.5 mm · 방향 5° · 기울기 10° 판정</div>
 <div style="margin-left:auto"><span class="tag tr">연구자</span>정답 좌표의 용도: 시연 생성 · 학습 라벨 · 채점 · 검출 식별(감사)뿐</div></div>
</div>
<div class="cap">실험 3의 조건 C·D(정답 좌표 검측)는 점선 위치의 "진단용 오라클"이며 로봇 시스템의 일부가 아님 → RQ4에서 탑재 카메라 추정으로 교체</div>
</div>""")

FIGS["fig_division"] = (1600, 640, CSS + """<div class="wrap">
<h3>한 사이클의 분담 — 위: 학습 정책이 맡는 구간 / 아래: 탑재 검측이 끼어드는 지점</h3>
<div class="row" style="gap:10px">
 <div class="box grey" style="width:120px;text-align:center"><b>접근</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>파지</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>들어 올림</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>운반</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>놓기 직전</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>해제</b></div><div class="arrow">→</div>
 <div class="box grey" style="width:120px;text-align:center"><b>놓은 뒤</b></div>
</div>
<div style="position:relative;height:60px;margin:6px 0">
 <div style="position:absolute;left:0;width:1000px;top:14px;height:34px;background:#2a5fb0;border-radius:17px;color:#fff;font-weight:bold;font-size:18px;line-height:34px;text-align:center">학습 정책 (카메라 3대 + 관절값) — 다시 학습하지 않음</div>
 <div style="position:absolute;left:1020px;width:540px;top:14px;height:34px;background:#8a98a3;border-radius:17px;color:#fff;font-size:17px;line-height:34px;text-align:center">검측이 팔을 잠시 넘겨받음</div>
</div>
<div class="row" style="gap:20px;margin-top:6px">
 <div class="box" style="width:430px;margin-left:300px"><b>G1 잡기 확인 — 자체 감각만</b>1.5 cm 들고 집게 각도 &gt; 0.2 rad AND 손목 하중 ≥ 0.9 N<br>빈손이면 열고 재접근<br><span class="tag tg">현장 가능</span>집게 서보 각도로 충분</div>
 <div class="box" style="width:400px"><b>G2 놓기 전 보정 — 위치 정보 필요</b>쥔 벽돌 vs 목표: 2.5 mm · 3° · 3 mm<br>어긋나면 이동 수정 (최대 1 s)<br><span class="tag tb">탑재 카메라</span>RQ4</div>
 <div class="box" style="width:400px"><b>G3 놓은 뒤 재배치 — 위치 정보 필요</b>4.5 mm · 3 mm · 5° · 5° 초과면<br>다시 집어 1회 재배치<br><span class="tag tb">탑재 카메라</span>RQ4</div>
</div>
<div class="cap">검측은 세 지점에서만 개입하고 나머지 구간은 정책이 낸 관절 목표가 그대로 실행된다. 모든 비교 조건에서 정책 가중치가 같다.</div>
</div>""")

FIGS["fig_truth_usage"] = (1000, 1000, CSS + """<div class="wrap">
<h3>'정답 좌표를 누가 쓰나'</h3>
<div class="row" style="gap:24px">
 <div style="width:450px">
  <div class="box red" style="margin-bottom:12px"><b>① 시연 생성</b>IK 스크립트 교사가 벽돌 좌표로 경로 계산<br><span class="tag tr">연구자</span></div>
  <div class="box red" style="margin-bottom:12px"><b>② 학습 라벨</b>성공 시연 선별(허용오차 판정)<br><span class="tag tr">연구자</span></div>
  <div class="box red" style="margin-bottom:12px"><b>③ 채점</b>놓인 벽돌의 실제 좌표로 합격 판정<br><span class="tag tr">연구자</span></div>
  <div class="box red" style="margin-bottom:12px"><b>④ 검출 식별·감사</b>카메라 검출이 어느 벽돌인지 맞추기, 오차 기록<br><span class="tag tr">연구자</span></div>
  <div class="box red" style="border-style:dashed;background:#fff"><b>진단용 오라클 (실험 3 조건 C·D)</b>검측에 정답 좌표를 준 상한값 실험<br>"복구에 어떤 정보가 필요한가"를 재는 용도<br>→ RQ4에서 카메라 추정으로 교체</div>
 </div>
 <div style="width:450px">
  <div class="box blue" style="height:100%"><b>실행 중 로봇이 쓰는 것</b>
   <div style="margin-top:10px;font-size:17px;line-height:1.6">
   • 카메라 3대 영상 (앞·손목·위)<br>• 관절값 6 (팔 5 + 집게)<br>• 집게 각도 (서보)<br>• 손목 하중 (힘 센서)<br>• 탑재 윗면 카메라로 추정한 벽돌 위치 (RQ4)<br></div>
   <div style="margin-top:18px;padding:10px;background:#fff;border-radius:6px;font-size:16px"><span class="tag tb">로봇</span><b style="display:inline">정답 좌표는 한 번도 들어가지 않음</b><br>실기에서 모두 얻을 수 있는 신호만</div>
  </div>
 </div>
</div>
</div>""")

FIGS["fig_teacher_student"] = (1600, 360, CSS + """<div class="wrap">
<h3>교사 → 학생 구조 (Tao et al. 2026, Huang et al. 2026과 같은 틀)</h3>
<div class="row">
 <div class="box red" style="width:360px"><b>교사: IK 스크립트</b>특권 정보(정답 벽돌 좌표)를 알고 안정된 경로로 집기·운반·놓기<br>성공만 자동 선별</div>
 <div class="arrow">→</div>
 <div class="box grey" style="width:260px;text-align:center"><b>시연 240개</b>366프레임 × 20 Hz = 18.3 s<br>영상 3대 + 관절 6 + 행동 6</div>
 <div class="arrow">→</div>
 <div class="box blue" style="width:420px"><b>학생: ACT · Diffusion Policy</b>입력 카메라 3대 128×128 + 관절 6<br>출력 관절 목표 6 (행동 청크)<br>좌표·접촉력 입력 없음</div>
 <div class="arrow">→</div>
 <div class="box blue" style="width:300px"><b>실행</b>카메라와 관절값만으로 같은 작업<br>교사와 행동 공간이 같아 불일치 없음</div>
</div>
</div>""")

FIGS["fig_models"] = (1600, 640, CSS + """<div class="wrap">
<h3>두 정책의 구조 (우리 설정 치수) — 원논문 Zhao et al. 2023 Fig. 2, Chi et al. 2023 Fig. 3을 단순화해 다시 그림</h3>
<div class="row" style="gap:40px">
 <div style="width:750px">
  <div style="font-size:19px;font-weight:bold;color:#143a50;margin-bottom:8px">ACT (Action Chunking Transformer)</div>
  <div class="row">
   <div class="box grey" style="width:200px"><b>관측</b>앞·손목·위 128×128 RGB ×3<br>관절 6</div><div class="arrow">→</div>
   <div class="box" style="width:170px"><b>ResNet-18 ×3</b>영상 특징</div><div class="arrow">→</div>
   <div class="box" style="width:200px"><b>트랜스포머 인코더–디코더</b>CVAE 스타일 잠재 z (학습 시)</div><div class="arrow">→</div>
   <div class="box blue" style="width:150px"><b>행동 청크</b>100스텝 × 관절 6</div>
  </div>
  <div class="cap">40k 갱신 · 배치 32 · 시간 앙상블 없음 · 실행 길이 10스텝(0.5 s)마다 재관측 · LeRobot 0.6.1 기본값</div>
 </div>
 <div style="width:750px">
  <div style="font-size:19px;font-weight:bold;color:#143a50;margin-bottom:8px">Diffusion Policy</div>
  <div class="row">
   <div class="box grey" style="width:200px"><b>관측 2프레임</b>앞·손목·위 128×128 ×3<br>관절 6</div><div class="arrow">→</div>
   <div class="box" style="width:170px"><b>ResNet-18 ×3</b>조건 특징</div><div class="arrow">→</div>
   <div class="box" style="width:200px"><b>조건부 확산 (1D U-Net)</b>잡음 행동열 → 반복 제거 (DDPM)</div><div class="arrow">→</div>
   <div class="box blue" style="width:150px"><b>행동열</b>horizon 64 × 관절 6</div>
  </div>
  <div class="cap">60k 갱신 · 배치 32 · 실행 길이 10스텝 · LeRobot 0.6.1 기본값</div>
 </div>
</div>
<div class="cap" style="margin-top:14px">두 정책 모두: 입력에 벽돌 좌표·접촉력 없음 · 출력은 관절 목표값 6 (20 Hz) · 학습 seed 1000/1001/1002 × 3회 · RTX 5090 1장, PyTorch 2.11.0+cu128, MuJoCo 3.13.0</div>
</div>""")

FIGS["fig_tolerance"] = (1100, 700, CSS + """<div class="wrap">
<h3>성공 기준 (벽돌 3개 모두 만족해야 완성)</h3>
<svg width="1060" height="600" viewBox="0 0 1060 600" font-family="Malgun Gothic" font-size="17">
 <!-- plan view -->
 <text x="20" y="28" font-size="19" font-weight="bold" fill="#143a50">평면 (위에서 본 모습)</text>
 <text x="80" y="62" fill="#b0412a">점선 = 설계 위치 (90 × 42.6 mm), 주황 = 놓인 벽돌</text>
 <rect x="80" y="90" width="300" height="142" fill="#f6b48a" stroke="#b0412a" stroke-width="2" stroke-dasharray="6 4"/>
 <g transform="translate(236 165) rotate(4)"><rect x="-150" y="-71" width="300" height="142" fill="#f08a5d" opacity="0.85" stroke="#8c3a1e" stroke-width="2"/></g>
 <circle cx="230" cy="161" r="22" fill="none" stroke="#2a5fb0" stroke-width="2.5"/>
 <circle cx="236" cy="165" r="3" fill="#8c3a1e"/>
 <line x1="230" y1="183" x2="230" y2="250" stroke="#2a5fb0" stroke-width="1.5"/>
 <text x="150" y="268" fill="#2a5fb0" font-weight="bold">중심 위치 오차 &lt; 4.5 mm (파란 원)</text>
 <line x1="236" y1="165" x2="440" y2="165" stroke="#1d7a3e" stroke-width="1.5" stroke-dasharray="4 3"/>
 <line x1="236" y1="165" x2="439" y2="151" stroke="#1d7a3e" stroke-width="2.5"/>
 <text x="448" y="162" fill="#1d7a3e" font-weight="bold">방향 오차 &lt; 5°</text>
 <text x="80" y="300" fill="#5b6973" font-size="15">실척 환산 9.5 mm: 세로줄눈 +9.5 mm [24], 직진도 ±10 mm [25]</text>
 <!-- elevation -->
 <text x="20" y="350" font-size="19" font-weight="bold" fill="#143a50">입면 (옆에서 본 모습)</text>
 <rect x="80" y="430" width="300" height="90" fill="#f6b48a" stroke="#b0412a" stroke-width="2" stroke-dasharray="6 4"/>
 <g transform="translate(240 475) rotate(-6)"><rect x="-150" y="-45" width="300" height="90" fill="#f08a5d" opacity="0.85" stroke="#8c3a1e" stroke-width="2"/></g>
 <line x1="420" y1="430" x2="420" y2="402" stroke="#2a5fb0" stroke-width="2.5"/>
 <line x1="410" y1="430" x2="430" y2="430" stroke="#2a5fb0" stroke-width="2"/><line x1="410" y1="402" x2="430" y2="402" stroke="#2a5fb0" stroke-width="2"/>
 <text x="438" y="422" fill="#2a5fb0" font-weight="bold">높이 오차 &lt; 4.5 mm</text>
 <line x1="90" y1="520" x2="210" y2="520" stroke="#1d7a3e" stroke-width="1.5" stroke-dasharray="4 3"/>
 <line x1="90" y1="520" x2="208" y2="500" stroke="#1d7a3e" stroke-width="2.5"/>
 <text x="220" y="528" fill="#1d7a3e" font-weight="bold">기울기 &lt; 10°</text>
 <text x="80" y="580" fill="#5b6973">보조 지표: 3D IoU · 검측 G3의 개입 기준(4.5 mm · 3 mm · 5° · 5°)은 이보다 엄격</text>
 <!-- right column -->
 <g transform="translate(640 360)">
  <rect x="0" y="0" width="400" height="200" rx="8" fill="#edf5f6" stroke="#147c85" stroke-width="2.5"/>
  <text x="16" y="34" font-size="19" font-weight="bold" fill="#143a50">축소 모형 → 실척</text>
  <text x="16" y="70">벽돌 90 × 42.6 × 27 mm</text>
  <text x="16" y="98">= KS 표준형 190 × 90 × 57 의 약 0.47배 [19]</text>
  <text x="16" y="134">위치 4.5 mm ↔ 실척 9.5 mm</text>
  <text x="16" y="162">높이 4.5 mm ↔ 실척 9.5 mm</text>
  <text x="16" y="190">방향 5°, 기울기 10° 는 그대로</text>
 </g>
 <g transform="translate(640 60)">
  <rect x="0" y="0" width="400" height="250" rx="8" fill="#fff5e9" stroke="#c7802a" stroke-width="2.5"/>
  <text x="16" y="34" font-size="19" font-weight="bold" fill="#143a50">네 가지를 모두 넘어야 합격</text>
  <text x="16" y="72">① 중심 위치 오차 &lt; 4.5 mm</text>
  <text x="16" y="104">② 높이 오차 &lt; 4.5 mm</text>
  <text x="16" y="136">③ 방향(yaw) 오차 &lt; 5°</text>
  <text x="16" y="168">④ 기울기 &lt; 10°</text>
  <text x="16" y="212" fill="#5b6973" font-size="15">벽돌 3개가 모두 합격해야 "완성" 1회로 셈</text>
  <text x="16" y="236" fill="#5b6973" font-size="15">판정은 놓인 뒤 안정(settle) 후의 실제 좌표로</text>
 </g>
</svg></div>""")

FIGS["fig_gantt"] = (1300, 560, CSS + """<div class="wrap">
<h3>일정 (2026-10-13 중간 1 → 12-08 최종)</h3>
<svg width="1260" height="470" viewBox="0 0 1260 470" font-family="Malgun Gothic" font-size="16">
 <defs><pattern id="hat" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#2a5fb0" stroke-width="3"/></pattern></defs>
 <!-- axis: 10/06 .. 12/14 = 70 days over 1000 px from x=220 -->
 <g stroke="#d9e4e9"><line x1="220" y1="40" x2="220" y2="430"/><line x1="363" y1="40" x2="363" y2="430"/><line x1="506" y1="40" x2="506" y2="430"/><line x1="649" y1="40" x2="649" y2="430"/><line x1="792" y1="40" x2="792" y2="430"/><line x1="935" y1="40" x2="935" y2="430"/><line x1="1078" y1="40" x2="1078" y2="430"/><line x1="1220" y1="40" x2="1220" y2="430"/></g>
 <g fill="#5b6973" font-size="14"><text x="212" y="30">10/06</text><text x="355" y="30">10/16</text><text x="498" y="30">10/26</text><text x="641" y="30">11/05</text><text x="784" y="30">11/15</text><text x="927" y="30">11/25</text><text x="1070" y="30">12/05</text></g>
 <!-- rows -->
 <text x="10" y="80" font-weight="bold" fill="#143a50">RQ4 소형 환경</text><rect x="320" y="60" width="157" height="30" rx="6" fill="#147c85"/><text x="330" y="81" fill="#fff" font-size="14">10/13–10/24</text><text x="486" y="81" fill="#243549" font-size="14">학습 정책 + 카메라 검측 D (seed 3, 시험 50·검증 40) · 예측 vs 실측</text>
 <text x="10" y="135" font-weight="bold" fill="#143a50">대형 환경 구축 (병행)</text><rect x="334" y="115" width="286" height="30" rx="6" fill="#2a5fb0"/><text x="344" y="136" fill="#fff" font-size="14">10/14–11/03</text><text x="629" y="136" fill="#243549" font-size="14">산업용 팔 · 실척 벽돌 · 3단×4~5개 벽체 · 교사 확장 · 시연 수집</text>
 <text x="10" y="190" font-weight="bold" fill="#143a50">시연 수 곡선</text><rect x="477" y="170" width="143" height="30" rx="6" fill="#8a98a3"/><text x="487" y="191" fill="#fff" font-size="14">10/24–11/03</text><text x="629" y="191" fill="#243549" font-size="14">60 / 120 / 240개 학습 → 완성률</text>
 <text x="10" y="245" font-weight="bold" fill="#143a50">RQ5 벽체 학습·평가</text><rect x="735" y="225" width="286" height="30" rx="6" fill="#1d7a3e"/><text x="745" y="246" fill="#fff" font-size="14">11/11–12/01</text><text x="1030" y="246" fill="#243549" font-size="14">정책 + 카메라 검측 · 단별 오차</text>
 <text x="10" y="300" font-weight="bold" fill="#143a50">보고서·발표 준비</text><rect x="1021" y="280" width="100" height="30" rx="6" fill="#c7802a"/><text x="1031" y="301" fill="#fff" font-size="14">12/02–12/08</text>
 <!-- milestones -->
 <g fill="#b0412a"><polygon points="320,360 332,380 308,380"/><polygon points="720,360 732,380 708,380"/><polygon points="1120,360 1132,380 1108,380"/></g>
 <g font-size="14" fill="#b0412a" font-weight="bold"><text x="280" y="400">10/13 중간 1</text><text x="680" y="400">11/10 중간 2</text><text x="1080" y="400">12/08 최종</text></g>
 <text x="10" y="372" font-weight="bold" fill="#143a50">발표</text>
 <text x="10" y="450" fill="#5b6973" font-size="14">모든 학습·평가는 Ubuntu PC(RTX 5090), 코드·결과는 github.com/wonyoungjacob/masonry-IL-capstone</text>
</svg></div>""")

FIGS["fig_external_metrology"] = (1260, 700, CSS + """<div class="wrap">
<h3>기존 조적 로봇의 위치 확보 방식 — 외부 계측 → 기준 좌표 재정합</h3>
<svg width="1220" height="560" viewBox="0 0 1220 560" font-family="Malgun Gothic" font-size="17">
 <rect x="0" y="420" width="1220" height="4" fill="#8a98a3"/>
 <!-- wall -->
 <g fill="#f08a5d" stroke="#8c3a1e" stroke-width="1.5">
  <rect x="80" y="380" width="120" height="40"/><rect x="204" y="380" width="120" height="40"/><rect x="328" y="380" width="120" height="40"/>
  <rect x="142" y="336" width="120" height="40"/><rect x="266" y="336" width="120" height="40"/>
  <rect x="80" y="292" width="120" height="40"/><rect x="204" y="292" width="120" height="40"/>
 </g>
 <!-- robot base + arm -->
 <rect x="600" y="340" width="140" height="80" rx="8" fill="#dfe6ea" stroke="#5b6973" stroke-width="2"/>
 <line x1="670" y1="340" x2="560" y2="220" stroke="#5b6973" stroke-width="14" stroke-linecap="round"/>
 <line x1="560" y1="220" x2="420" y2="300" stroke="#5b6973" stroke-width="12" stroke-linecap="round"/>
 <rect x="392" y="292" width="60" height="30" fill="#f08a5d" stroke="#8c3a1e" stroke-width="1.5"/>
 <text x="600" y="450" fill="#5b6973">조적 로봇 (이동식 또는 고정식)</text>
 <!-- laser tracker -->
 <circle cx="1050" cy="190" r="30" fill="#edf5f6" stroke="#147c85" stroke-width="3"/>
 <rect x="1036" y="220" width="28" height="60" fill="#edf5f6" stroke="#147c85" stroke-width="3"/>
 <text x="930" y="140" fill="#147c85" font-weight="bold">레이저 트래커 / 토탈스테이션</text>
 <line x1="1022" y1="200" x2="450" y2="296" stroke="#b0412a" stroke-width="2.5" stroke-dasharray="8 6"/>
 <line x1="1022" y1="200" x2="700" y2="342" stroke="#b0412a" stroke-width="2.5" stroke-dasharray="8 6"/>
 <text x="430" y="200" fill="#b0412a" font-weight="bold">① 집게·벽돌·로봇 위치를 외부에서 계측</text>
 <!-- correction loop -->
 <path d="M 700 250 Q 760 300 700 330" fill="none" stroke="#2a5fb0" stroke-width="2.5" marker-end="url(#ar)"/>
 <defs><marker id="ar" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#2a5fb0"/></marker></defs>
 <text x="710" y="290" fill="#2a5fb0" font-weight="bold">② 기준 좌표로 재정합</text>
 <!-- notes -->
 <g font-size="16" fill="#243549">
  <text x="40" y="60">In situ Fabricator [2]: 레이저 트래커 기준 좌표로 매 벽돌 보정 · Hadrian X: 레이저 추적 동적 보정 · SAM100: 레이저 기준선 센서</text>
  <text x="40" y="92" fill="#b0412a" font-weight="bold">벽돌 규격·적재 조건이 바뀌면 → 사람이 계측 기준과 경로를 다시 설정해야 함</text>
 </g>
 <g transform="translate(40 480)"><rect x="0" y="0" width="1140" height="60" rx="8" fill="#eef3fb" stroke="#2a5fb0" stroke-width="2"/>
  <text x="16" y="38" font-size="17" fill="#143a50"><tspan font-weight="bold">이 연구의 로봇:</tspan> 외부 계측 없이 탑재 카메라 영상 + 관절값만 → 재설정 부담이 없음 (그 대신 실패를 스스로 알아채야 함)</text></g>
</svg></div>""")


def shoot(name, w, h, html):
    p = os.path.join(SP, name + ".html")
    open(p, "w", encoding="utf-8").write("<!doctype html><html lang='ko'>" + html + "</html>")
    out = os.path.join(OUT, name + ".png")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={w},{h}", f"--screenshot={out}", "file:///" + p.replace("\\", "/")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    ok = os.path.exists(out) and os.path.getsize(out) > 1000
    if ok:  # 흰 여백 자르기 (아래·오른쪽), 여유 24 px
        from PIL import Image, ImageChops
        im = Image.open(out).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bbox = ImageChops.difference(im, bg).getbbox()
        if bbox:
            im.crop((0, 0, min(im.width, bbox[2] + 24), min(im.height, bbox[3] + 24))).save(out)
    print(name, "ok" if ok else "FAILED", flush=True)


if __name__ == "__main__":
    names = sys.argv[1:] or list(FIGS)
    for n in names:
        w, h, html = FIGS[n]; shoot(n, w, h, html)
