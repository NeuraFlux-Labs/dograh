// =============================================================================
// Dograh Voice AI — Jenkins CI/CD Pipeline
// =============================================================================
// Clones the repo (with pipecat submodule), builds Docker images on the VPS,
// and deploys via docker compose.
//
// Prerequisites on the Jenkins agent:
//   - Docker + Docker Compose v2 installed
//   - /opt/dograh/.env with secrets (never committed to Git)
//   - Git configured with access to the NeuraFlux-Labs/dograh repo
// =============================================================================

pipeline {
    agent any

    environment {
        DEPLOY_DIR      = '/opt/dograh'
        COMPOSE_PROJECT = 'dograh'
        GIT_REPO        = 'https://github.com/NeuraFlux-Labs/dograh.git'
        DEPLOY_BRANCH   = 'main'
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${DEPLOY_BRANCH}"]],
                    extensions: [
                        [$class: 'SubmoduleOption',
                         recursiveSubmodules: true,
                         trackingSubmodules: false],
                        [$class: 'CleanBeforeCheckout']
                    ],
                    userRemoteConfigs: [[url: GIT_REPO]]
                ])
            }
        }

        stage('Sync to Deploy Dir') {
            steps {
                sh """
                    mkdir -p ${DEPLOY_DIR}
                    rsync -a --delete \
                        --exclude='.env' \
                        --exclude='*.pid' \
                        --exclude='logs/' \
                        --exclude='.git/' \
                        . ${DEPLOY_DIR}/
                """
            }
        }

        stage('Build Images') {
            steps {
                dir("${DEPLOY_DIR}") {
                    sh """
                        # Enforce memory limits for Next.js build
                        export NODE_MEM_MB=2560
                        docker compose -p ${COMPOSE_PROJECT} \
                            -f docker-compose.yaml \
                            build
                    """
                }
            }
        }

        stage('Deploy') {
            steps {
                dir("${DEPLOY_DIR}") {
                    sh """
                        docker compose -p ${COMPOSE_PROJECT} \
                            -f docker-compose.yaml \
                            --env-file .env \
                            up -d --remove-orphans
                    """
                }
            }
        }

        stage('Health Check') {
            steps {
                retry(3) {
                    sh """
                        sleep 20
                        echo "Checking API health..."
                        curl --fail --max-time 10 http://localhost:8000/api/v1/health
                        echo ""
                        echo "Checking UI..."
                        curl --fail --max-time 10 http://localhost:3010
                        echo ""
                        echo "✅ Both services healthy"
                    """
                }
            }
        }
    }

    post {
        failure {
            dir("${DEPLOY_DIR}") {
                sh """
                    echo "========== DEPLOYMENT FAILED — Container Logs =========="
                    docker compose -p ${COMPOSE_PROJECT} logs --tail=100
                """
            }
        }
        success {
            echo '✅ Dograh deployed successfully at https://voice.salespyper.com'
        }
        always {
            cleanWs()
        }
    }
}
