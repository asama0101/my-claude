#!/bin/bash
# ── fail-close: jq 不在なら解析不能として block ──────────────
command -v jq >/dev/null 2>&1 || { echo "❌ bash-guard: jq not found, failing closed" >&2; exit 2; }
# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 1) 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
#    で失敗し終了ステータス2を返す。下の判定は全て `if ... grep -qiP ...; then` 形式で、
#    エラー(2)は「不一致」と同じ扱いになるため、ロケールを明示しないと
#    BLOCKED_PATTERNS 全件が黙って fail-open する（＝何も守らない）。
# 2) rm 許可ゾーン判定に渡るパスは Windows 形式(C:\...)になり得るが $(pwd)/$HOME は
#    MSYS 形式(/c/...)。MSYS の realpath は C:\x を C:/x に直すだけで /c/x にはしない
#    ため、正規化しないと前方一致比較が必ず失敗する。
case "${OSTYPE:-}" in msys* | cygwin*) export LC_ALL="${LC_ALL:-C.UTF-8}" ;; esac

to_posix() {
  local p="${1//\\//}"                                                      # \ → /
  case "$p" in
    [A-Za-z]:/*) p="/$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')${p#*:}" ;;  # C:/x → /c/x
  esac
  # NTFS はパスの大文字小文字を区別しないため、ゾーン前方一致比較
  # （"$PROJECT_DIR"/* 等）が大文字小文字違いだけで誤って不一致判定
  # されないよう、Windows(msys/cygwin)上でのみ全体を小文字化する。
  case "${OSTYPE:-}" in msys* | cygwin*) p=$(printf '%s' "$p" | tr 'A-Z' 'a-z') ;; esac
  printf '%s' "$p"
}

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
PROJECT_DIR=$(to_posix "$(pwd)")
CLAUDE_HOME=$(to_posix "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")

# ── 難読化正規化（判定用。実行はしない）──────────────
# クォート分割('r''m')・バックスラッシュエスケープ(r\m)・${IFS}/$IFS空白代替
# (kill${IFS}-9)で BLOCKED_PATTERNS の前提(コマンド名がそのまま文字列に現れる)
# が崩れるのを防ぐため、除去・置換のみ行った正規化版を作る。コマンド置換
# ($()/``)や変数展開は評価しない単純なテキスト変換のため安全。
NORMALIZED=$(printf '%s' "$COMMAND" | tr -d "\"'\\\\" | sed -E 's/\$\{?IFS\}?/ /g')

BLOCKED_PATTERNS=(
  # ── ディスク・デバイス破壊 ──────────────────────
  'dd\s+if=.*of=/dev/sd'           # ディスク上書き
  'dd\s+if=.*of=/dev/nvme'         # NVMe上書き
  '>\s*/dev/sd'                    # リダイレクト上書き
  'mkfs\.'                         # 再フォーマット
  'shred\s+.*(/dev/|/disk)'        # 完全消去

  # ── パーミッション破壊 ──────────────────────────
  # chmod 000 / chmod -R 777 / はゾーン判定（下記専用ブロック）へ移行済み。
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

  # ── 迂回削除（find/python/rsync 経由）──────────────
  # find -delete・rsync --delete はゾーン判定（下記専用ブロック）へ移行済み。
  'shutil\.rmtree'                          # Python shutil.rmtree
  'os\.(remove|unlink|rmdir)'               # Python os.remove/unlink/rmdir
  'truncate\s+.*--size[= ]*0'              # truncate --size 0 でファイルを空にする

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

  # ── 機密ファイル読取・持ち出し ──────────────────
  # cat/less/head等のファイル読取はゾーン判定（下記専用ブロック）へ移行済み。
  # python/perl等のワンライナー経由（-c/-e）はファイル対象がコード文字列に
  # 埋め込まれ静的に確定できないためゾーン判定の対象外とし、常時無条件ブロックのまま。
  '(python3?|perl|ruby|node)\s+(-c|-e)\s+.*(\.env(\.|\s|['"'"'")]|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|['"'"'")]|$)|\.key(\s|['"'"'")]|$)|authorized_keys|\.netrc|credentials)'
)

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
# 場合、正規化後の文字列に対して同じパターン(+rm系/ゾーン判定対象のcatch-all)を
# 再評価しブロックする。find -delete/rsync --delete/chmod 000/-R 777/機密ファイル
# 読取はゾーン判定で許可されうるため、通常時（$NORMALIZED == $COMMAND）は下の
# ゾーン判定に委ねるが、難読化を検知した時点ではゾーン判定のトリガー正規表現ごと
# 迂回されうるため、ここで無条件ブロックにフォールバックする。
if [ "$NORMALIZED" != "$COMMAND" ]; then
  for pattern in "${BLOCKED_PATTERNS[@]}" '\b(rm|rmdir|unlink)(\s|$)' \
                 'find\s+.*-delete' 'rsync\s+.*--del' 'chmod\s+.*000' 'chmod\s+-R\s+777\s+/' \
                 '\b(cat|less|more|head|tail|base64|xxd|od|strings)\s+.*(\.env(\.|\s|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|$)|\.key(\s|$)|authorized_keys|\.netrc|credentials)'; do
    # 正規化で「新たに」現れたマッチのみを難読化とみなす。元コマンドの時点で
    # 既に同じパターンに一致していた場合、そのキーワードはクォート等で隠されて
    # おらず素通しで見えているということなので、難読化ではない（無関係な箇所の
    # クォート — 例: git commit -m "..." のメッセージ引用 — がNORMALIZED!=COMMAND
    # を成立させただけで、rm等が誤って道連れブロックされるのを防ぐ）。この場合は
    # 後続のゾーン判定（git rm --cached 等）に評価を委ねる。
    # 安全性メモ（review-security確認済み）: この除外条件は「同じパターンが
    # コマンド中のどこか無害な場所に既出であれば除外する」ため、変更前より
    # 狭い範囲でしか捕捉しない。実際に危険なコマンドが素通りしないのは、
    # 445行目付近の最終catch-all（\b(rm|rmdir|unlink)(\s|$)等の同一パターン）
    # や各専用ゾーン判定のFIRSTトークン厳格チェックが独立した安全網として
    # 機能しているためであり、この除外条件自身が安全性を担保しているわけでは
    # ない。将来それらの層を変更する際は、この除外条件との相互作用を再確認する
    # こと。
    if printf '%s' "$NORMALIZED" | grep -qiP "$pattern" \
       && ! printf '%s' "$COMMAND" | grep -qiP "$pattern"; then
      echo "❌ BLOCKED: $COMMAND" >&2
      echo "   クォート分割/バックスラッシュ/\${IFS}等の難読化を検知し、正規化後に危険パターンへ一致しました: $pattern" >&2
      echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
      exit 2
    fi
  done
