pipeline {
  agent { label 'ci' }
  environment {
    REGISTRY = '192.168.56.10:5000'
    APP_HOST = '192.168.56.20'
    BUILDKIT_PROGRESS = 'plain'
    COMPOSE_ANSI = 'never'
    DEPLOY_RESULT = 'NOT_STARTED'
  }
  parameters {
    string(name: 'APP_VERSION', defaultValue: '1.0.0', description: 'Префикс уникального тега образов')
    choice(name: 'DEPLOY_ENV', choices: ['prod', 'staging'], description: 'Автоматический деплой main/master: prod:8080, staging:8082')
  }
  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20'))
  }
  triggers { pollSCM('H/2 * * * *') }
  stages {
    stage('Prepare') {
      steps {
        script {
          // New multibranch jobs may start before parameters reach the shell environment.
          env.APP_VERSION = params.APP_VERSION == null ? '1.0.0' : params.APP_VERSION.toString()
          env.DEPLOY_ENV = params.DEPLOY_ENV == null ? 'prod' : params.DEPLOY_ENV.toString()
          sh '''
            set -eu
            mkdir -p artifacts
            rm -f artifacts/smoke.xml artifacts/frontend.tar.gz artifacts/images.json artifacts/image-tag artifacts/container-logs.txt
            case "$APP_VERSION" in ''|*[!A-Za-z0-9_.-]*|[.-]*) echo 'Invalid APP_VERSION' >&2; exit 1 ;; esac
            [ "${#APP_VERSION}" -le 80 ]
            case "$DEPLOY_ENV" in prod|staging) ;; *) exit 1 ;; esac
            python3 -m venv backend/.venv
            backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
            cd frontend
            npm ci
          '''
          env.IMAGE_TAG = sh(returnStdout: true, script: '''
            printf '%s-%s-%s-%s' "$APP_VERSION" "$BUILD_NUMBER" \
              "$(git rev-parse --short=12 HEAD)" \
              "$(printf '%s' "$BRANCH_NAME" | sha256sum | cut -c1-12)"
          ''').trim()
          env.CI_PROJECT = "ci-${env.IMAGE_TAG}".toLowerCase().replaceAll('[^a-z0-9_-]', '-')
          writeFile file: 'artifacts/image-tag', text: "${env.IMAGE_TAG}\n"
        }
      }
    }
    stage('Lint') {
      steps {
        sh '''
          set -eu
          backend/.venv/bin/ruff check backend/app ci
          cd frontend
          npm run lint
        '''
      }
    }
    stage('Build') {
      steps {
        sh '''
          set -eu
          backend/.venv/bin/python -m compileall -q backend/app
          cd frontend
          npm run build
          cd ..
          tar -czf artifacts/frontend.tar.gz -C frontend/dist .
          docker build -t "$REGISTRY/investhelper-backend:$IMAGE_TAG" backend
          docker build -f ci/frontend.Dockerfile -t "$REGISTRY/investhelper-frontend:$IMAGE_TAG" .
        '''
      }
    }
    stage('Test built application') {
      steps { sh 'bash ci/run-smoke.sh' }
      post {
        always {
          script {
            if (fileExists('artifacts/smoke.xml')) {
              junit testResults: 'artifacts/smoke.xml', allowEmptyResults: false
            }
          }
        }
      }
    }
    stage('Publish artifacts') {
      steps {
        sh '''
          set -eu
          docker push "$REGISTRY/investhelper-backend:$IMAGE_TAG"
          docker push "$REGISTRY/investhelper-frontend:$IMAGE_TAG"
          docker image inspect "$REGISTRY/investhelper-backend:$IMAGE_TAG" \
            "$REGISTRY/investhelper-frontend:$IMAGE_TAG" > artifacts/images.json
        '''
        archiveArtifacts artifacts: 'artifacts/*', fingerprint: true, allowEmptyArchive: false
      }
    }
    stage('Deploy') {
      when { anyOf { branch 'main'; branch 'master' } }
      steps {
        script {
          env.DEPLOY_RESULT = 'IN_PROGRESS'
          env.DEPLOY_TARGET_URL = "http://${env.APP_HOST}:${env.DEPLOY_ENV == 'staging' ? '8082' : '8080'}/"
        }
        sh '''
          set -eu
          ssh -i "$HOME/.ssh/investhelper_deploy_ed25519" \\
            -o BatchMode=yes -o IdentitiesOnly=yes \\
            -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \\
            "vagrant@$APP_HOST" \\
            "deploy-investhelper '$IMAGE_TAG' '$DEPLOY_ENV'"
        '''
        script { env.DEPLOY_RESULT = 'SUCCESS' }
      }
      post {
        failure { script { env.DEPLOY_RESULT = 'FAILURE' } }
        aborted { script { env.DEPLOY_RESULT = 'ABORTED' } }
      }
    }
  }
  post {
    always {
      script {
        if (fileExists('artifacts/smoke.xml')) {
          archiveArtifacts artifacts: 'artifacts/smoke.xml', allowEmptyArchive: false
        }
        if (fileExists('artifacts/container-logs.txt')) {
          archiveArtifacts artifacts: 'artifacts/container-logs.txt', allowEmptyArchive: false
        }
      }
      echo "Итог сборки: ${currentBuild.currentResult}"
    }
    cleanup {
      script {
        if (env.DEPLOY_RESULT == 'NOT_STARTED') {
          env.DEPLOY_RESULT = 'SKIPPED'
          env.DEPLOY_SKIP_REASON = env.BRANCH_NAME in ['main', 'master'] ?
            'Предыдущие стадии не завершились успешно' : 'Деплой только для main/master'
        }
        try {
          withCredentials([
            string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
            string(credentialsId: 'telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')
          ]) {
            withEnv(["BUILD_RESULT=${currentBuild.currentResult}"]) {
              def notificationStatus = sh(returnStatus: true, script: '''
                set +x
                python3 ci/notify_telegram.py
              ''')
              if (notificationStatus != 0) {
                echo 'Telegram: уведомление не доставлено; проверьте credentials и доступ к api.telegram.org.'
              }
            }
          }
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException interrupted) {
          throw interrupted
        } catch (Exception notificationError) {
          echo 'Telegram: отправка недоступна; проверьте Secret text credentials telegram-bot-token и telegram-chat-id.'
        }
      }
    }
  }
}
