#!/bin/bash
# system-guard.sh — PreToolUse フック
# 場所を問わずシステム全体を破壊しうるコマンドのみを無条件ブロックする単純な1層構成。
# ゾーン判定（プロジェクト外かどうか）はworkspace-guard.sh、ブランチ判定は
# branch-guard.shが別途担当する。
#
# ── fail-close: jq 不在なら解析不能として block ──────────────
command -v jq >/dev/null 2>&1 || { echo "❌ system-guard: jq not found, failing closed" >&2; exit 2; }
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'
  'dd\s+if=.*of=/dev/nvme'
  '>\s*/dev/sd'
  'mkfs\.'
  'shred\s+.*(/dev/|/disk)'

  # ── パーミッション破壊 ──────────────────────────
  'chown\s+-R\s+.*\s+/'

  # ── プロセス・システム停止 ──────────────────────
  'kill\s+-9\s+-1'
  ':\(\)\s*\{.*:\|:.*\}'
  '\bshutdown(\s+(-|now|\+|halt)|$)'
  'halt'
  'reboot'
  'poweroff'
  'init\s+0'
  'init\s+6'
  'systemctl\s+(poweroff|reboot|halt)'

  # ── 危険なリモート実行 ──────────────────────────
  'curl\s+.*\|\s*(bash|sh)'
  'wget\s+.*\|\s*(bash|sh)'
  'eval\s+.*curl'

  # ── システムファイル破壊 ────────────────────────
  '>\s*/etc/hosts'
  '>\s*/etc/passwd'
  '>\s*/etc/shadow'
  'unset\s+PATH'

  # ── DB破壊 ─────────────────────────────────────
  'DROP\s+DATABASE'
  'DROP\s+TABLE'

  # ── グローバルパッケージ インストール ────────────
  'npm\s+(install|i)\s+(-g|--global)'
  'yarn\s+global\s+add'
  'pnpm\s+(add|install)\s+(-g|--global)'
  'cargo\s+install'
  'gem\s+install'
  'go\s+install'
  'pipx\s+install'
  'uv\s+tool\s+install'
  'conda\s+install'

  # ── パッケージ アンインストール ──────────────────
  'apt\s+(remove|purge|autoremove)\s+-y'
  'apt-get\s+(remove|purge|autoremove)\s+-y'
  'yum\s+remove\s+-y'
  'dnf\s+remove\s+-y'
  'npm\s+uninstall\s+-g'

  # ── システムパッケージのupdate/upgrade ──────────
  'apt(-get)?\s+update\b'
  'apt(-get)?\s+(upgrade|dist-upgrade)\b'
  'brew\s+upgrade\b'
  'yum\s+(update|upgrade)\b'
  'dnf\s+(update|upgrade)\b'

  # ── ファイル内容消去 ────────────────────────────
  'truncate\s+.*-s\s+0'

  # ── 迂回削除（python経由）──────────────────────
  'shutil\.rmtree'
  'os\.(remove|unlink|rmdir)'
  'truncate\s+.*--size[= ]*0'

  # ── DB 追加破壊 ─────────────────────────────────
  'TRUNCATE\s+TABLE'
  'DROP\s+SCHEMA'

  # ── スケジューラ破壊 ────────────────────────────
  'crontab\s+-r'

  # ── 機密ファイル読取・持ち出し ──────────────────
  # cat/less/head等のファイル読取のゾーン判定はworkspace-guard.shの対象外(Write/Edit系
  # のみに縮小済み)のため、ここでは対象にしない(2026-08-29再設計でスコープ確定)。
  # python/perl等のワンライナー経由（-c/-e）はファイル対象がコード文字列に
  # 埋め込まれ静的に確定できないためゾーン判定になじまず、常時無条件ブロックのまま。
  '(python3?|perl|ruby|node)\s+(-c|-e)\s+.*(\.env(\.|\s|['"'"'")]|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|['"'"'")]|$)|\.key(\s|['"'"'")]|$)|authorized_keys|\.netrc|credentials)'
)

# ── 難読化正規化（判定用。実行はしない）──────────────
# クォート分割('r''m')・バックスラッシュエスケープ(r\m)・${IFS}/$IFS空白代替
# (kill${IFS}-9)で BLOCKED_PATTERNS の前提(コマンド名がそのまま文字列に現れる)
# が崩れるのを防ぐため、除去・置換のみ行った正規化版を作る。
normalize() {
  printf '%s' "$1" | tr -d "\"'\\\\" | sed -E 's/\$\{?IFS\}?/ /g'
}

# ── 全体スコープの危険パターン判定（$COMMAND全体へ評価）────────────────
check_whole_command() {
  local pattern COMMAND_NORMALIZED
  COMMAND_NORMALIZED=$(normalize "$COMMAND")

  for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiP "$pattern"; then
      echo "❌ BLOCKED: $COMMAND" >&2
      echo "   matched pattern: $pattern" >&2
      echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
      exit 2
    fi
  done

  if [ "$COMMAND_NORMALIZED" != "$COMMAND" ]; then
    for pattern in "${BLOCKED_PATTERNS[@]}"; do
      if printf '%s' "$COMMAND_NORMALIZED" | grep -qiP "$pattern" \
         && ! printf '%s' "$COMMAND" | grep -qiP "$pattern"; then
        echo "❌ BLOCKED: $COMMAND" >&2
        echo "   クォート分割/バックスラッシュ/\${IFS}等の難読化を検知し、正規化後に危険パターンへ一致しました: $pattern" >&2
        echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
        exit 2
      fi
    done
  fi
}
check_whole_command
exit 0