fi

# ── 削除系コマンドの難読化（変数展開・コマンド置換）遮断 ────────────
# 削除語（rm/rmdir/unlink）を含み、かつ $展開 または
# コマンド置換（` / $(）を含む場合は削除対象を確定できず解析不能として block。
# 削除語を含む場合のみに限定し、通常コマンドの誤爆を避ける（delete/rmtree は
# 英単語での誤爆を避けるためトリガーから除外＝それぞれ専用パターンで捕捉済み）。
# 判定は「削除語を含む行」単位に限定する。複数行コマンド（例: git rm --cached の
# 次行に git commit -m "$(cat <<EOF ... )" のような別コマンドが続く場合）で、
# 削除語を含まない別行の $(...) に道連れでブロックされないようにするため
# （削除対象を確定できない、という本来の趣旨は削除語自身の行にのみ関係する）。
RM_LINES=$(printf '%s\n' "$COMMAND" | grep -iP '\b(rm|rmdir|unlink)\b')
if [ -n "$RM_LINES" ] && printf '%s' "$RM_LINES" | grep -qE '[$`]'; then
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   削除系コマンドに変数展開/コマンド置換が含まれ、削除対象を確定できません。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

# ── rm/rmdir/unlink: プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の子要素のみ許可 ──
# 上のブロックリストを通過した後に評価する。
# 許可は「先頭トークンが rm/rmdir/unlink の単純コマンド」かつ「全対象が
# 上記3ゾーンいずれかの子要素」の場合のみ。各ゾームのルート自体・ゾーン外・
# シェル展開や cd を含むものは不許可。wrapper(sudo 等)/パイプ/連結/-exec 経由や
# 末尾形の rm 呼び出しは下のブロック正規表現で従来どおりブロックし手動実行に委ねる。
RM_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
case "$RM_FIRST" in
  rm | rmdir | unlink)
    rm_allowed=1
    # 安全文字集合外（~ $ ` ( ) { } " ' \ ; & | < > = 等）→ 解析不能 → 不許可
    # 改行は tr で許可集合外の \v に変換してから判定する（grep は行単位評価のため
    # 生の改行は素通りし、複数行コマンドの2行目以降が無検査になる穴を防ぐ）。
    printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && rm_allowed=0
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
        abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
        [ -z "$abs" ] && { rm_allowed=0; break; }
        case "$abs" in
          "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;  # 3ゾーンいずれかの子要素 → OK
          *) rm_allowed=0; break ;;                          # ルート自体・ゾーン外 → NG
        esac
      done
      set +f
    fi
    if [ "$rm_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
      exit 0                                # 許可ゾーン配下の削除のみ → 許可
    fi
    ;;
  git)
    # git rm のみ: rm 同等の配下チェックを通れば許可（連結は安全文字チェックで弾く）
    if [ "$(printf '%s' "$COMMAND" | awk 'NR==1{print $2}')" = "rm" ]; then
      rm_allowed=1
      printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && rm_allowed=0
      printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && rm_allowed=0
      had_target=0
      if [ "$rm_allowed" -eq 1 ]; then
        set -f
        for tok in $COMMAND; do
          case "$tok" in
            git | rm) continue ;;             # コマンド名・サブコマンド
            -*) continue ;;                   # フラグ（--cached, -r, -f 等）
          esac
          had_target=1
          abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
          [ -z "$abs" ] && { rm_allowed=0; break; }
          case "$abs" in
            "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;  # 3ゾーンいずれかの子要素 → OK
            *) rm_allowed=0; break ;;                          # ゾーン外 → NG
          esac
        done
        set +f
      fi
      if [ "$rm_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
        exit 0                                # 許可ゾーン配下の git rm のみ許可
      fi
    fi
    ;;
esac

# ── find -delete: プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の子要素のみ許可 ──
# find の path 指定はコマンド直後にまとまるため、最初のオプション(-*)出現までを
# 対象パスとみなす。-delete を含まない find は対象外（従来通り無条件許可）。
# トリガー判定はコマンド全体に対して行う（cd混在等で先頭トークンがfindでない
# 複合コマンドも、ゾーン判定を通らなければ下のブロックへフォールスルーさせるため）。
FIND_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
# (?<!-)-delete で rsync の --delete と誤マッチしないようにする（find -delete 専用）。
if printf '%s' "$COMMAND" | grep -qiP '\bfind\b' && printf '%s' "$COMMAND" | grep -qiP -- '(?<!-)-delete\b'; then
  find_allowed=0
  had_target=0
  if [ "$FIND_FIRST" = "find" ]; then
    find_allowed=1
    printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && find_allowed=0
    printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && find_allowed=0
    # -exec/-execdir/-ok/-okdir や -fprint系はゾーン外ファイルを操作・破壊できるため、
    # path列挙を打ち切った式部分に含まれていたら不許可（対象パス検査の対象外になるため）。
    printf '%s' "$COMMAND" | grep -qiP -- '-(exec|execdir|ok|okdir|fprint0?|fprintf|fls)\b' && find_allowed=0
    if [ "$find_allowed" -eq 1 ]; then
      set -f
      for tok in $COMMAND; do
        case "$tok" in
          find) continue ;;
          -*) break ;;                        # 最初のオプション以降は式なのでpath列挙終了
        esac
        had_target=1
        abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
        [ -z "$abs" ] && { find_allowed=0; break; }
        case "$abs" in
          "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;
          *) find_allowed=0; break ;;
        esac
      done
      set +f
    fi
  fi
  if [ "$find_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
    exit 0
  fi
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   find -delete はプロジェクト配下($PROJECT_DIR)／\$CLAUDE_HOME配下($CLAUDE_HOME)／/tmp配下の子要素に対してのみ許可されています。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

# ── rsync --delete: プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の子要素のみ許可 ──
# --delete系オプション（--del/--delete/--delete-before/--delete-during/--delete-delay/
# --delete-after/--delete-excluded/--delete-missing-args）を含まない rsync は対象外
# （従来通り無条件許可）。--delは--delete-duringのrsync公式エイリアス。
# トリガー判定はコマンド全体に対して行う（cd混在等のフォールスルー対策、find参照）。
# 注: 安全文字集合の`:`はWindowsパス（C:/...）向けだが、rsyncは最初のスラッシュより
# 前に`:`があるとHOST:PATH（リモート）構文と解釈する。C:/...形式はrsync自体がリモート
# ホスト指定と誤解釈し接続失敗するため、rsyncゾーンでは実質的に機能しない（fail-inert、
# ゾーン外への書き込みには繋がらないためブロッカーとしては許容）。
RSYNC_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
if printf '%s' "$COMMAND" | grep -qiP '\brsync\b' && printf '%s' "$COMMAND" | grep -qiP -- '--del(ete)?\b'; then
  rsync_allowed=0
  had_target=0
  if [ "$RSYNC_FIRST" = "rsync" ]; then
    rsync_allowed=1
    printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && rsync_allowed=0
    printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && rsync_allowed=0
    if [ "$rsync_allowed" -eq 1 ]; then
      set -f
      for tok in $COMMAND; do
        case "$tok" in
          rsync) continue ;;
          -*) continue ;;
        esac
        had_target=1
        abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
        [ -z "$abs" ] && { rsync_allowed=0; break; }
        case "$abs" in
          "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;
          *) rsync_allowed=0; break ;;
        esac
      done
      set +f
    fi
  fi
  if [ "$rsync_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
    exit 0
  fi
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   rsync --delete はプロジェクト配下($PROJECT_DIR)／\$CLAUDE_HOME配下($CLAUDE_HOME)／/tmp配下の子要素に対してのみ許可されています。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

# ── chmod 000 / chmod -R 777: プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の子要素のみ許可 ──
# 最初の非フラグトークンはモード引数として無条件スキップ（数値・シンボリック問わず）、
# それ以降の非フラグトークンのみを対象パスとみなす。000/-R 777 以外の chmod は対象外
# （シンボリックモードでの全開放/全剥奪はスコープ外・既存の弱点のまま）。
# トリガー判定は「先頭トークンがchmodで、最初の非フラグトークン(モード引数)が
# 000/0000/777/0777相当」を主とし、フラグ順序(chmod 777 -R等)・桁数(0777等)の
# バリエーションを吸収する。先頭トークンがchmodでない複合コマンド（cd混在等）は
# 解析できないため、粗いパターン一致のみで安全側にトリガーする。
CHMOD_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
CHMOD_MODE=""
if [ "$CHMOD_FIRST" = "chmod" ]; then
  set -f
  for tok in $COMMAND; do
    case "$tok" in
      chmod) continue ;;
      -*) continue ;;
    esac
    CHMOD_MODE="$tok"
    break
  done
  set +f
