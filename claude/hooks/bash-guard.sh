#!/bin/bash
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
PROJECT_DIR=$(pwd)

BLOCKED_PATTERNS=(
  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'           # ディスク上書き
  'dd\s+if=.*of=/dev/nvme'         # NVMe上書き
  '>\s*/dev/sd'                    # リダイレクト上書き
  'mkfs\.'                         # 再フォーマット
  'shred\s+.*(/dev/|/disk)'        # 完全消去

  # ── パーミッション破壊 ──────────────────────────
  'chmod\s+.*000'                  # chmod 000（-R あり・なし両方）
  'chmod\s+-R\s+777\s+/'
  'chown\s+-R\s+.*\s+/'            # ルート以下オーナー変更

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

  # ── ファイル内容消去 ────────────────────────────
  'truncate\s+.*-s\s+0'                     # ファイルを空にする

  # ── Git 系破壊 ──────────────────────────────────
  'git\s+clean\s+-[a-z]*f[a-z]*d'          # 未追跡ファイル全削除

  # ── DB 追加破壊 ─────────────────────────────────
  'TRUNCATE\s+TABLE'                        # テーブルデータ全消去
  'DROP\s+SCHEMA'                           # スキーマ削除

  # ── スケジューラ破壊 ────────────────────────────
  'crontab\s+-r'                            # crontab 全削除

  # ── SSH 設定書き換え ────────────────────────────
  '(>>|>)\s*~?/?\.ssh/'                    # ~/.ssh/ への書き込み
  '(>>|>)\s*/home/[^/]+/\.ssh/'            # /home/user/.ssh/ への書き込み
  '(>>|>)\s*/root/\.ssh/'                  # /root/.ssh/ への書き込み

  # ── シェル設定書き換え ──────────────────────────
  '(>>|>)\s*~?/?\.(bashrc|zshrc|profile|bash_profile|bash_login|zprofile)'
  '(>>|>)\s*/home/[^/]+/\.(bashrc|zshrc|profile|bash_profile|bash_login|zprofile)'
  '(>>|>)\s*/root/\.(bashrc|zshrc|profile|bash_profile)'
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiP "$pattern"; then
    echo "❌ BLOCKED: $COMMAND" >&2
    echo "   matched pattern: $pattern" >&2
    echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
    exit 2
  fi
done

# ── rm/rmdir/unlink: プロジェクト配下の子要素のみ許可 ──────────────
# 上のブロックリストを通過した後に評価する。
# 許可は「先頭トークンが rm/rmdir/unlink の単純コマンド」かつ「全対象が
# プロジェクト配下の子要素」の場合のみ。ルート自体・配下外・シェル展開や
# cd を含むものは不許可。wrapper(sudo 等)/パイプ/連結/-exec 経由や末尾形の
# rm 呼び出しは下のブロック正規表現で従来どおりブロックし手動実行に委ねる。
RM_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
case "$RM_FIRST" in
  rm | rmdir | unlink)
    rm_allowed=1
    # 安全文字集合外（~ $ ` ( ) { } " ' \ ; & | < > = 等）→ 解析不能 → 不許可
    printf '%s' "$COMMAND" | grep -qP '[^A-Za-z0-9 \t_./*?-]' && rm_allowed=0
    # cd を含むと cwd 変化でプロジェクト判定が崩れる → 不許可
    printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && rm_allowed=0
    had_target=0
    if [ "$rm_allowed" -eq 1 ]; then
      set -f                                # グロブ展開を抑止しトークンを保全
      for tok in $COMMAND; do
        case "$tok" in
          rm | rmdir | unlink) continue ;;  # コマンド名
          -*) continue ;;                   # フラグ
        esac
        had_target=1
        abs=$(realpath -m "$tok" 2>/dev/null)
        [ -z "$abs" ] && { rm_allowed=0; break; }
        case "$abs" in
          "$PROJECT_DIR"/*) ;;              # 配下の子要素 → OK
          *) rm_allowed=0; break ;;         # ルート自体・配下外 → NG
        esac
      done
      set +f
    fi
    if [ "$rm_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
      exit 0                                # プロジェクト配下の削除のみ → 許可
    fi
    ;;
esac

# 上で許可されなかった rm/rmdir/unlink 呼び出しはブロック（末尾形も捕捉）
if printf '%s' "$COMMAND" | grep -qiP '\b(rm|rmdir|unlink)(\s|$)'; then
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   rm 等はプロジェクト配下($PROJECT_DIR)の子要素削除のみ許可されています（配下外/ルート自体/パイプ・連結・wrapper 経由は不可）。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

exit 0
