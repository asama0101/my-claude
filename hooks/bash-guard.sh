#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  # ── ファイルシステム破壊 ────────────────────────
  'rm\s+-[a-z]*r[a-z]*f\s+/'       # rm -rf / 系
  'rm\s+-[a-z]*r[a-z]*f\s+~'       # rm -rf ~
  'rm\s+-[a-z]*r[a-z]*f\s+\*'      # rm -rf *
  'rm\s+-[a-z]*r[a-z]*f\s+\.'      # rm -rf .
  'find\s+.*-exec\s+rm'            # find経由削除

  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'           # ディスク上書き
  'dd\s+if=.*of=/dev/nvme'         # NVMe上書き
  '>\s*/dev/sd'                    # リダイレクト上書き
  'mkfs\.'                         # 再フォーマット
  'shred\s+.*(/dev/|/disk)'        # 完全消去

  # ── パーミッション破壊 ──────────────────────────
  'chmod\s+-R\s+000'
  'chmod\s+-R\s+777\s+/'
  'chown\s+-R\s+.*\s+/'            # ルート以下オーナー変更

  # ── プロセス・システム停止 ──────────────────────
  'kill\s+-9\s+-1'                 # 全プロセス強制終了
  ':\(\)\s*\{.*:\|:.*\}'           # Fork爆弾
  'shutdown'
  'halt'
  'reboot'
  'poweroff'
  'init\s+0'
  'init\s+6'
  'systemctl\s+(poweroff|reboot|halt)'

  # ── 危険なリモート実行 ──────────────────────────
  'curl\s+.*\|\s*(bash|sh)'        # curl | bash
  'wget\s+.*\|\s*(bash|sh)'        # wget | sh
  'eval\s+.*curl'

  # ── システムファイル破壊 ────────────────────────
  '>\s*/etc/hosts'
  '>\s*/etc/passwd'
  '>\s*/etc/shadow'
  'unset\s+PATH'                   # PATH破壊

  # ── DB破壊 ─────────────────────────────────────
  'DROP\s+DATABASE'
  'DROP\s+TABLE'

  # ── パッケージ アンインストール ──────────────────
  'apt\s+(remove|purge|autoremove)\s+-y'     # apt 一括削除
  'apt-get\s+(remove|purge|autoremove)\s+-y'
  'yum\s+remove\s+-y'
  'dnf\s+remove\s+-y'
  'npm\s+uninstall\s+-g'                    # グローバルパッケージ削除
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiP "$pattern"; then
    echo "❌ BLOCKED: $COMMAND" >&2
    echo "   matched pattern: $pattern" >&2
    exit 2
  fi
done

exit 0
