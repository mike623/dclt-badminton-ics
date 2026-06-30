#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

podman network exists badminton-n8n-poc >/dev/null 2>&1 || podman network create badminton-n8n-poc >/dev/null

podman build -t localhost/dclt-badminton-checker:latest -f checker/Containerfile checker

podman rm -f dclt-badminton-checker >/dev/null 2>&1 || true
podman run -d \
  --name dclt-badminton-checker \
  --network badminton-n8n-poc \
  -p 8787:8787 \
  localhost/dclt-badminton-checker:latest >/dev/null

podman rm -f n8n-badminton-poc >/dev/null 2>&1 || true
mkdir -p n8n output
podman run -d \
  --name n8n-badminton-poc \
  --network badminton-n8n-poc \
  -p 5678:5678 \
  -e N8N_HOST=0.0.0.0 \
  -e N8N_PORT=5678 \
  -e N8N_PROTOCOL=http \
  -e N8N_SECURE_COOKIE=false \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e DCLT_CHECKER_URL=http://dclt-badminton-checker:8787/availability?days=2 \
  -e N8N_RUNNERS_ENABLED=true \
  -e GENERIC_TIMEZONE=Europe/London \
  -e TZ=Europe/London \
  -v "$PWD/n8n:/home/node/.n8n:U,Z" \
  -v "$PWD/output:/files:U,Z" \
  docker.io/n8nio/n8n:latest >/dev/null

printf 'Started:\n'
podman ps --filter name='dclt-badminton-checker|n8n-badminton-poc' --format '  {{.Names}}  {{.Status}}  {{.Ports}}'
printf '\nOpen n8n: http://localhost:5678\nChecker: http://localhost:8787/availability?days=2\n'
