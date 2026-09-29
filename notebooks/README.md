# 데이터 파트 노트북

| 순서 | 노트북 | 작업 |
| --- | --- | --- |
| 01 | [데이터 준비](01_data_preparation.ipynb) | 매니페스트, 이미지 무결성, 사과 단위 분할 |
| 02 | [모델 비교](02_training_comparison.ipynb) | 모델·뷰 수 비교, 개선 실험, 결과 비교 |
| 03 | [가상 당도 실험](03_virtual_brix_experiments.ipynb) | 당도 생성, 결합 실험, 상품등급 학습·CV·진단 |
| 04 | [모델 검증](04_model_verification.ipynb) | 평가 절차, 재사용 Test 진단, 패키지 검사 |
| 05 | [시연 데이터](05_demo_bundles.ipynb) | 묶음 생성, 출처·SHA 검증, 당도 연결 |

VS Code의 Jupyter 확장이나 JupyterLab에서 프로젝트의 Python 커널을 선택하고 위에서부터 읽는다. PyTorch·torchvision·Pillow·API 의존성은 `requirements-inference.txt`를 참고한다. 그래프 생성에는 matplotlib, 노트북 커널에는 ipykernel이 필요하다.

실행 셀의 `RUN_...`은 기본 `False`다. 필요한 단계만 켜고 출력 경로를 확인한다. 번호는 읽는 순서이며 기존 실험을 모두 재실행할 필요는 없다. GPU 학습은 GPU 작업 환경에서 실행한다. 기존 데이터와 평가 증거를 보존하도록 새 출력 경로를 사용한다.

일회성 Python 파일 9개의 함수 본문은 03~05 노트북으로 옮겼다. 셀에서 경로 등 이름 있는 인자를 지정해 실행한다. 상품등급 CV도 같은 노트북의 학습 함수를 호출한다.

`src/data`, `src/models`, `src/training`, `data/sampling`의 재사용 함수는 추론 서버·학습·테스트가 공유하므로 Python 모듈로 유지했다. `scripts/verify_inference_http.py`, `scripts/benchmark_inference_http.py`는 서버 실행과 HTTP 검사용 명령으로 유지했다. 발표 자료 생성 코드는 이번 데이터 처리 정리 범위에서 제외했다.

원격 PS1 네 개는 [scripts/remote](../scripts/remote/README.md)에 모았다. 데이터·모델 산출물은 변경하지 않았다.
