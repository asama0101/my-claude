#!/bin/bash
# セッション終了時に使用したスキル・プラグインのサマリーを出力する Stop フック
LOG_FILE="/home/asama/.claude/logs/session-skills-$(date '+%Y%m%d').log"

if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
  echo ""
  echo "=== 本セッションで使用したスキル・プラグイン ==="
  cat "$LOG_FILE"
  echo "================================================"
fi
exit 0
