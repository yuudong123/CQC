"""CQC 모델 학습·실험 비교·평가·패키징을 위한 공통 함수 패키지다.

데이터 로더와 모델 본체는 ``src.data``, ``src.models``를 가져와 쓰고, 일회성 실험 흐름은
``notebooks/``, 원격 GPU 실행용 PowerShell은 ``scripts/remote/``에 둔다. 산출물은 Git에서
제외되는 ``outputs/`` 아래에 저장한다. 실험 결과와 선택 근거는 ``docs/wbs/[DM-05~09]``에 적는다.

주요 모듈:
    train                 단일 fold 학습 (4·8·12·16·40장, joint·separate·separate_brix)
    engine                epoch 실행, Accuracy·Macro F1·혼동행렬, 체크포인트 저장
    models                joint·separate·가상 당도 결합 모델 생성
    experiments / audit / summarize / report
                          2구조 × 5장수 × 5-fold 50회 계획·검사·집계·비교표
    improvement_experiments / improvement_report
                          v2 손실·정규화 4종 24회 계획과 공통 epoch 강건 후보 선정
    brix_experiments / brix_report
                          이미지 단독과 가상 당도 결합 48회 계획·비교
    final_fit             공통 epoch 기준으로 Test 제외 개발 데이터 전체 최종 학습
    evaluate              고정 Test 1회 평가 (확인 문구·잠금 표식 필요)
    export_predictions / thresholds
                          검증 fold 확률 CSV와 품종·품질 신뢰도 기준 탐색
    package_model / model_card
                          체크포인트 패키징(SHA-256)과 모델 카드 생성
    benchmark / benchmark_concurrency / acceptance_cpu
                          CPU·GPU 지연·처리량 측정, 서버컴 합성 입력 수용시험

실행 예:
    python -m src.data.virtual_brix                       # 가상 당도 CSV 생성
    python -m src.training.brix_experiments               # 계획만 생성
    python -m src.training.brix_experiments --device cuda --execute
    python -m src.training.brix_report

안전 장치:
    - experiments·improvement_experiments·brix_experiments·final_fit은 기본적으로 계획 JSON만
      만들고 ``--execute``가 있어야 학습한다. brix_experiments는 완료된 run을 ``summary.json``
      기준으로 건너뛰며, 다시 돌릴 때만 ``--rerun-completed``를 붙인다.
    - 최종 Test는 ``--confirm-final-test RUN_FINAL_TEST_ONCE``가 없으면 거부하고, 실행한
      체크포인트 옆에 잠금 표식을 남겨 재실행을 막는다.
    - 모델·epoch·임계값 선택에는 고정 Test를 쓰지 않는다. 5-fold와 원본 Validation(source)만 쓴다.
    - 최종 epoch는 fold별 최고값 중앙값이 아니라 같은 epoch끼리 평균한 검증 점수로 정한다.
    - 40장 입력은 기본 batch size를 1로 낮춘다.
    - 가상 당도는 RGB에서 만든 시연값이다. 결합 모델의 결과를 실측 당도 성능으로 해석하지 않는다.
"""
