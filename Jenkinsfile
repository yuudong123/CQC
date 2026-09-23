pipeline {

    agent any

    // ========================================================
    // CQC Jenkins Pipeline
    // WBS: MO-03 + MO-04 연동 검증
    // 담당: 홍유나
    //
    // 목적:
    // - GitHub에서 Jenkinsfile과 프로젝트 코드를 checkout
    // - Docker / Docker Compose 실행 환경 확인
    // - compose.yaml 문법 검증
    // - Compose 서비스 빌드 및 기동
    // - MO-04에서 추가한 healthcheck / 기동 의존성 검증
    //
    // 현재 검증 대상:
    // - mysql
    // - 실제 inference
    // - 실제 backend
    // - frontend
    // - simulator
    //
    // Healthcheck 대상:
    // - mysql
    // - inference
    // - backend
    //
    // 기동 의존성:
    //   MySQL ─────┐
    //              ├→ Backend → Simulator
    //   Inference ─┘          └→ Frontend
    // ========================================================

    // ========================================================
    // Jenkins 기본 실행 정책
    // ========================================================
    options {

        // 같은 Job이 동시에 여러 번 실행되는 것을 방지한다.
        // 동시에 두 배포가 실행되면 같은 Docker 컨테이너를
        // 서로 변경할 수 있기 때문에 막는다.
        disableConcurrentBuilds()

        // Pipeline이 비정상적으로 오래 실행되는 것을 방지한다.
        timeout(time: 20, unit: 'MINUTES')

        // Jenkins 빌드 기록을 최근 30개까지만 유지한다.
        buildDiscarder(
            logRotator(numToKeepStr: '30')
        )
    }

    // ========================================================
    // 자동 실행 Trigger
    // ========================================================
    // GitHub에 push가 발생하면 Jenkins Pipeline을 자동 실행한다.
    //
    // Jenkins Job은 Pipeline script from SCM을 사용하고,
    // Branch Specifier는 */feat/mlops로 설정한다.
    //
    // GitHub 저장소의 Webhook이 Jenkins와 연결되어 있어야
    // push 이벤트가 Jenkins로 전달된다.
    // ========================================================
    triggers {
        githubPush()
    }

    // ========================================================
    // MO-05 MySQL 환경변수 / Credentials
    // ========================================================
    environment {
        MYSQL_ROOT_PASSWORD = credentials('cqc-mysql-root-password')
        MYSQL_CREDS = credentials('cqc-mysql-creds')

        MYSQL_DATABASE = 'cqc'
        MYSQL_USER = "${MYSQL_CREDS_USR}"
        MYSQL_PASSWORD = "${MYSQL_CREDS_PSW}"

        // 물류 Web 번들에 포함되는 Jenkins 배포 호스트의 공개 주소
        LOGISTICS_PUBLIC_WEB_ORIGIN = 'http://192.168.133.106:3100'
        LOGISTICS_PUBLIC_API_URL = 'http://192.168.133.106:8100/api/v1'
        LOGISTICS_WEB_PORT = '3100'
        LOGISTICS_API_PORT = '8100'
    }

    stages {

        // ====================================================
        // 1. Environment Check
        // ====================================================
        // Pipeline script from SCM을 사용하므로
        // Jenkins Job의 SCM 설정에 지정된 브랜치를 자동 checkout한다.
        //
        // 따라서 Jenkinsfile 내부에서 별도의 git clone / checkout을
        // 다시 수행하지 않는다.
        //
        // 현재 작업 브랜치를 feat/mlops로 사용할 경우,
        // Jenkins Job의 Branch Specifier를 */feat/mlops로 설정한다.
        //
        // 이 단계에서는 Jenkins 실행 환경에서
        // Git / Docker / Docker Compose 사용 가능 여부를 확인한다.
        // ====================================================
        stage('Environment Check') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " Git Version"
                    echo "======================================"
                    git --version

                    echo "======================================"
                    echo " Current Git Branch / Commit"
                    echo "======================================"
                    git branch --show-current || true
                    git rev-parse --short HEAD

                    echo "======================================"
                    echo " Docker Version"
                    echo "======================================"
                    docker --version

                    echo "======================================"
                    echo " Docker Compose Version"
                    echo "======================================"
                    docker-compose --version
                '''
            }
        }

        // ====================================================
        // 2. Compose Validate
        // ====================================================
        // 현재 compose.yaml 전체 설정을 검사한다.
        //
        // 실제 컨테이너를 변경하기 전에
        // YAML 문법, 필수 모델 경로, healthcheck, depends_on 등
        // Compose 설정 오류가 없는지 먼저 확인한다.
        // ====================================================
        stage('Compose Validate') {

            steps {

                sh '''
                    set -eu

                    export INFERENCE_CLIENT_MODE=http
                    export INFERENCE_URL=http://inference:8001/v1/predict
                    export INFERENCE_MODEL_DIR="$PWD/models/cqc-apple-separate12-focal-v2-candidate"

                    echo "======================================"
                    echo " Compose Validate"
                    echo "======================================"

                    docker-compose -f compose.yaml config
                '''
            }
        }

        // ====================================================
        // 3. Docker Build
        // ====================================================
        // Compose의 build 설정이 존재하는 서비스를 빌드한다.
        //
        // Backend / Inference는 이 단계에서 실제 Dockerfile로 빌드된다.
        // Frontend / Simulator는 실행 파일이 준비될 때까지 placeholder를 유지한다.
        // ====================================================
        stage('Docker Build') {

            steps {

                sh '''
                    set -eu

                    export INFERENCE_CLIENT_MODE=http
                    export INFERENCE_URL=http://inference:8001/v1/predict
                    export INFERENCE_MODEL_DIR="$PWD/models/cqc-apple-separate12-focal-v2-candidate"

                    echo "======================================"
                    echo " Docker Build"
                    echo "======================================"

                    docker-compose -f compose.yaml build
                '''
            }
        }

        // ====================================================
        // 4. Basic Check
        // ====================================================
        // 현재 프로젝트에서 반드시 존재해야 하는
        // 기본 디렉터리 구조를 확인한다.
        //
        // 추후 테스트 환경이 확정되면
        // pytest 등 실제 자동 테스트 단계로 확장한다.
        // ====================================================
        stage('Basic Check') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " Project Structure Check"
                    echo "======================================"

                    test -d src
                    test -d tests
                    test -d docs
                    test -f models/cqc-apple-separate12-focal-v2-candidate/model.json
                    test -f models/cqc-apple-separate12-focal-v2-candidate/model.pt
                    test -d scripts
                    test -d cqc-logistics-platform/apps/api
                    test -d cqc-logistics-platform/apps/web

                    echo "CQC project structure OK"
                '''
            }
        }

        // ====================================================
        // 5. Deploy
        // ====================================================
        // 이전 단계의 검증과 Build가 성공한 경우에만
        // Compose 서비스를 실행한다.
        //
        // --no-build를 사용해 Deploy 단계에서
        // 이미지를 다시 빌드하지 않는다.
        //
        // compose.yaml의 depends_on + service_healthy 설정에 따라
        // MySQL / Inference가 healthy 상태가 된 뒤 Backend가 기동되고,
        // Backend가 healthy 상태가 된 뒤 Frontend / Simulator가 기동된다.
        // ====================================================
        stage('Deploy') {

            steps {

                sh '''
                    set -eu

                    export INFERENCE_CLIENT_MODE=http
                    export INFERENCE_URL=http://inference:8001/v1/predict
                    export INFERENCE_MODEL_DIR="$PWD/models/cqc-apple-separate12-focal-v2-candidate"

                    echo "======================================"
                    echo " CQC Deploy"
                    echo "======================================"

                    docker-compose -f compose.yaml up -d --no-build
                '''
            }
        }

        // ====================================================
        // 6. Verify
        // ====================================================
        // MO-04에서 적용한 healthcheck와 기동 상태를 검증한다.
        //
        // 1) 전체 서비스 상태 출력
        // 2) mysql / inference / backend 컨테이너 존재 여부 확인
        // 3) 각 컨테이너의 Health.Status가 healthy인지 확인
        // 4) frontend / simulator가 실행 중인지 확인
        //
        // healthcheck가 아직 완료되지 않은 경우를 고려해
        // 최대 60초 동안 반복 확인한다.
        // ====================================================
        stage('Verify') {

            steps {

                sh '''
                    set -eu

                    export INFERENCE_CLIENT_MODE=http
                    export INFERENCE_URL=http://inference:8001/v1/predict
                    export INFERENCE_MODEL_DIR="$PWD/models/cqc-apple-separate12-focal-v2-candidate"

                    echo "======================================"
                    echo " CQC Container Status"
                    echo "======================================"

                    docker-compose -f compose.yaml ps

                    echo "======================================"
                    echo " Healthcheck Verification"
                    echo "======================================"

                    HEALTH_SERVICES="mysql inference backend logistics-mongodb logistics-api logistics-web"

                    for service in $HEALTH_SERVICES; do

                        container_id="$(docker-compose -f compose.yaml ps -q "$service")"

                        if [ -z "$container_id" ]; then
                            echo "[ERROR] $service container not found"
                            exit 1
                        fi

                        echo "Waiting for $service to become healthy..."

                        healthy="false"

                        for i in $(seq 1 12); do

                            status="$(docker inspect \
                                --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
                                "$container_id")"

                            echo "[$i/12] $service health status: $status"

                            if [ "$status" = "healthy" ]; then
                                healthy="true"
                                break
                            fi

                            if [ "$status" = "unhealthy" ]; then
                                echo "[ERROR] $service became unhealthy"
                                docker inspect "$container_id" || true
                                exit 1
                            fi

                            sleep 5
                        done

                        if [ "$healthy" != "true" ]; then
                            echo "[ERROR] $service did not become healthy within 60 seconds"
                            docker inspect "$container_id" || true
                            exit 1
                        fi
                    done

                    echo "======================================"
                    echo " Runtime Verification"
                    echo "======================================"

                    for service in frontend simulator; do

                        container_id="$(docker-compose -f compose.yaml ps -q "$service")"

                        if [ -z "$container_id" ]; then
                            echo "[ERROR] $service container not found"
                            exit 1
                        fi

                        running="$(docker inspect \
                            --format='{{.State.Running}}' \
                            "$container_id")"

                        echo "$service running: $running"

                        if [ "$running" != "true" ]; then
                            echo "[ERROR] $service is not running"
                            exit 1
                        fi
                    done

                    echo "======================================"
                    echo " API Smoke Verification"
                    echo "======================================"

                    backend_id="$(docker-compose -f compose.yaml ps -q backend)"
                    inference_id="$(docker-compose -f compose.yaml ps -q inference)"

                    docker exec "$inference_id" python -c \
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5)"
                    docker exec "$backend_id" python -c \
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

                    echo "======================================"
                    echo " MO-04 healthcheck + API verification OK"
                    echo "======================================"

                    docker-compose -f compose.yaml ps
                '''
            }
        }
    }

    // ========================================================
    // Pipeline 최종 결과
    // ========================================================
    post {

        success {
            echo '======================================'
            echo ' CQC CI/CD + MO-04 VERIFY SUCCESS'
            echo '======================================'
        }

        failure {
            echo '======================================'
            echo ' CQC CI/CD FAILED'
            echo '======================================'

            // 실패 시 원인 확인을 위해 현재 Compose 상태를 출력한다.
            sh '''
                export INFERENCE_MODEL_DIR="$PWD/models/cqc-apple-separate12-focal-v2-candidate"
                docker-compose -f compose.yaml ps || true
            '''
        }

        always {
            // 현재는 MO-04 서비스 상태 확인이 필요하므로
            // Pipeline 종료 후 컨테이너를 자동으로 내리지 않는다.
            echo 'CQC Pipeline finished.'
        }
    }
}
