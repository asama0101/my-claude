#!/bin/bash
# system-guard.sh — PreToolUse フック
# 場所を問わずシステム全体を破壊しうるコマンドのみを無条件ブロックする単純な1層構成。
# ゾーン判定（プロジェクト外かどうか）はworkspace-guard.sh、ブランチ判定は
# branch-guard.shが別途担当する。
#
# ── fail-close: jq 不在なら解析不能として block ──────────────
command -v jq >/dev/null 2>&1 || { echo "❌ system-guard: jq not found, failing closed" >&2; exit 2; }

# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
# で失敗し終了ステータス2を返す。下の判定は全て `if ... grep -qiP ...; then` 形式で、
# エラー(2)は「不一致」と同じ扱いになるため、ロケールを明示しないと
# BLOCKED_PATTERNS 全件が黙って fail-open する（＝何も守らない）。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'           # ディスク上書き
  'dd\s+if=.*of=/dev/nvme'         # NVMe上書き
  '>\s*/dev/sd'                    # リダイレクト上書き
  'mkfs\.'                         # 再フォーマット
  'shred\s+.*(/dev/|/disk)'        # 完全消去

  # ── パーミッション破壊 ──────────────────────────
  'chown\s+-R\s+.*\s+/'            # ルート以下オーナー変更
  'chmod\s+-R\s+777\s+/\s*(&&|;|\||$)'  # ファイルシステムルート配下の全権限解放
  'chmod\s+(-\S+\s+)*0{1,4}\b'          # chmod 000/-R 000等の全権限剥奪

  # ── プロセス・システム停止 ──────────────────────
  'kill\s+-9\s+-1'                 # 全プロセス強制終了
  ':\(\)\s*\{.*:\|:.*\}'           # Fork爆弾
  '\bshutdown(\s+(-|now|\+|halt)|$)'   # システム停止コマンド（grep/if-chip-shutdown 等の read-only 文字列は通す）
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

  # ── グローバルパッケージ インストール ────────────
  'npm\s+(install|i)\s+(-g|--global)'       # npm グローバルインストール
  'yarn\s+global\s+add'                     # yarn グローバルインストール
  'pnpm\s+(add|install)\s+(-g|--global)'   # pnpm グローバルインストール
  'cargo\s+install'                         # Rust クレートのグローバルインストール
  'gem\s+install'                           # Ruby gem インストール
  'go\s+install'                            # Go パッケージのグローバルインストール
  'pipx\s+install'                          # pipx によるグローバル CLI ツールのインストール
  'uv\s+tool\s+install'                    # uv のグローバル CLI ツールのインストール
  'conda\s+install'                        # Anaconda/Miniconda パッケージインストール

  # ── パッケージ アンインストール ──────────────────
  'apt\s+(remove|purge|autoremove)\s+-y'     # apt 一括削除
  'apt-get\s+(remove|purge|autoremove)\s+-y'
  'yum\s+remove\s+-y'
  'dnf\s+remove\s+-y'
  'npm\s+uninstall\s+-g'                    # グローバルパッケージ削除

  # ── システムパッケージのupdate/upgrade ──────────
  'apt(-get)?\s+update\b'
  'apt(-get)?\s+(upgrade|dist-upgrade)\b'
  'brew\s+upgrade\b'
  'yum\s+(update|upgrade)\b'
  'dnf\s+(update|upgrade)\b'

  # ── ファイル内容消去 ────────────────────────────
  'truncate\s+.*-s\s+0'                     # ファイルを空にする

  # ── 迂回削除（python経由）──────────────────────
  'shutil\.rmtree'                          # Python shutil.rmtree
  'os\.(remove|unlink|rmdir)'               # Python os.remove/unlink/rmdir
  'truncate\s+.*--size[= ]*0'              # truncate --size 0 でファイルを空にする

  # ── DB 追加破壊 ─────────────────────────────────
  'TRUNCATE\s+TABLE'                        # テーブルデータ全消去
  'DROP\s+SCHEMA'                           # スキーマ削除

  # ── スケジューラ破壊 ────────────────────────────
  'crontab\s+-r'                            # crontab 全削除

  # ── Git作業ツリー破壊(パス指定なしの無差別削除) ──────
  'git\s+clean\s+-[a-z]*f[a-z]*d[a-z]*\s*(&&|;|\||$)'

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
# が崩れるのを防ぐため、除去・置換のみ行った正規化版を作る。コマンド置換
# ($()/``)や変数展開は評価しない単純なテキスト変換のため安全。
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

  # ── 正規化後の危険パターン再判定（難読化バイパス対策）──────────────
  # クォート分割/バックスラッシュ/${IFS}等で上のBLOCKED_PATTERNSを回避しようとした
  # 場合、正規化後の文字列に対して同じパターンを再評価しブロックする。
  if [ "$COMMAND_NORMALIZED" != "$COMMAND" ]; then
    for pattern in "${BLOCKED_PATTERNS[@]}"; do
      # 正規化で「新たに」現れたマッチのみを難読化とみなす。元のコマンドの時点で
      # 既に同じパターンに一致していた場合、そのキーワードはクォート等で隠されて
      # おらず素通しで見えているということなので、難読化ではない（無関係な箇所の
      # クォート — 例: git commit -m "..." のメッセージ引用 — がCOMMAND_NORMALIZED!=
      # COMMANDを成立させただけの誤爆を防ぐ）。
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
