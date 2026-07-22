pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  stages {
    stage('Backend') {
      steps {
        dir('backend') {
          sh '''
            set -e
            python3 -m venv .venv
            . .venv/bin/activate
            pip install -r requirements.txt -r requirements-dev.txt
            python -m compileall -q app
            ruff check app
          '''
        }
      }
    }

    stage('Frontend') {
      steps {
        dir('frontend') {
          sh '''
            set -e
            npm ci
            npm run lint
            npm run build
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'frontend/dist/**', allowEmptyArchive: true
    }
  }
}