fi
chmod_trigger=0
case "$CHMOD_MODE" in
  0 | 00 | 000 | 0000 | 7 | 77 | 777 | 0777) chmod_trigger=1 ;;
esac
if [ "$chmod_trigger" -eq 0 ]; then
  printf '%s' "$COMMAND" | grep -qiP '(chmod\s+.*000|chmod\s+-R\s+777\s+/)' && chmod_trigger=1
fi
if [ "$chmod_trigger" -eq 1 ]; then
  chmod_allowed=0
  had_target=0
  if [ "$CHMOD_FIRST" = "chmod" ]; then
    chmod_allowed=1
    printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && chmod_allowed=0
    printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && chmod_allowed=0
    if [ "$chmod_allowed" -eq 1 ]; then
      set -f
      mode_consumed=0
      for tok in $COMMAND; do
        case "$tok" in
          chmod) continue ;;
          -*) continue ;;
        esac
        if [ "$mode_consumed" -eq 0 ]; then
          mode_consumed=1
          continue                              # 最初の非フラグトークン = モード引数
        fi
        had_target=1
        abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
        [ -z "$abs" ] && { chmod_allowed=0; break; }
        case "$abs" in
          "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;
          *) chmod_allowed=0; break ;;
        esac
      done
      set +f
    fi
  fi
  if [ "$chmod_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
    exit 0
  fi
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   chmod 000/-R 777 はプロジェクト配下($PROJECT_DIR)／\$CLAUDE_HOME配下($CLAUDE_HOME)／/tmp配下の子要素に対してのみ許可されています。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

# ── 機密ファイル読取: プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の子要素のみ許可 ──
# cat/less/more/head/tail/base64/xxd/od/stringsで.env/.ssh/id_rsa/credentials等
# 「らしき」対象に触れるコマンドが対象。読取自体は場所を問わず機密性が変わらないため
# 本来はゾーン判定より無条件ブロックの方が安全だが、使い捨てのテスト用フィクスチャ
# （/tmp配下やプロジェクト配下の作業ファイル）まで一律ブロックする運用コストとの
# トレードオフとして、他の破壊的操作と同じゾーン判定方式に揃える（ユーザー承認済み）。
# パイプ・リダイレクト・複合コマンド・改行・cd・安全文字集合外の文字を含む場合は
# 解析不能として従来通りブロックへフォールバックする。
READ_FIRST=$(printf '%s' "$COMMAND" | awk 'NR==1{print $1}')
if printf '%s' "$COMMAND" | grep -qiP '\b(cat|less|more|head|tail|base64|xxd|od|strings)\s+.*(\.env(\.|\s|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|$)|\.key(\s|$)|authorized_keys|\.netrc|credentials)'; then
  read_allowed=0
  had_target=0
  case "$READ_FIRST" in
    cat | less | more | head | tail | base64 | xxd | od | strings)
      read_allowed=1
      printf '%s' "$COMMAND" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./:-]' && read_allowed=0
      printf '%s' "$COMMAND" | grep -qiP '\bcd\b' && read_allowed=0
      if [ "$read_allowed" -eq 1 ]; then
        set -f
        idx=0
        for tok in $COMMAND; do
          idx=$((idx + 1))
          if [ "$idx" -eq 1 ]; then continue; fi   # コマンド名は先頭トークン(位置)でスキップ
          case "$tok" in
            -*) continue ;;
          esac
          had_target=1
          abs=$(to_posix "$(realpath -m "$tok" 2>/dev/null)")
          [ -z "$abs" ] && { read_allowed=0; break; }
          case "$abs" in
            "$PROJECT_DIR"/* | "$CLAUDE_HOME"/* | /tmp/*) ;;
            *) read_allowed=0; break ;;
          esac
        done
        set +f
      fi
      ;;
  esac
  if [ "$read_allowed" -eq 1 ] && [ "$had_target" -eq 1 ]; then
    exit 0
  fi
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   機密ファイルの読取はプロジェクト配下($PROJECT_DIR)／\$CLAUDE_HOME配下($CLAUDE_HOME)／/tmp配下の子要素に対してのみ許可されています。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

# 上で許可されなかった rm/rmdir/unlink 呼び出しはブロック（末尾形も捕捉）
if printf '%s' "$COMMAND" | grep -qiP '\b(rm|rmdir|unlink)(\s|$)'; then
  echo "❌ BLOCKED: $COMMAND" >&2
  echo "   rm 等はプロジェクト配下($PROJECT_DIR)／\$CLAUDE_HOME配下($CLAUDE_HOME)／/tmp配下の子要素削除のみ許可されています（各ゾーン外/ルート自体/パイプ・連結・wrapper 経由は不可）。" >&2
  echo "このコマンドはポリシーによりブロックされました。自分では実行せず、ユーザーに次のコマンドを実行するよう依頼してください（! プレフィックス推奨）: ${COMMAND}"
  exit 2
fi

exit 0
