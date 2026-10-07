"""Body text of the KICEM 2026 student paper (construction-management angle): inspection, rework and work time.

Differs from the KSARC abstract (stage-wise completion rate): the question here is how often each inspection step
intervenes, how much rework it triggers and what it costs in work time.  Completion rates appear only as context and
are cited to the KSARC abstract (정원영 외, 2026).
Structure (advisor): 1 서론 (배경, 문제 정의, 목적, 제안 방법, 검증 계획, 결과, 예상 기여) / 2 제안 방법 / 3 실험 (환경 세팅,
평가 방법, 결과) / 4 고찰 / 5 결론.  Section 2 holds no environment values and no results.
"""
from decimal import Decimal, ROUND_HALF_UP

DJ = lambda c: f"<font name='DJ'>{c}</font>"
TH = DJ("θ")


def pc(k, n):
    return f"{int((Decimal(100 * k) / Decimal(n)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}%"


def hu(v):
    """Fraction -> percent, 0.5 rounded up (same rule as pc)."""
    return f"{int((Decimal(str(100 * v))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}%"


def text(T, m, P):
    dB, dC, dD = T["diffusion_B"], T["diffusion_C"], T["diffusion_D"]
    aB, aC, aD = T["act_B"], T["act_C"], T["act_D"]
    g2 = lambda x: pc(x["g2_corrected"], x["placements"])
    g3 = lambda x: pc(x["g3_failed"], x["placements"])
    share = lambda x: hu(x["recover_time_share"])
    tw = lambda x: f"{x['time_per_accepted_wall_s']:.0f}초"
    lo_hi = lambda a, b, f: f"{f(a)}~{f(b)}" if a <= b else f"{f(b)}~{f(a)}"
    bshare = lo_hi(aB["recover_time_share"], dB["recover_time_share"], hu)
    g2rng = lo_hi(dD["g2_corrected"] / dD["placements"], aD["g2_corrected"] / aD["placements"], hu)
    rep_all = aD["replaced"] + dD["replaced"]
    rep_ok = aD["replaced_ok"] + dD["replaced_ok"]
    rep_s = aD["replace_s"]["median"]
    fin_d, fin_a = dD["finish_s"]["median"], aD["finish_s"]["median"]
    # every comparative sentence below is checked against the data
    assert aD["time_per_accepted_wall_s"] < aC["time_per_accepted_wall_s"]
    assert dD["time_per_accepted_wall_s"] <= dC["time_per_accepted_wall_s"]
    assert dB["recover_time_share"] > dC["recover_time_share"] and aB["recover_time_share"] > aC["recover_time_share"]
    assert aC["g3_failed"] / aC["placements"] > dC["g3_failed"] / dC["placements"]
    assert dB["grasp_rejected"] / dB["grasp_checks"] >= dC["grasp_rejected"] / dC["grasp_checks"] - 0.05
    assert aB["grasp_rejected"] / aB["grasp_checks"] >= aC["grasp_rejected"] / aC["grasp_checks"] - 0.05
    assert aD["time_per_accepted_wall_s"] > 2 * aD["finish_s"]["median"] and dD["time_per_accepted_wall_s"] > 2 * dD["finish_s"]["median"]
    nre, nmis = T["rerun_total"], len(T["rerun_mismatch"])
    out = {}

    out["abstract"] = (
        "본 연구의 목적은 모방학습 조적 로봇에 시공 품질관리 절차에 대응하는 검측과 보완시공 단계를 두었을 때 발생하는 검측 개입, "
        "불합격, 재시공의 빈도와 그에 드는 작업시간을 정량화하는 것이다. 학습된 정책 밖에 자재 취급 확인, 시공 중 검측, 시공 후 "
        "검측과 1회 보완시공을 두고, 벽돌 3개를 2단으로 쌓는 물리 시뮬레이션에서 두 정책의 검측 기록을 분석하였다. 그 결과 시공 중 "
        f"검측은 배치의 {g2(dD)}(Diffusion Policy)와 {g2(aD)}(ACT)에서 개입하였고, 보완시공 {rep_all}건 중 {rep_ok}건이 합격하였다. "
        f"보완시공은 1회에 약 {rep_s:.0f}초가 들었으나 ACT가 합격 벽체 하나를 얻는 데 드는 시간을 {tw(aC)}에서 {tw(aD)}로 줄였다. "
        f"반면 자재 취급 확인만 두었을 때는 작업시간의 {bshare}가 헛집기 복구에 쓰였다. 이는 로봇 시공의 "
        "품질관리계획에서 시공 중 검측을 상시 두고 불합격에 대한 보완 수단을 함께 계획해야 하며, 로봇의 생산성을 산정할 때 검측과 "
        "재작업의 시간을 포함해야 함을 보여준다.")

    def flow(fig):
        s = []
        # ------------------------------------------------------------------------------------------ 1 서론
        s += [P("1. 서론", "h1"), P("1.1 연구 배경", "h2"),
              P("국내 건설기능인력은 2026년 수요에 비해 약 30만 명이 부족할 것으로 전망되며(건설근로자공제회, 2025), 조적은 반복 "
                "작업과 중량물 취급이 겹쳐 일찍부터 로봇화가 시도된 공종이다(Bock, 2015). 로봇이 시공을 맡더라도 품질관리의 원칙은 "
                "같다. 현행 지침은 시공자가 먼저 점검하고 검측을 받으며, 불합격이면 보완시공 후 재검측을 받도록 정하고 있다"
                "(국토교통부, 2026). 이 절차는 품질을 확보하는 대신 공정에 시간을 더하고, 재작업은 건설 프로젝트의 비용과 공기 "
                "초과를 일으키는 주요 원인으로 보고되어 왔다(Love, 2002; Hwang et al., 2009). 그래서 검측을 어느 단계에서 몇 번 "
                "할지는 품질과 공기를 함께 따져 공정계획 단계에서 정한다."),
              P("로봇 조적의 제어 방식도 바뀌고 있다. 기존 조적 로봇은 계측과 보정 절차를 사람이 설계하여(Giftthaler et al., "
                "2017; Gao and Adel, 2026) 벽돌 규격이나 작업 조건이 바뀔 때마다 재설정이 필요하였다. 시연을 모방하여 영상에서 "
                "곧바로 동작을 출력하는 모방학습(Zhao et al., 2023; Chi et al., 2023)은 이 부담을 줄이는 대안이며, 철근망 "
                "조립(Sun et al., 2026)과 목재 접합(Ibrahimov et al., 2026) 같은 건설 작업에도 적용되었다."),
              P("1.2 문제 정의", "h2"),
              P("모방학습 정책은 성공한 시연만으로 학습하므로 불량을 스스로 인지하지 못한다. 집기에 실패하고도 운반을 계속하거나"
                "(Yang et al., 2025) 어긋나게 놓은 블록을 그대로 둔다. 이에 정책 밖에서 실패를 감지하여 다시 실행하거나(Zheng et "
                "al., 2026) 단계마다 조건을 확인하는 방법(Yu et al., 2026)이 제안되었고, 조적 로봇에서도 검측 단계를 더하면 "
                "완성률이 높아짐이 보고되었다(정원영 외, 2026). 학습 기반 로봇 시공에도 사람의 시공과 같이 검측과 보완시공이 "
                "필요한 것이다."),
              P("그러나 이 연구들은 검측의 효과를 성공률로만 보고하며, 검측이 몇 번 개입하였고 불합격과 재시공이 얼마나 "
                "발생하였으며 그에 시간이 얼마나 들었는지는 다루지 않는다. 이 공백은 건설관리에서 세 가지 판단을 막는다. 첫째, 로봇의 "
                "생산성을 산정할 수 없다. 성공률이 같아도 검측과 재시공에 드는 시간이 다르면 단위 작업의 소요시간이 달라지므로, "
                "성공률만으로는 로봇 도입이 공기에 미치는 효과를 판단할 수 없다. 둘째, 검측을 어디에 배치할지 정할 수 없다. 로봇의 "
                "자동 검측도 계측 장비와 시간을 소모하므로 모든 단계를 같은 수준으로 검측할 수는 없는데, 불량이 어느 단계에 집중되는지 "
                "모르면 상시 검측할 단계와 생략할 단계를 가릴 수 없다. 셋째, 보완시공의 허용 범위를 정할 수 없다. 모르타르 위의 "
                "벽돌은 굳기 전에만 다시 놓을 수 있으므로 재시공의 횟수와 시간은 제한되어야 하는데, 재시공이 얼마나 성공하고 시간이 "
                "얼마나 드는지 모르면 이 한도를 근거 있게 정할 수 없다."),
              P("1.3 연구 목적", "h2"),
              P("본 연구의 목적은 모방학습 조적 로봇에 시공 품질관리 절차에 대응하는 검측과 보완시공 단계를 두고, 단계별 검측 "
                "개입, 불합격, 재시공의 빈도와 그에 따른 작업시간을 정량화하여 로봇 시공의 검측 계획과 생산성 산정에 필요한 근거를 "
                "제시하는 것이다. 이를 위해 세 가지를 확인한다. 첫째, 각 검측 단계는 공정 중 얼마나 자주 개입하는가. 둘째, 불합격 "
                "후 보완시공은 얼마나 성공하며 시간이 얼마나 드는가. 셋째, 검측과 보완시공을 더하면 합격한 벽체 하나를 얻는 데 드는 "
                "시간은 늘어나는가, 줄어드는가."),
              P("1.4 제안 방법", "h2"),
              P("현행 검측 절차를 로봇 공정에 대응시킨 세 검측 단계, 곧 자재 취급 확인(G1), 시공 중 검측(G2), 시공 후 검측과 "
                "보완시공(G3)을 학습된 정책 밖에 둔다. 그리고 이 단계들이 남기는 기록에서 검측 개입률, 시공 후 불합격률, 보완시공 "
                "성공률, 합격 벽체당 투입 시간을 산출하는 평가 체계를 제안한다. 검측을 정책 밖에 두므로 정책을 다시 학습하지 않고도 "
                "검측 수준만 바꾸어 비교할 수 있다."),
              P("1.5 검증 계획", "h2"),
              P("벽돌 3개를 2단으로 쌓는 물리 시뮬레이션에서, 같은 시연으로 학습한 두 정책(ACT, Diffusion Policy)에 검측 수준을 "
                "달리한 조건을 같은 초기 배치로 적용하고, 각 실행의 검측 기록에서 위 지표를 산출하여 비교한다."),
              P("1.6 연구 결과", "h2"),
              P(f"시공 중 검측은 배치의 {g2(dD)}(Diffusion Policy)와 {g2(aD)}(ACT)에서 개입하였다. 시공 후 불합격은 ACT에 집중되었고, "
                f"보완시공 {rep_all}건 중 {rep_ok}건이 합격하였다. 보완시공은 1회에 약 {rep_s:.0f}초가 들었지만 ACT의 합격 벽체당 투입 "
                f"시간을 {tw(aC)}에서 {tw(aD)}로 줄였다. 자재 취급 확인만 둔 조건에서는 작업시간의 {bshare}가 헛집기 "
                "복구에 쓰였다."),
              P("1.7 예상 기여", "h2"),
              P("학술적으로는 학습 기반 시공 로봇의 평가를 성공률에서 검측 개입, 재작업, 작업시간을 포함한 품질비용의 관점으로 "
                "넓히는 지표 체계를 제시한다. 실무적으로는 로봇 시공의 품질관리계획을 세울 때 상시 검측할 단계를 고르고, 보완시공의 "
                "허용 횟수를 정하며, 검측과 재작업의 시간을 반영하여 로봇의 생산성을 산정하는 근거를 제공한다.")]
        # ------------------------------------------------------------------------------------------ 2 제안 방법
        s += [P("2. 제안 방법", "h1"), P("2.1 검측 단계와 시공 품질관리 절차의 대응", "h2"),
              P("학습된 정책은 카메라 영상과 관절값을 입력받아 관절 목표값을 출력하며, 검측 단계는 이 출력과 로봇 사이에서 동작한다"
                "(그림 1). 각 단계는 현행 검측 절차의 한 과정에 대응한다. 작업 전에는 로봇이 집을 수 없는 초기 배치를 제외하는 "
                "실행가능성 검토(G0)를 둔다. 이는 시공 전 작업 여건의 검토에 해당하며, 집을 수 없는 배치가 남아 있으면 정책의 실패와 "
                "작업 여건의 실패를 구분할 수 없기 때문이다."),
              fig["gate_figure"](),
              P("G1(자재 취급 확인)은 자재를 들어 올린 직후 제대로 잡았는지 확인하는 단계로, 시공자의 자체 점검에 해당한다. "
                "불합격이면 자재를 운반하지 않고 다시 집게 한다. G2(시공 중 검측)는 정책이 블록을 놓으려는 순간 잡고 있는 블록의 "
                "위치를 측정하고, 기준을 넘으면 오차를 보정한 뒤 놓는다. 놓기 전에 오차를 없애는 자체 점검이다. G3(시공 후 검측과 "
                "보완시공)는 놓은 직후의 블록을 허용오차로 판정하고, 불합격이면 그 블록을 다시 집어 놓는다. 불합격 후 보완시공과 "
                "재검측에 해당하며, 모르타르가 굳기 전에만 다시 놓을 수 있으므로 블록당 1회로 제한한다."),
              P("2.2 검측 판정 기준", "h2"),
              P("G1은 손을 일정 높이 들어 잠시 정지한 뒤 식 (1)을 만족할 때만 운반을 허용한다. 자재의 무게는 바닥에서 떨어진 뒤에야 "
                "하중으로 나타나므로, 집게를 닫는 순간이 아니라 들어 올린 뒤에 판정한다."),
              fig["eq1"](),
              P(f"{TH}<sub>jaw</sub>는 집게 관절각, F<sub>z</sub>는 정지 구간의 손목 수직 하중 평균, m<sub>g</sub>g는 집게의 "
                f"자중이다. 각도 기준 {TH}<sub>th</sub>는 블록을 물었을 때와 빈손일 때의 집게 각도 사이에, 하중 기준 F<sub>th</sub>는 "
                "블록 무게의 절반으로 둔다. G2는 식 (2)에 해당하면 보정한다."),
              fig["eq2"](),
              P(f"e<sub>xy</sub>, e<sub>{DJ('ψ')}</sub>, e<sub>z</sub>는 목표 대비 블록의 수평 위치, 방향, 높이 오차이다. G2의 위치 "
                "기준은 최종 허용오차보다 작게 두는데, 놓는 순간 블록이 밀리는 양만큼 여유가 필요하기 때문이다. G3는 최종 "
                "허용오차, 곧 위치, 높이, 방향, 기울기의 기준으로 판정한다."),
              P("2.3 품질과 작업시간 지표", "h2"),
              P("검측 단계는 판정이 일어날 때마다 시각과 결과를 기록한다. 이 기록에서 다음 지표를 산출한다. 품질 측면에서 파지 "
                "기각률은 전체 파지 판정 중 G1이 불합격으로 판정한 비율, 시공 중 검측 개입률은 전체 배치 중 G2가 보정한 비율, 시공 후 "
                "불합격률은 전체 배치 중 G3가 불합격으로 판정한 비율, 보완시공 성공률은 재시공 중 재검측에 합격한 비율이다."),
              P("시간 측면에서 복구 시간은 G1 불합격부터 다음 합격 파지까지의 시간이고, 그 합을 전체 작업시간으로 나누어 복구 시간 "
                "비중을 구한다. 보완시공 시간은 처음 놓은 시각부터 다시 놓은 시각까지이고, 완성 시간은 마지막 블록을 합격 상태로 놓은 "
                "시각이다. 합격 벽체당 투입 시간은 모든 실행에 투입한 시간의 합을 완성된 벽체 수로 나눈 값이며, 완성하지 못한 실행은 "
                "작업 제한 시간 전체를 투입한 것으로 본다. 불량 벽체에 쓴 시간도 생산에 투입된 시간이기 때문이다. 이 값은 검측과 "
                "재작업의 시간, 그리고 그로 인한 품질 향상을 하나의 생산성 지표로 묶는다.")]
        # ------------------------------------------------------------------------------------------ 3 실험
        s += [P("3. 실험", "h1"), P("3.1 실험 환경 세팅", "h2"),
              P("실험은 물리 시뮬레이터 MuJoCo(Todorov et al., 2012)에서 수행하였다(그림 2). 물리 계산 간격은 1 ms, 제어 주기는 "
                "20 Hz이다. 로봇은 팔 관절 5개와 집게 관절 1개를 가진 저가 개방형 로봇팔 SO-ARM100이며, G1의 하중 판정을 위해 "
                "손목에 힘 센서를 두었다."),
              fig["task_figure"](),
              P("벽돌은 KS L 4201의 표준형 190×90×57 mm(국가기술표준원, 2022)를 긴 변 90 mm로 축소한 90×42.6×27 mm, 무게 "
                "1.83 N이다. 가로줄눈은 KCS 41 34 02의 줄눈 너비 10 mm(국토교통부, 2021)를 같은 축척으로 줄인 4.7 mm 두께의 층으로 "
                "두었고, 놓인 벽돌은 2초간 정지하면 고정되어 모르타르의 경화를 대신한다. 초기 배치는 위치 ±30 mm, 방향 ±60° "
                "범위에서 무작위로 정하였다."),
              P("시연은 정답 좌표로 경로를 계산하는 스크립트로 생성하였고, 첫 시도에 세 벽돌을 모두 허용오차 안에 놓은 240개 중 200개로 "
                "ACT(Zhao et al., 2023)와 Diffusion Policy(Chi et al., 2023)를 학습하였다. 두 정책은 카메라 3대의 영상과 관절값 6개를 "
                f"입력받으며 0.5초마다 다시 관측한다. 검측 기준값은 {TH}<sub>th</sub> 0.2 rad(블록을 물었을 때 약 0.31 rad, 빈손일 때 "
                "-0.12 rad), F<sub>th</sub> 0.9 N, 들어 올리는 높이 1.5 cm와 정지 0.25초, G2 기준 2.5 mm·3°·3 mm로 두었고, 이 값은 "
                "시험과 별도인 검증 배치 40개에서 정하였다. G1 불합격 시 G1만 둔 조건에서는 제자리에서 손을 4 cm 올리고, G2를 둔 "
                "조건에서는 다음 블록 위로 손을 옮겨 다시 시도하게 한다. G2와 G3의 위치는 시뮬레이터의 정답 좌표로 측정하였다."),
              P("3.2 평가 방법", "h2"),
              P("검측 수준을 표 1의 네 조건으로 나누었다. 모든 조건에서 정책의 가중치는 같고 검측 단계만 다르다. 정책 단독(A)은 "
                "정책이 끝을 알리지 않아 완성 시각이 기록되지 않으므로 시간 지표에서 제외하고, 품질 비교의 기준으로만 쓴다."),
              fig["t_cond"](),
              P("최종 합격 기준은 세 벽돌 모두 설계 위치에서 중심 4.5 mm, 방향 5°, 기울기 10° 이내이다. 위치 기준은 실척으로 "
                "9.5 mm이며 세로줄눈 두께와 벽면 직진도의 허용오차(Porter, 2017; LABC, 2021)에 해당한다. G3는 이에 높이 3 mm를 더하고 "
                "기울기를 5°로 엄격히 하여 판정한다. 작업 제한 시간은 실행당 90초이고, 시간은 시뮬레이션의 제어 시간이다."),
              P("시험에는 학습과 검증에 쓰지 않은 초기 배치를 사용하고, 모든 조건이 실행을 마친 같은 배치끼리 짝지어 비교하였다"
                f"(Diffusion Policy {dD['paired_total']}개, ACT {aD['paired_total']}개, 학습 seed 1000 모델). 원래 시험에서 판정 기록 "
                f"파일이 남지 않은 배치는 같은 명령과 난수로 다시 실행하여 기록을 얻었다. 다시 실행한 {nre}회 중 {nre - nmis}회는 "
                f"완성 여부가 원래 시험과 같았고 {nmis}회는 GPU 연산의 비결정성으로 달랐다. 본 논문의 지표는 모두 판정 기록이 있는 "
                "실행에서 계산하였다."),
              P("3.3 결과", "h2"),
              P(f"품질 지표는 표 2와 같다. 시공 중 검측(G2)은 조건 D에서 Diffusion Policy 배치의 {g2(dD)}, ACT 배치의 {g2(aD)}에서 "
                f"개입하였다. 보정 없이 놓아도 되는 경우가 드물었다는 뜻이다. 시공 후 불합격률은 보완시공이 없는 조건 C에서 ACT "
                f"{g3(aC)}, Diffusion Policy {g3(dC)}였다. 조건 D의 보완시공은 ACT {aD['replaced']}건 중 {aD['replaced_ok']}건, Diffusion "
                f"Policy {dD['replaced']}건 중 {dD['replaced_ok']}건이 재검측에 합격하였다. G1만 둔 조건 B의 파지 기각률은 Diffusion "
                f"Policy {pc(dB['grasp_rejected'], dB['grasp_checks'])}, ACT {pc(aB['grasp_rejected'], aB['grasp_checks'])}로, G1 불합격 "
                f"뒤 다음 블록으로 안내하는 조건 C의 {pc(dC['grasp_rejected'], dC['grasp_checks'])}, {pc(aC['grasp_rejected'], aC['grasp_checks'])}"
                "와 비슷하거나 높았다."),
              fig["t_quality"](),
              P(f"시간 지표는 표 3, 그림 3과 같다. 완성된 실행의 완성 시간 중앙값은 조건 D에서 Diffusion Policy {fin_d:.1f}초, ACT "
                f"{fin_a:.1f}초였고, 보완시공 1회에는 중앙값 {rep_s:.1f}초가 더 들었다. 합격 벽체당 투입 시간은 ACT가 조건 C의 "
                f"{tw(aC)}에서 D의 {tw(aD)}로, Diffusion Policy가 {tw(dC)}에서 {tw(dD)}로 줄었다. 조건 B에서는 작업시간 가운데 "
                f"헛집기 복구에 쓰인 비중이 Diffusion Policy {share(dB)}, ACT {share(aB)}로, 조건 C의 {share(dC)}, {share(aC)}보다 "
                "컸다."),
              fig["t_time"](), fig["time_figure"]()]
        # ------------------------------------------------------------------------------------------ 4 고찰
        s += [P("4. 고찰", "h1"),
              P("첫째, 시공 중 검측은 생략할 수 없는 상시 검측이었다. 두 정책 모두 다수의 배치에서 놓기 직전 보정이 필요하였고, "
                "특히 ACT는 거의 모든 배치에서 보정을 받았다. 학습 정책이 허용오차 안으로 스스로 놓기를 기대하기 어려우므로, "
                "품질관리계획에서는 배치 직전의 위치 측정과 보정을 매 배치마다 두어야 한다."),
              P("둘째, 보완시공은 품질뿐 아니라 생산성도 높였다. 재시공은 1회마다 시간이 들지만 불합격 벽체를 합격으로 바꾸어 "
                "합격 벽체당 투입 시간을 줄였다. 불량을 남기는 데 쓴 시간이 재시공에 쓴 시간보다 컸기 때문이다. 다만 효과의 크기는 "
                "정책에 따라 달랐다. 시공 후 불합격이 잦은 ACT에서는 크게 줄었고, 불합격이 드문 Diffusion Policy에서는 작았다. "
                "보완시공의 허용 여부와 횟수는 사용할 정책의 시공 후 불합격률을 먼저 측정한 뒤 정하는 것이 타당하다."),
              P("셋째, 보완 수단이 없는 검측은 공기만 늘렸다. G1만 둔 조건에서는 빈손 운반은 막았으나 정책이 같은 자리에서 "
                "헛집기를 되풀이하여 작업시간의 상당 부분이 복구에 쓰였다. 불합격을 알아내는 것만으로는 부족하고, 다시 시도할 위치 "
                "정보처럼 불합격을 해소할 수단이 함께 계획되어야 검측이 품질로 이어진다."),
              P("넷째, 성공률만으로는 생산성을 판단할 수 없다. 완성된 실행만 보면 벽체 하나에 수십 초가 걸렸지만, 실패한 실행에 쓴 "
                "시간까지 포함한 합격 벽체당 투입 시간은 그보다 몇 배 컸다. 로봇 도입의 공기 효과를 검토할 때는 완성 시간이 아니라 "
                "검측, 재작업, 실패에 쓴 시간을 포함한 투입 시간을 써야 한다."),
              P("본 연구의 한계는 다음과 같다. 결과는 벽돌 3개를 쌓는 축소 모형의 시뮬레이션에서 얻었고, 시간은 시뮬레이션의 제어 "
                "시간이므로 실제 공기가 아니라 조건 간의 상대 비교로 해석해야 한다. G2와 G3는 정답 좌표를 사용하였으므로 계측 오차가 "
                "있는 현장에서는 개입과 재시공이 더 늘어날 수 있다. 합격 벽체당 투입 시간은 작업 제한 시간의 설정에 영향을 받으며, "
                "학습 seed 하나의 모델로 측정하였다.")]
        # ------------------------------------------------------------------------------------------ 5 결론
        s += [P("5. 결론", "h1"),
              P("본 연구는 모방학습 조적 로봇에 시공 품질관리 절차에 대응하는 검측과 보완시공 단계를 두고, 단계별 검측 개입, 불합격, "
                f"재시공의 빈도와 작업시간을 정량화하였다. 시공 중 검측은 배치의 {g2rng}에서 개입하였고, 보완시공은 "
                f"{rep_all}건 중 {rep_ok}건이 합격하였으며, 1회 약 {rep_s:.0f}초의 시간으로 ACT의 합격 벽체당 투입 시간을 {tw(aC)}에서 "
                f"{tw(aD)}로 줄였다. 반면 보완 수단 없이 자재 취급만 확인하면 작업시간의 {bshare}가 복구에 쓰였다."),
              P("따라서 학습 기반 조적 로봇의 품질관리계획에는 시공 중 검측을 상시 두고, 불합격을 해소할 보완시공 수단과 그 허용 "
                "횟수를 함께 정하며, 생산성 산정에는 검측과 재작업의 시간을 포함해야 한다. 향후에는 정답 좌표를 영상 기반 계측으로 "
                "대체하고 다층 벽체로 확장하여 검측 비용을 포함한 로봇 조적의 공정계획 방법을 구체화할 예정이다.")]
        return s

    out["flow"] = flow
    out["refs"] = [
        "건설근로자공제회 (2025). 2026년 건설근로자 수급전망.",
        "국가기술표준원 (2022). KS L 4201 점토 벽돌.",
        "국토교통부 (2021). KCS 41 34 02 벽돌공사, 건축공사 표준시방서.",
        "국토교통부 (2026). 건설공사 사업관리방식 검토기준 및 업무수행지침, 국토교통부고시 제2026-360호.",
        "정원영, 강현준, 김홍조 (2026). \"모방학습 조적 로봇의 파지·배치 검측 단계별 효과.\" 한국건설자동화로보틱스학회 "
        "정기학술대회 초록.",
        "Bock, T. (2015). \"The Future of Construction Automation: Technological Disruption and the Upcoming Ubiquity of "
        "Robotics.\" Automation in Construction, 59, pp. 113-121.",
        "Chi, C., Feng, S., Du, Y., et al. (2023). \"Diffusion Policy: Visuomotor Policy Learning via Action Diffusion.\" "
        "Robotics: Science and Systems.",
        "Gao, J. and Adel, A. (2026). \"Adaptive Human-Robot Collaboration for Masonry Construction Under Material and Assembly "
        "Uncertainty.\" Proc. of the 43rd ISARC.",
        "Giftthaler, M., Sandy, T., D<font name='DJ'>ö</font>rfler, K., et al. (2017). \"Mobile Robotic Fabrication at 1:1 Scale: "
        "the In situ Fabricator.\" Construction Robotics, 1, pp. 3-14.",
        "Hwang, B.-G., Thomas, S. R., Haas, C. T., and Caldas, C. H. (2009). \"Measuring the Impact of Rework on Construction "
        "Cost Performance.\" Journal of Construction Engineering and Management, 135(3), pp. 187-198.",
        "Ibrahimov, R., Mozaffari, S., and Adel, A. (2026). \"Contact-Rich Robotic Manipulation in Construction via Zero-Shot "
        "Learning: A Diffusion Policy-Guided Adaptive Control.\" arXiv:2608.22100.",
        "LABC Warranty (2021). Technical Manual Version 10, Section 1 Tolerances.",
        "Love, P. E. D. (2002). \"Influence of Project Type and Procurement Method on Rework Costs in Building Construction "
        "Projects.\" Journal of Construction Engineering and Management, 128(1), pp. 18-29.",
        "Porter, G. (2017). The Acceptability of Masonry, Masonry Advisory Council.",
        "Sun, T., Han, B., Wu, J., Rusinkiewicz, S., and Shao, Y. (2026). \"Mobile Robotic Rebar Cage Assembly via Imitation "
        "Learning.\" Automation in Construction, 181, 106671.",
        "Todorov, E., Erez, T., and Tassa, Y. (2012). \"MuJoCo: A Physics Engine for Model-Based Control.\" IEEE/RSJ IROS, "
        "pp. 5026-5033.",
        "Yang, Y., Chen, L., Song, Z., et al. (2025). \"Disambiguate Gripper State in Grasp-Based Tasks: Pseudo-Tactile as "
        "Feedback Enables Pure Simulation Learning.\" IEEE/RSJ IROS.",
        "Yu, J., Li, B., Tang, Z., et al. (2026). \"BrickCraft: Visuomotor Skill Composition with Situated Manual Guidance for "
        "Long-Horizon Interlocking Brick Assembly.\" arXiv:2605.07605.",
        "Zhao, T. Z., Kumar, V., Levine, S., and Finn, C. (2023). \"Learning Fine-Grained Bimanual Manipulation with Low-Cost "
        "Hardware.\" Robotics: Science and Systems.",
        "Zheng, G., Seenivasan, S., Johnson-Roberson, M., and Zhi, W. (2026). \"Rewind-IL: Online Failure Detection and State "
        "Respawning for Imitation Learning.\" arXiv:2604.16683.",
    ]
    return out
