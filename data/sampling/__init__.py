"""다각도 학습에서 사진을 선택하는 실험용 샘플링 함수를 제공한다.

각도 균형 랜덤 12장: 같은 사과의 촬영 사진에서 epoch마다 다른 12장을 골라 관측 각도를 바꾸는
학습 증강이다. 사과 수를 늘리는 것이 아니다.

선택 규칙 (``angle_balanced.select_angle_balanced_random_views``):
    1. 프레임을 top·bottom 촬영면으로 나누고, 둘 다 있으면 6장씩 배분한다.
    2. 촬영면별로 수평각 순서로 정렬해 연속 각도 구간으로 나누고 구간마다 한 장을 고른다.
    3. 난수는 ``seed + epoch + group_no``의 SHA-256으로 만든다. 같은 입력이면 같은 12장이다.
    4. 한 촬영면만 있으면 그 촬영면 전체에서, 12장 미만이면 전부 쓰고 부족분은 마스킹한다.

누수 방지: 모든 조합은 원래 ``group_no``와 fold를 유지하고, 랜덤 선택은 학습 데이터에만 쓴다.
Validation·source·Test는 고정 12장을 유지한다. 179개 사과 기준 seed 42의 1~3 epoch에서 그룹당
서로 다른 프레임은 평균 30.56장(최소 8, 최대 36)이었다.

후속 실험 (``experiments``): v2 설정을 유지하고 샘플링만 바꿔 5-fold 5회 + source 1회를 비교한다.
    python -m data.sampling.experiments            # 계획만 생성
    python -m data.sampling.experiments --execute  # 학습 시작
2026-09-23 사용자 요청으로 중단했고 v2를 유지한다. 기록은 ``docs/wbs/[DM-06] 모델·입력 장수 비교.md``.
"""

from .angle_balanced import select_angle_balanced_random_views

__all__ = ["select_angle_balanced_random_views"]
