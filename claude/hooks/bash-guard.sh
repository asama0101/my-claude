#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

BLOCKED_PATTERNS=(
  # ── ファイル削除（全形式ブロック・ユーザーが手動実行）──
  '\brm\s+'                        # rm（全オプション・全対象、find -exec rm / xargs rm も含む）
  '\brmdir\s+'                     # ディレクトリ削除
  '\bunlink\s+'                    # unlink による削除

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

exit 0
