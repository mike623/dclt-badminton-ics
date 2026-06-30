#!/usr/bin/env bash
set -euo pipefail
podman rm -f n8n-badminton-poc dclt-badminton-checker >/dev/null 2>&1 || true
printf 'Stopped n8n-badminton-poc and dclt-badminton-checker if they existed.\n'
