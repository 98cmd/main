#!/bin/bash
set -euo pipefail

# Claude Code on the web 以外では何もしない
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# 環境変数 CODEX_AUTH_JSON_B64 を ~/.codex/auth.json に展開して
# Codex CLI をログイン済み状態にする
if [ -n "${CODEX_AUTH_JSON_B64:-}" ]; then
  mkdir -p "$HOME/.codex"
  echo "$CODEX_AUTH_JSON_B64" | base64 -d > "$HOME/.codex/auth.json"
  chmod 600 "$HOME/.codex/auth.json"
  echo "Codex auth.json restored from CODEX_AUTH_JSON_B64" >&2
else
  echo "CODEX_AUTH_JSON_B64 is not set; skipping Codex auth setup" >&2
fi
