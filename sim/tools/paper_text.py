"""Body text of the KICEM draft (revision 2). Numbers come from paper_results.collect().

Condition letters in the paper vs. run names: A = A_policy, B = C_anglelaod_inplace, C = D_pre_release, D = E_replace.
"""
from reportlab.platypus import Paragraph
from build_kicem_paper import S


def _p(t, st="body"):
    return Paragraph(t, S[st])


def _pc(s):
    return f"{100 * s['rate']:.0f}%" if s and s["n"] else "-"


def text(r):
    T, N, M = r["test"], r["noise"], r["multi"]
    d, a = T["diffusion"], T["act"]
    dA, dB, dC, dD = d["A_policy"], d["C_anglelaod_inplace"], d["D_pre_release"], d["E_replace"]
    aA, aB, aC, aD = a["A_policy"], a["C_anglelaod_inplace"], a["D_pre_release"], a["E_replace"]
    e1, e2 = T["expert"], T["expert_gate"]
    nd, na = len(r["seeds"]["diffusion"]), len(r["seeds"]["act"])
    out = {}
    out["intro"] = [
        _p("1. 서론", "h1"), _p("1.1 연구의 배경 및 목적", "h2"),
        _p("국내 건설기능인력은 2026년 수요 약 171만 명에 비해 내국인 공급이 약 142만 명에 그쳐 약 30만 명이 부족할 것으로 "
           "전망된다(건설근로자공제회, 2025). 조적은 정형화된 단위 작업의 반복과 중량물 취급이 겹쳐 자동화 수요가 큰 공종이나, "
           "기존 조적 로봇은 사람이 설계한 계측·계획·제어 절차에 의존하여 조건이 바뀔 때마다 재설정이 필요하다. 시연을 모방하여 "
           "영상에서 곧바로 동작을 출력하는 모방학습 정책(Zhao et al., 2023; Chi et al., 2023)은 이 재설정 부담을 줄이는 "
           "대안으로 주목받고 있다."),
        _p("그러나 성공 시연만으로 학습한 정책은 실패 상태를 경험하지 못하여, 파지에 실패하고도 다음 단계로 넘어가는 현상이 "
           "보고되었고(Yang et al., 2025), mm 단위 정밀도에서는 시연을 늘려도 넘기 어려운 한계가 제시되었다(Xu et al., 2026). "
           "이에 정책 밖에서 실패를 감지하여 재실행하거나(Zheng et al., 2026) 외부 보정 제어를 결합하는 연구(Ibrahimov et al., "
           "2026)가 이어지고 있다. 벽돌 조립에서는 Diffusion Policy 기술 사이에 사전·사후 조건 검사를 두고 실패를 원인별로 "
           "분류한 연구(Yu et al., 2026)와 측정 기반 벽돌 자세 보정(Gao and Adel, 2026)이 보고되었다. 그러나 이들 연구는 확인·보정 "
           "기능을 하나의 체계로 묶어 전체 성공률의 향상을 보고하므로, 개별 단계가 어떤 실패를 얼마나 줄였는지는 드러나지 않는다. "
           "조적 공정에서 이 구분이 필요한 이유는 두 가지이다. 첫째, 검측에 투입할 수 있는 인력·장비·시간이 한정되어 있어 로봇 "
           "공정의 어느 단계에 검측을 배치할지 정해야 한다. 둘째, 모르타르 위에 놓인 벽돌을 다시 들면 부착이 손상되어 재작업 "
           "비용이 크므로, 어떤 실패를 배치 전에 막아야 하는지가 품질관리의 핵심이 된다."),
        _p("이에 본 연구는 시공 현장의 검측 절차, 즉 시공자 자체 점검과 검측, 불합격 시 보완시공 후 재검측(국토교통부, 2026)에 "
           "대응하는 확인 단계(이하 검측 단계)를 학습 정책 밖에 두고, 단계를 하나씩 추가하며 각 단계가 조적 완성률에 미치는 영향을 "
           "분리하여 측정한다. 각 확인 "
           "기법은 기존 문헌의 방법이며, 본 연구의 기여는 조적 과제에서의 단계별 측정과 그 건설관리적 해석에 있다."),
        _p("1.2 연구의 범위 및 방법", "h2"),
        _p("물리 시뮬레이터 MuJoCo에서 저가 로봇팔 SO-ARM100(팔 관절 5개와 그리퍼 관절 1개)이 블록 3개를 아래 2개, 위 1개로 쌓는 "
           "과제로 범위를 한정하며(그림 1), 실물 이식은 다루지 않는다."),
    ]
    out["method1"] = [
        _p("2. 연구 방법", "h1"), _p("2.1 과제 및 학습 조건", "h2"),
        _p("블록 치수는 KS L 4201(점토 벽돌)의 표준형 190×90×57 mm를 긴 변 90 mm로 축소(축척 s = 90/190 ≈ 0.474)하여 "
           "90×42.6×27 mm로 하였다. 밀도는 점토벽돌 제조사 기술자료의 총건조밀도 1,800 kg/m³(Wienerberger, 2026)를 적용하여 "
           "개당 질량은 186.5 g(1.83 N)이다. 가로줄눈(모르타르층)은 KCS 41 34 02:2021 3.4.2(1)의 표준 줄눈 너비 10 mm에 같은 "
           "축척을 적용하여 4.7 mm로 하였고, 세로줄눈(머리줄눈)은 모르타르를 모사하지 않으므로 이웃 블록과의 맞댐 간격 1 mm로 "
           "두었다. 공급 블록의 위치는 ±30 mm, 방향은 ±60° 범위에서 무작위로 정한다."),
        _p("시연은 블록의 정답 좌표로 경로를 계산하는 역기구학 스크립트(이하 전문가 스크립트)가 생성하였다. 454회 시도 중 첫 "
           "시도에 성공한 240개(학습 200, 검증 40)로 ACT와 Diffusion Policy를 학습하였으며, 두 정책은 카메라 3대의 영상"
           "(128×128)과 관절값 6개(팔 5개, 그리퍼 1개)만 입력받아 20 Hz로 같은 6개 관절의 목표값을 출력한다."),
        _p("성공은 세 블록이 모두 설계 위치 대비 중심 오차 4.5 mm, 방향 5°, 기울기 10° 이내에 놓인 경우이다. KCS 41 34 02에는 "
           "쌓기 위치의 허용오차가 따로 규정되어 있지 않아, 위치 기준은 블록 길이의 5%(실척 환산 9.5 mm)로 하여 배치 오차가 실척 "
           "줄눈 너비 10 mm 안에서 흡수되도록 정하였다. 방향 5°는 블록 끝단 변위 (L/2)·sin 5° ≈ 3.9 mm로 위치 기준과 같은 수준이 "
           "되도록 한 값이고, 기울기 10°는 블록이 이웃 블록에 걸치거나 넘어진 상태를 가려내는 기준이다."),
    ]
    out["method2"] = [
        _p("2.2 실패 원인 분석", "h2"),
        _p("시연 생성 중 발생한 첫 블록 파지 실패 70건을 전수 재현한 결과, 35건은 집게가 로봇 몸체에 부딪혔고 30건은 닫히는 "
           "집게가 이웃 블록을 쳤으며 5건은 집게 끝이 블록 윗면에 얹혔다. 즉 학습 이전에 집을 수 없는 초기 배치가 섞여 있었다. "
           "학습된 정책은 집게 각도를 입력으로 받으면서도 빈손으로 운반을 계속하였고, ACT는 놓기 직전 5~18 mm 어긋나 있었다."),
        _p("2.3 검측 단계 설계", "h2"),
        _p("그림 2와 같이 네 검측 단계를 둔다. G0(실행가능성 필터)는 파지 자세의 로봇 자기충돌과 이웃 블록 간섭을 사전에 "
           "계산하여 집을 수 없는 초기 배치를 제외한다. G1(파지 검측)은 집게가 닫히면 1.5 cm 들어 0.25초 정지한 뒤 식 (1)을 "
           "만족할 때만 운반을 허용하고, 불합격이면 집게를 열고 4 cm 올린 뒤 정책이 다시 시도하게 한다. G2(해제 전 검측)는 "
           "정책이 집게를 열려는 순간 개입하여, 블록 오차가 식 (2)의 기준을 넘으면 보정하고 해제는 게이트가 직접 수행한다. G3(해제 후 검측)는 해제 직후 최종 "
           "허용오차로 채점하고 불합격이면 블록당 1회에 한해 다시 집어 놓는다."),
    ]
    out["method3"] = [
        _p("식에서 θ<font size=6>jaw</font>는 집게 각도, F̄<font size=6>z</font>는 정지 구간의 손목 수직 하중 평균, "
           "m<font size=6>g</font>g는 집게 자중, e는 블록의 "
           "목표 대비 오차이다. G1은 로봇 자체 신호만 사용하지만, 재접근 안내와 G2·G3는 시뮬레이터의 정답 블록 좌표를 사용한다. 따라서 G2를 적용한 "
           "조건에서 정책은 집기와 운반을 맡고 최종 정렬과 해제는 게이트가 맡으며, 그 결과는 좌표가 완벽할 때의 상한값이다. 공정 관점에서 G1·G2는 시공자의 자체 점검에, G3는 검측 불합격 시 보완시공 후 "
           "재검측에 대응한다."),
    ]
    out["exp"] = [
        _p("3. 실험 및 결과", "h1"), _p("3.1 실험 조건", "h2"),
        _p("모든 조건에서 학습된 정책의 신경망 가중치는 같으며, 조건 간 차이는 실행 중 정책 밖에서 작동하는 검측 단계의 조합뿐이다. "
           "조건 A~D의 구성은 표 1과 같다. B는 G1 불합격 시 제자리에서 재시도하여 좌표를 쓰지 않고, C·D는 다음 블록 위로 재접근을 "
           "안내한다. 기준선 1은 전문가 스크립트를 첫 시도만 허용하여 실행한 것이고, 기준선 2는 여기에 G1~G3를 적용한 것이다."),
        _p(f"문턱값은 검증 배치 40개로 정하고, 성능은 학습·검증에 쓰지 않은 시험 배치로 측정하였다. 모든 조건에 G0를 적용하고, "
           f"조건과 기준선은 같은 배치(Diffusion {nd}개, ACT {na}개)로 짝지어 비교하였다."),
    ]
    out["results"] = [
        _p("3.2 결과", "h2"),
        _p(f"표 1에서 정책 단독(A)의 완성은 Diffusion {_pc(dA)}, ACT {_pc(aA)}였다. 좌표를 쓰지 않는 파지 검측(B)은 빈손 운반을 "
           f"막았으나 정책이 같은 자리에서 다시 헛집는 경우가 많아 완성률을 올리지 못하였다({_pc(M['diffusion'][1000]['res']['B'])}, {_pc(M['act'][1000]['res']['B'])}). 재접근 안내와 "
           f"해제 전 검측(C)을 더하면 {_pc(dC)}, {_pc(aC)}로 올랐고, 해제 후 1회 재배치(D)까지 더하면 {_pc(dD)}, {_pc(aD)}였다. "
           f"ACT는 재배치 {aD['replaced']}회 중 {aD['replaced_ok']}회가 합격하여 C와 D의 차이 대부분을 만들었으며, 주된 실패가 "
           f"파지보다 배치 정밀도임을 보여 준다. 검증 배치에서 하중 조건만으로 파지를 기각한 경우는 두 정책 모두 0건으로, 손목 "
           f"하중은 집게 각도에 추가 정보를 주지 못하였다."),
        _p(f"기준선 1은 {_pc(e1['diffusion'])}, 기준선 2는 {_pc(e2['diffusion'])}였다(Diffusion 비교 배치). 검측 단계는 동작 생성 "
           f"방식과 무관하게 완성률을 높였으며, 좌표가 완벽하게 주어지면 전문가 스크립트가 학습 정책보다 높았다. 표 2에서 D의 "
           f"완성은 좌표에 2 mm 측정 잡음만 더해도 Diffusion {_pc(N['diffusion'][0])}에서 {_pc(N['diffusion'][2])}로, ACT "
           f"{_pc(N['act'][0])}에서 {_pc(N['act'][2])}로, 4 mm에서는 {_pc(N['diffusion'][4])}, {_pc(N['act'][4])}로 떨어졌다. 학습 seed를 1001, 1002로 바꾼 두 모델에서도 A와 D를 같은 배치로 "
           f"비교한 결과, 세 seed 합산 완성은 Diffusion {_pc(M['diffusion']['pooled']['A'])}에서 {_pc(M['diffusion']['pooled']['D'])}, "
           f"ACT {_pc(M['act']['pooled']['A'])}에서 {_pc(M['act']['pooled']['D'])}로 올라 개선 경향이 모든 seed에서 유지되었다(표 1)."),
    ]
    out["conclusion"] = [
        _p("4. 결론", "h1"),
        _p("검측 단계별 측정 결과에서 얻은 건설관리 관점의 시사점은 다음과 같다."),
        _p(f"첫째, 시연 학습만으로는 조적 품질 기준을 충족하기 어렵다(정책 단독 완성 Diffusion {_pc(dA)}, ACT {_pc(aA)}). "
           f"해제 전·후 검측을 공정에 넣었을 때 {_pc(dD)}, {_pc(aD)}로 올랐으므로, 학습 기반 로봇을 도입하더라도 검측 절차는 "
           f"공정 계획에 포함되어야 한다. 둘째, 품질을 좌우한 단계는 파지가 아니라 배치였다. 한정된 검측 자원은 블록을 놓기 "
           f"직전과 직후의 검측에 우선 배정하는 것이 효과적이다. 셋째, 검측의 효과는 계측 정확도에 좌우되어 2 mm 잡음에서도 크게 "
           f"떨어졌다. 로봇 시공의 품질관리계획에는 2 mm보다 정확한 계측 수단과 그 비용이 함께 검토되어야 한다. 넷째, 재배치가 "
           f"필요했던 비율(ACT 해제 {aD['releases']}회 중 {aD['replaced']}회, Diffusion {dD['releases']}회 중 {dD['replaced']}회)은 "
           f"로봇 작업의 재작업률로서 품질 지표와 생산성 산정에 활용할 수 있다."),
        _p("본 결과는 시뮬레이션과 제한된 시험 배치에 근거하며(조건 B·C는 학습 seed 1개, A·D는 3개), C·D의 수치는 정답 좌표를 "
           "사용한 상한값이다. 향후 "
           "실제 계측 장비 수준의 오차를 반영하고 다층 벽체로 확장하여, 로봇 조적의 검측 체크리스트와 품질 기준을 구체화할 예정이다."),
    ]
    out["refs"] = [
        "건설근로자공제회 (2025). 2026년 건설근로자 수급전망, 2025.12.18.",
        "국가기술표준원. KS L 4201 점토 벽돌. [개정 연도 확인 필요]",
        "국토교통부 (2021). KCS 41 34 02:2021 벽돌공사, 국가건설기준 건축공사 표준시방서.",
        "국토교통부 (2026). 건설공사 사업관리방식 검토기준 및 업무수행지침, 국토교통부고시 제2026-360호.",
        "Chi, C., Feng, S., Du, Y., Xu, Z., Cousineau, E., Burchfiel, B., and Song, S. (2023). \"Diffusion Policy: Visuomotor "
        "Policy Learning via Action Diffusion.\" Robotics: Science and Systems.",
        "Gao, J. and Adel, A. (2026). \"Adaptive Human-Robot Collaboration for Masonry Construction Under Material and Assembly "
        "Uncertainty.\" Proceedings of the 43rd ISARC.",
        "Ibrahimov, R., Mozaffari, S., and Adel, A. (2026). \"Contact-Rich Robotic Manipulation in Construction via Zero-Shot "
        "Learning: A Diffusion Policy-Guided Adaptive Control.\" arXiv:2608.22100.",
        "Wienerberger (2026). Telford Brindle Product Data, <https://www.wienerberger.co.uk> (2026.9.28.).",
        "Xu, C., Xu, Y., Xue, M., Lin, J., Wang, J., Zhang, X., Wang, Y., and Yu, J. (2026). \"The Curse of Precision: A Data "
        "Scaling Law for High-Precision Robotic Manipulation.\" IEEE ICRA.",
        "Yang, Y., Chen, L., Song, Z., Chen, Y., Sun, W., Zhou, Z., Xiong, R., and Wang, Y. (2025). \"Disambiguate Gripper State "
        "in Grasp-Based Tasks: Pseudo-Tactile as Feedback Enables Pure Simulation Learning.\" IEEE/RSJ IROS.",
        "Yu, J., Li, B., Tang, Z., Lu, G., Hu, C., Liu, R., and Liu, C. (2026). \"BrickCraft: Visuomotor Skill Composition with "
        "Situated Manual Guidance for Long-Horizon Interlocking Brick Assembly.\" arXiv:2605.07605.",
        "Zhao, T. Z., Kumar, V., Levine, S., and Finn, C. (2023). \"Learning Fine-Grained Bimanual Manipulation with Low-Cost "
        "Hardware.\" Robotics: Science and Systems.",
        "Zheng, G., Seenivasan, S., Johnson-Roberson, M., and Zhi, W. (2026). \"Rewind-IL: Online Failure Detection and State "
        "Respawning for Imitation Learning.\" arXiv:2604.16683.",
    ]
    return out
