pipeline {
  agent { label 'ci' }

  environment {
    REGISTRY = '192.168.56.10:5000'
    APP_HOST = '192.168.56.20'
  }

  parameters {
    string(name: 'APP_VERSION', defaultValue: '1.0.0', description: 'Версия приложения')
    choice(name: 'DEPLOY_ENV', choices: ['staging', 'prod'], description: 'Окружение для деплоя')
    booleanParam(name: 'RUN_DEPLOY', defaultValue: false, description: 'Выполнить деплой')
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  stages {
    stage('Build') {
      steps {
        echo "Сборка ${params.APP_VERSION} на ${env.NODE_NAME}"
        dir('backend') {
          sh '''
            set -e
            python3 -m venv .venv
            . .venv/bin/activate
            pip install -r requirements.txt -r requirements-dev.txt
            python -m compileall -q app
          '''
        }
        dir('frontend') {
          sh '''
            set -e
            npm ci
            npm run build
          '''
        }
      }
      post {
        success {
          archiveArtifacts artifacts: 'frontend/dist/**', allowEmptyArchive: true
        }
        failure {
          echo 'Build завершился с ошибкой'
        }
      }
    }

    stage('Test') {
      steps {
        script {
          def backendRc = sh(
            script: '''
              cd backend
              . .venv/bin/activate
              ruff check app
            ''',
            returnStatus: true
          )
          def frontendRc = sh(
            script: '''
              cd frontend
              npm run lint
            ''',
            returnStatus: true
          )
          echo "Коды возврата: backend=${backendRc}, frontend=${frontendRc}"
          if (backendRc != 0 || frontendRc != 0) {
            error("Тесты завершились с ошибкой: backend=${backendRc}, frontend=${frontendRc}")
          }
        }
      }
      post {
        failure {
          echo 'Test упал, Deploy запущен не будет'
        }
      }
    }

    stage('Deploy') {
      when {
        allOf {
          branch 'main'
          expression { return params.RUN_DEPLOY }
        }
      }
      steps {
        sh '''
          set -e
          # Validate before using the version in Docker tags and a remote command.
          case "$APP_VERSION" in ''|*[!A-Za-z0-9_.-]*|[.-]*) echo 'Invalid APP_VERSION' >&2; exit 1 ;; esac
          [ "${#APP_VERSION}" -le 80 ]
          case "$DEPLOY_ENV" in staging|prod) ;; *) exit 1 ;; esac
          IMAGE_TAG="${APP_VERSION}-${BUILD_NUMBER}-$(git rev-parse --short=12 HEAD)"
          docker build -t "$REGISTRY/investhelper-backend:$IMAGE_TAG" backend
          docker build -t "$REGISTRY/investhelper-frontend:$IMAGE_TAG" frontend
          docker push "$REGISTRY/investhelper-backend:$IMAGE_TAG"
          docker push "$REGISTRY/investhelper-frontend:$IMAGE_TAG"
          ssh -i "$HOME/.ssh/investhelper_deploy_ed25519" \\
            -o BatchMode=yes -o IdentitiesOnly=yes \\
            -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \\
            "vagrant@$APP_HOST" \\
            "deploy-investhelper '$IMAGE_TAG' '$DEPLOY_ENV'"
          echo "Deployed $IMAGE_TAG ($DEPLOY_ENV) to $APP_HOST"
        '''
      }
    }
  }

  post {
    success {
      echo "Pipeline ${params.APP_VERSION} успешно завершён"
    }
    failure {
      echo 'Pipeline завершился с ошибкой'
    }
    always {
      echo "Итог сборки: ${currentBuild.currentResult}"
    }
  }
}
