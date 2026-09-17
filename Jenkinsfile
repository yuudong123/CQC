pipeline {

    agent any

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
        // 오래된 로그가 계속 쌓이는 것을 방지한다.
        buildDiscarder(
            logRotator(numToKeepStr: '30')
        )
    }


    // ========================================================
    // 자동 실행 Trigger
    // ========================================================
    // 현재는 GitHub ↔ Jenkins ↔ Docker 연결을 확인하는 단계이므로
    // Build Now를 이용해 수동 실행한다.
    //
    // 연결 검증이 끝나면 아래 설정을 활성화한다.
    //
    // triggers {
    //     githubPush()
    // }
    // ========================================================


    stages {

        // ====================================================
        // 1. Git Clone
        // ====================================================
        // 현재 MLOps 작업 브랜치인 feat/mlops를 가져온다.
        //
        // Jenkins 연결 및 Pipeline 검증이 완료되면
        // 최종 CI/CD 기준 브랜치를 dev로 변경한다.
        // ====================================================
        stage('Git Clone') {

            steps {

                // 이전 Jenkins Workspace의 파일을 제거한다.
                // 이전 빌드 파일 때문에 발생할 수 있는 충돌을 방지한다.
                deleteDir()

                // CQC GitHub 저장소의 feat/mlops 브랜치를 가져온다.
                git branch: 'feat/mlops',
                    url: 'https://github.com/yuudong123/CQC.git'
            }
        }


        // ====================================================
        // 2. Environment Check
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
                    echo " Docker Version"
                    echo "======================================"
                    docker --version

                    echo "======================================"
                    echo " Docker Compose Version"
                    echo "======================================"
                    docker compose version
                '''
            }
        }


        // ====================================================
        // 3. Compose Validate
        // ====================================================
        stage('Compose Validate') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " Compose Validate"
                    echo "======================================"

                    docker compose -f compose.yaml config --quiet
                '''
            }
        }


        // ====================================================
        // 4. Docker Build
        // ====================================================
        stage('Docker Build') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " Docker Build"
                    echo "======================================"

                    docker compose -f compose.yaml build
                '''
            }
        }


        // ====================================================
        // 5. Basic Check
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
                    test -d models
                    test -d scripts

                    echo "CQC project structure OK"
                '''
            }
        }


        // ====================================================
        // 6. Deploy
        // ====================================================
        stage('Deploy') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " CQC Deploy"
                    echo "======================================"

                    docker compose -f compose.yaml up -d --no-build
                '''
            }
        }


        // ====================================================
        // 7. Verify
        // ====================================================
        stage('Verify') {

            steps {

                sh '''
                    set -eu

                    echo "======================================"
                    echo " CQC Container Status"
                    echo "======================================"

                    docker compose -f compose.yaml ps
                '''
            }
        }

    }


    // ========================================================
    // Pipeline 결과
    // ========================================================
    post {

        success {
            echo '======================================'
            echo ' CQC CI/CD SUCCESS'
            echo '======================================'
        }

        failure {
            echo '======================================'
            echo ' CQC CI/CD FAILED'
            echo '======================================'
        }

        always {
            echo 'CQC Pipeline finished.'
        }
    }
}
