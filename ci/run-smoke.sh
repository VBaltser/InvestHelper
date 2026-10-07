#!/usr/bin/env bash
set -euo pipefail
: "${CI_PROJECT:?}" "${REGISTRY:?}" "${IMAGE_TAG:?}"
compose=(docker compose -p "$CI_PROJECT" -f ci/compose.test.yml)
cleanup() {
  "${compose[@]}" logs --no-color > artifacts/container-logs.txt 2>&1 || true
  "${compose[@]}" down --volumes --remove-orphans || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${compose[@]}" up -d --wait --wait-timeout 120 --pull never
address=$("${compose[@]}" port frontend 80)
python3 ci/smoke.py "http://$address" artifacts/smoke.xml
