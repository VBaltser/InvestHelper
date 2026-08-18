pipeline {
  agent none

  parameters {
    string(name: 'APP_VERSION', defaultValue: '1.0.0', description: 'Версия приложения')
    choice(name: 'DEPLOY_ENV', choices: ['staging', 'prod'], description: 'Окружение для деплоя')
    booleanParam(name: 'RUN_DEPLOY', defaultValue: false, description: 'Выполнить деплой')
  }

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  stages {
    stage('Build') {
      agent { label 'vm2' }
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
          stash name: 'frontend-dist', includes: 'frontend/dist/**'
          archiveArtifacts artifacts: 'frontend/dist/**', allowEmptyArchive: true
        }
        failure {
          echo 'Build завершился с ошибкой'
        }
      }
    }

    stage('Test') {
      agent { label 'vm2' }
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
      agent { label 'vm3' }
      when {
        allOf {
          branch 'main'
          expression { return params.RUN_DEPLOY }
        }
      }
      steps {
        unstash 'frontend-dist'
        sh '''
          set -e
          DEST="$HOME/investhelper/${DEPLOY_ENV}/${APP_VERSION}"
          mkdir -p "$DEST"
          cp -a frontend/dist/. "$DEST/"
          echo "${APP_VERSION}" > "$DEST/VERSION"
          ln -sfn "$DEST" "$HOME/investhelper/${DEPLOY_ENV}/current"
          echo "Deployed ${APP_VERSION} (${DEPLOY_ENV}) to ${DEST} on $(hostname)"
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
