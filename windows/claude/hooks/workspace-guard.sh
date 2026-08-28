#!/bin/bash
# workspace-guard.sh — PreToolUse フック
# プロジェクト配下・~/.claude 配下・Claude Code のセッション用一時ディレクトリ
# (/tmp/claude-*/配下、Windowsでは */[Tt]emp/claude/*配下)以外へのファイル作成・
# 編集をブロックする。
# Write/Edit/MultiEdit/NotebookEdit: 対象 file_path が許可ゾーン外なら exit 2。
# Bash:
#   - リダイレクト(> / >>)の汎用ゾーン判定: /var/tmp・および /tmp/claude-*/以外の
#     /tmp 配下への書き込みをブロック（/dev/null等の疑似デバイス・fd複製>&Nは除外）。
#   - cp/tee/mv/curl/wget のプロジェクト外宛先を保守的にブロック。
#   - rm/rmdir/unlink・git rm・find -delete・rsync --delete・chmod 000/-R777・
#     git clean -fd・機密ファイル読取(cat/less/head等で.env/.ssh/id_rsa等)の
#     7カテゴリをゾーン判定でブロック（旧bash-guard.shから移設。トリガー検知は
#     位置非依存の正規表現で行い、sudo等でラップされたケースも捕捉する）。
#
# 許可ゾーン（Write/Edit/リダイレクト/cp等）:
#   1) プロジェクトルート($PROJECT_DIR=pwd)配下
#   2) ~/.claude(=${CLAUDE_CONFIG_DIR:-$HOME/.claude})配下（hooks/settings.json含む。
#      設定管理ワークフロー自体がhooks/settingsの編集を要するため自己防御は設けない。
#      settings.json の permissions.ask 側で実行前確認を挟む二重防御に委ねる）
#   3) /tmp/claude-*/配下（Claude Code自身のセッション固有一時ディレクトリ:
#      スクラッチパッド・サブエージェントのタスク出力等。/tmp 直下や無関係な
#      /tmp配下ディレクトリ、/var/tmp は対象外）
#   4) */[Tt]emp/claude/*配下（Windows: %LOCALAPPDATA%\Temp\claude\<project>\<session>\
#      配下。上記3)のWindows版セッション用スクラッチパッド）
#
# 許可ゾーン（rm/git rm/find -delete/rsync --delete/chmod/git clean -fd/機密読取の
# 7カテゴリ専用。_wg_tok_in_zone参照）:
#   1) プロジェクトルート配下（ルート自体は除く。子要素のみ）
#   2) $CLAUDE_HOME配下（ルート自体は除く。子要素のみ）
#   3) /tmp 配下全体（旧bash-guard.shと同じ広い範囲。上記の/tmp/claude-*/限定とは
#      意図的に異なる）
#   4) */[Tt]emp/claude/*配下（Windows版セッション用スクラッチパッド。3)のWindows版）
#
# 既知の限界: Bash のファイル書き込み全検出は不可能なため /var/tmp・/tmp(claude-*以外)
# リダイレクト＋ cp/tee/mv/curl/wget の主要経路のみ検査（完全検出ではない）。
# 文字列中に "> /var/tmp/" 等を含むコマンド(grep 等)は誤ブロックされ得る。
# その場合は Read ツールで回避すること（bash-guard.sh / venv-guard.sh と同種の制約）。
# is_ext_dest()（cp/tee/mv/curl/wget・リダイレクト共用）は $VAR 形式の宛先（例:
# $HOME/.bashrc）を判定不能として保守的に素通しする（詳細は is_ext_dest() 参照）。

# jq 不在時は fail-close（PreToolUse ガードなので判定不能なら安全側に倒して exit 2）。
command -v jq >/dev/null 2>&1 || { echo "❌ workspace-guard: jq not found, failing closed" >&2; exit 2; }

# ── Windows(Git Bash)対応 ──────────────────────────────────────────
# 1) 既定ロケール(CP932等)では grep -P が "supports only unibyte and UTF-8 locales"
#    で失敗し終了ステータス2を返す。下の判定は全て `if ... grep -qiP ...; then` 形式で、
#    エラー(2)は「不一致」と同じ扱いになるため、ロケールを明示しないと危険パターン
#    判定・ゾーン判定が黙って fail-open する。
# 2) フックに渡る file_path・コマンド中のパスは Windows 形式(C:\...)になり得るが
#    $(pwd)/$HOME は MSYS 形式(/c/...)。MSYS の realpath は C:\x を C:/x に直すだけで
#    /c/x にはしないため、正規化しないと前方一致比較が必ず失敗する。
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
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
PROJECT_DIR=$(to_posix "$(pwd)")
CLAUDE_HOME=$(to_posix "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")

is_allowed() {
  local path="$1"
  local abs
  # 未存在ファイルも解決（相対パスは PROJECT_DIR 基準）
  abs=$(realpath -m "$path" 2>/dev/null) || abs="$path"
  abs=$(to_posix "$abs")
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 0 ;;
    /tmp/claude-*/*) return 0 ;;  # Claude Code 自身のセッション用ディレクトリのみ許可
    */[Tt]emp/claude/*) return 0 ;;  # Windows: %LOCALAPPDATA%\Temp\claude\<project>\<session>\ 配下
    *) return 1 ;;
  esac
}

# cp/tee/mv/curl/wget 宛先の外部判定（保守的）。
# 絶対パスのみ検査し、相対/判定不能はブロックしない。
# 既知の限界: $HOME/.bashrc のような変数展開形式の宛先は判定不能のため保守的に
# 許可（素通し）する。~/.bashrc 形式（チルダ展開）はチルダ展開のみ明示的にケアして
# いるためブロックできるが、$VAR形式は静的に値を確定できないため対象外（bash-guard.sh
# の機密ファイル読取ワンライナー判定と同種の割り切り）。
is_ext_dest() {
  local path="$1" abs
  case "$path" in
    \~/*) path="$HOME/${path#\~/}" ;;  # ~/... を $HOME 基準の絶対パスへ展開（~はcaseパターン解析時に
    \~) path="$HOME" ;;                # チルダ展開されるため \~ でエスケープ必須）
  esac
  path=$(to_posix "$path")
  case "$path" in
    /*) ;;         # 明確な絶対パスのみを検査対象とする
    *) return 1 ;; # 相対パス等は保守的にスルー（ブロックしない）
  esac
  abs=$(realpath -m "$path" 2>/dev/null) || return 1
  abs=$(to_posix "$abs")
  case "$abs" in
    "$PROJECT_DIR" | "$PROJECT_DIR"/*) return 1 ;; # プロジェクト配下 → 許可
    "$CLAUDE_HOME" | "$CLAUDE_HOME"/*) return 1 ;; # $CLAUDE_HOME 配下 → 許可
    /tmp/claude-*/*) return 1 ;;                   # /tmp/claude-* セッション用ディレクトリのみ許可
    */[Tt]emp/claude/*) return 1 ;;                # Windows: Temp\claude\ 配下(スクラッチパッド)も許可
    *) return 0 ;;                                 # 明確な外部絶対パス → ブロック対象
  esac
}

# ── normalize(): bash-guard.shと同一の難読化正規化(移植) ──
normalize() {
  printf '%s' "$1" | tr -d "\"'\\\\" | sed -E 's/\$\{?IFS\}?/ /g'
}

# ── トリガー正規表現の単一ソーステーブル。難読化再判定(_wg_check_obfuscation)と
#    通常分岐(wg_check_fragment)の両方がここを参照する。将来カテゴリ追加時は
#    この1箇所を更新すれば両方に反映される（片方だけ更新して検知漏れが生じる
#    事故を防ぐ、実装上の必須要件）。
#    例外(2件、意図的な非対称): chmod と secret(機密読取) は「危険なケースのみ」を
#    通常分岐のトリガーとするため専用関数(_wg_chmod_trigger/_wg_secret_trigger)を
#    使う。本テーブルの[chmod]/[secret]エントリは難読化再判定専用の粗いパターン
#    （chmodは全chmod対象・secretはコマンド名のみでファイル名条件なし）であり、
#    通常分岐では参照しない。難読化で構造検証自体が迂回されうる場面では、危険性を
#    厳密判定できない代わりに保守的にブロックする側に倒すため。通常分岐に粗い
#    パターンをそのまま使うと、無害な chmod 644 や cat 呼び出しまでゾーン判定に
#    かかってしまう regression になる。
declare -A WG_TRIGGER=(
  [gitrm]='\bgit\s+rm\b'
  [rm]='\b(rm|rmdir|unlink)\b'
  [gitclean]='\bgit\s+clean\s+-[a-z]*f[a-z]*d\b'
  [find]='\bfind\b.*(?<!-)-delete\b'
  [rsync]='\brsync\b.*--del(ete)?\b'
  [chmod]='\bchmod\b'
  [secret]='\b(cat|less|more|head|tail|base64|xxd|od|strings)\b'
)

# 断片が安全文字集合外(=解析不能)を含むか
# 安全文字集合に`:`は含めない(脆弱性教訓: `:`を安全文字に含めると
# rsyncの`HOST:PATH`リモートシェル構文（例: evilhost:/etc/passwd）が
# 「解析可能」として素通りし、_wg_tok_in_zoneのrealpath -mがコロンを
# ただの文字として扱って$PROJECT_DIR配下の奇妙なファイル名に誤解決し、
# ゾーン内と誤判定してしまう。実際のrsyncはこれをSSH経由のリモート宛先と
# 解釈するため、ゾーン判定が完全にすり抜けてしまう)。
# 代わりに、正当なWindowsドライブレターパス(`C:/x`形式)由来のコロンは
# wg_check_fragment()側で事前に正規化(_wg_norm_drive_colon)して除去して
# おくため、ここで`:`を許可しなくても支障はない。
# `\`(バックスラッシュ)は意図的に含めない: realpath -m によるゾーン判定と
# bashの実際の展開(エスケープ解釈)が乖離しパストラバーサルが成立し得るため、
# Windowsパスは`C:/Users/...`のスラッシュ形式でのみゾーン判定を通過でき、
# `C:\Users\...`のバックスラッシュ形式は引き続き解析不能としてブロックされる
# (意図的な設計)。
_wg_frag_unsafe() {
  printf '%s' "$1" | tr '\n' '\v' | grep -qP '[^A-Za-z0-9 \t_./-]'
}

# ドライブレターパスの事前正規化(_wg_frag_unsafe呼び出し前)。
# _wg_frag_unsafe()の安全文字集合から`:`を除去した代わりに、正当なWindows
# ドライブレターパス(`C:/x`形式)由来のコロンだけを事前に取り除く。バックスラッシュ
# 形式(`C:\x`)は意図的に対象外のまま(上記_wg_frag_unsafeのコメント通り、
# 解析不能として引き続きブロックされる設計を変更しない)。
# トークン単位で判定するのは、フラグメント全体(例: "rsync -a --delete C:/x C:/y")に
# 単純に前方一致パターンを適用すると先頭トークンしか正規化できないため
# (to_posix()の`[A-Za-z]:/*`判定パターンをトークン単位に拡張して流用)。
# rsyncのHOST:PATH構文(例: evilhost:/etc/passwd)は「1文字+コロン+スラッシュ」の
# 形に一致しないため正規化されず、コロンを含んだまま_wg_frag_unsafeに渡り
# 解析不能としてブロックされ続ける(意図した挙動)。
_wg_norm_drive_colon() {
  local frag="$1" out="" tok first=1
  set -f
  for tok in $frag; do
    case "$tok" in
      [A-Za-z]:/*) tok="/$(printf '%s' "${tok%%:*}" | tr 'A-Z' 'a-z')${tok#*:}" ;;
    esac
    if [ "$first" -eq 1 ]; then out="$tok"; first=0; else out="$out $tok"; fi
  done
  set +f
  printf '%s' "$out"
}

# 断片にcd/pushd/popdが含まれるか(cwd変化でrealpath -m基準がズレる)
_wg_frag_has_cd() {
  printf '%s' "$1" | grep -qiP '\b(cd|pushd|popd)\b'
}

# トークンが4ゾーン(プロジェクト配下/$CLAUDE_HOME配下/tmp配下/Windows Temp\claude\配下)内か。
# 旧bash-guard.shのrm系ゾーン判定を踏襲し、各ゾームの「子要素」のみを許可対象とする
# （ゾーンルート自体の一致は含めない。is_allowed()はWrite/Edit用でルート自体も許可対象と
#  なるが、rm等の削除系はゾーンルート自体を対象にできると配下ごと消去できてしまうため、
#  意図的に is_allowed() とは異なる判定にしている＝実装上の必須要件）。
# 3ゾーン目は /tmp/* 全体（旧bash-guard.shと同じ範囲）。is_allowed()/is_ext_dest()の
# /tmp/claude-*/配下限定(セッション用スクラッチパッドのみ)とは意図的に異なる、広い範囲。
# rm/find/rsync/chmod/機密読取等の削除・破壊的操作は旧bash-guard.shが元々/tmp全体を
# 許可対象としていたため、その挙動を変えない（狭めると旧実装からの意図しない仕様変更に
# なる。ブリーフの当初記述が誤ってworkspace-guard.sh既存の狭いセッション専用ゾーン定義を
# 7カテゴリに流用してしまっていたための是正）。
# 4ゾーン目(*/[Tt]emp/claude/*)はWindows版セッション用スクラッチパッド(is_allowed()/
# is_ext_dest()の4)と同一パターン)。realpath -m の結果は to_posix() で正規化してから
# 比較する（Windows(msys/cygwin)でのバックスラッシュ→スラッシュ変換・ドライブレター
# 小文字化・パス全体の大文字小文字統一。ここへの適用漏れは7カテゴリのゾーン判定全体が
# Windows実機で誤ブロックする regression になる＝実装上の必須要件）。
_wg_tok_in_zone() {
  local abs
  abs=$(realpath -m "$1" 2>/dev/null) || return 1
  abs=$(to_posix "$abs")
  # ゾーンルート自体（$PROJECT_DIR/$CLAUDE_HOME自体）は常に不許可。/tmp/*が広範な
  # ため、$PROJECT_DIRが偶然/tmp配下にある場合(例: /tmp/claude-*/配下で作業している
  # セッション)にzone3経由でルート除外がすり抜けてしまう相互作用を防ぐため、
  # zone判定に入る前に明示的除外する（実装上の必須要件）。
  case "$abs" in
    "$PROJECT_DIR" | "$CLAUDE_HOME") return 1 ;;
  esac
  case "$abs" in
    "$PROJECT_DIR"/*) return 0 ;;
    "$CLAUDE_HOME"/*) return 0 ;;
    /tmp/*) return 0 ;;
    */[Tt]emp/claude/*) return 0 ;;
    *) return 1 ;;
  esac
}

# rm/rmdir/unlink・git rm・git clean -fd 用の共通構造検証。
# skip引数（例: rm 一語、git rm 二語、git clean 二語）だけコマンド名として
# スキップし、残りの非フラグトークン全てがゾーン内かを検証する。
# トリガー検知（このコマンド種別かどうかの判定）はこの関数の外、呼び出し側で
# 位置非依存の正規表現により行うこと（下記wg_check_fragment参照）。
_wg_check_simple_zone_cmd() {
  local frag="$1"; shift
  local -a skip=("$@")
  local i=1
  for w in "${skip[@]}"; do
    [ "$(printf '%s' "$frag" | awk -v n="$i" 'NR==1{print $n}')" = "$w" ] || return 1
    i=$((i + 1))
  done
  _wg_frag_unsafe "$frag" && return 1
  _wg_frag_has_cd "$frag" && return 1
  local had_target=0 tok idx=0
  set -f
  for tok in $frag; do
    idx=$((idx + 1))
    [ "$idx" -le "${#skip[@]}" ] && continue
    case "$tok" in -*) continue ;; esac
    had_target=1
    _wg_tok_in_zone "$tok" || { set +f; return 1; }
  done
  set +f
  [ "$had_target" -eq 1 ]
}

# find -delete: findコマンド自身が先頭トークンであることは要求する
# （findは通常sudoで包む必要のあるコマンドではないため、findについては
#  先頭トークン一致で問題ない。ただし-exec等が含まれる場合は無条件不許可）
_wg_check_find_zone() {
  local frag="$1"
  [ "$(printf '%s' "$frag" | awk 'NR==1{print $1}')" = find ] || return 1
  _wg_frag_unsafe "$frag" && return 1
  _wg_frag_has_cd "$frag" && return 1
  printf '%s' "$frag" | grep -qiP -- '-(exec|execdir|ok|okdir|fprint0?|fprintf|fls)\b' && return 1
  local had_target=0 tok
  set -f
  for tok in $frag; do
    case "$tok" in find) continue ;; -*) break ;; esac
    had_target=1
    _wg_tok_in_zone "$tok" || { set +f; return 1; }
  done
  set +f
  [ "$had_target" -eq 1 ]
}

# rsync --delete(--delエイリアス含む): フラグ以外の全トークンがゾーン内
_wg_check_rsync_zone() {
  local frag="$1"
  [ "$(printf '%s' "$frag" | awk 'NR==1{print $1}')" = rsync ] || return 1
  _wg_frag_unsafe "$frag" && return 1
  _wg_frag_has_cd "$frag" && return 1
  local had_target=0 tok
  set -f
  for tok in $frag; do
    case "$tok" in rsync) continue ;; -*) continue ;; esac
    had_target=1
    _wg_tok_in_zone "$tok" || { set +f; return 1; }
  done
  set +f
  [ "$had_target" -eq 1 ]
}

# chmod 000/-R777: 最初の非フラグトークンはモード引数としてスキップ
_wg_chmod_trigger() {
  local frag="$1" mode="" tok
  if [ "$(printf '%s' "$frag" | awk 'NR==1{print $1}')" = chmod ]; then
    set -f
    for tok in $frag; do
      case "$tok" in chmod) continue ;; -*) continue ;; esac
      mode="$tok"; break
    done
    set +f
  fi
  case "$mode" in 0|00|000|0000|7|77|777|0777) return 0 ;; esac
  printf '%s' "$frag" | grep -qiP '(chmod\s+.*000|chmod\s+-R\s+777\s+/)'
}
_wg_check_chmod_zone() {
  local frag="$1"
  [ "$(printf '%s' "$frag" | awk 'NR==1{print $1}')" = chmod ] || return 1
  _wg_frag_unsafe "$frag" && return 1
  _wg_frag_has_cd "$frag" && return 1
  local had_target=0 mode_consumed=0 tok
  set -f
  for tok in $frag; do
    case "$tok" in chmod) continue ;; -*) continue ;; esac
    if [ "$mode_consumed" -eq 0 ]; then mode_consumed=1; continue; fi
    had_target=1
    _wg_tok_in_zone "$tok" || { set +f; return 1; }
  done
  set +f
  [ "$had_target" -eq 1 ]
}

# 機密ファイル読取: cat/less/.../strings で.env/.ssh/id_rsa等らしき対象に触れる場合
_wg_secret_trigger() {
  printf '%s' "$1" | grep -qiP '\b(cat|less|more|head|tail|base64|xxd|od|strings)\s+.*(\.env(\.|\s|$)|\.ssh/|id_rsa|id_ed25519|\.pem(\s|$)|\.key(\s|$)|authorized_keys|\.netrc|credentials)'
}
_wg_check_secret_zone() {
  local frag="$1"
  case "$(printf '%s' "$frag" | awk 'NR==1{print $1}')" in
    cat|less|more|head|tail|base64|xxd|od|strings) ;;
    *) return 1 ;;
  esac
  _wg_frag_unsafe "$frag" && return 1
  _wg_frag_has_cd "$frag" && return 1
  local had_target=0 idx=0 tok
  set -f
  for tok in $frag; do
    idx=$((idx + 1)); [ "$idx" -eq 1 ] && continue
    case "$tok" in -*) continue ;; esac
    had_target=1
    _wg_tok_in_zone "$tok" || { set +f; return 1; }
  done
  set +f
  [ "$had_target" -eq 1 ]
}

_wg_check_gitclean_zone() {
  _wg_check_simple_zone_cmd "$1" git clean
}

# ── 難読化(クォート分割/${IFS}等)によるトリガー正規表現迂回の再判定 ──
_wg_check_obfuscation() {
  local frag="$1" frag_n pattern key
  frag_n=$(normalize "$frag")
  [ "$frag_n" = "$frag" ] && return 0
  for key in "${!WG_TRIGGER[@]}"; do
    pattern="${WG_TRIGGER[$key]}"
    if printf '%s' "$frag_n" | grep -qiP "$pattern" \
       && ! printf '%s' "$frag" | grep -qiP "$pattern"; then
      echo "❌ BLOCKED: $CMD" >&2
      echo "   クォート分割/バックスラッシュ/\${IFS}等の難読化を検知しました: $pattern" >&2
      return 1
    fi
  done
  return 0
}

# ── リダイレクト(>/>>)の汎用ゾーン判定。/dev/null等の疑似デバイスと
#    fd複製(>&N)は必ず除外すること(実装上の必須要件。誤検知防止)。
#    fd番号は[0-9]*(0桁以上)で受けること。[0-9]?(1桁のみ)にすると
#    "10>/etc/x"のような2桁以上のfd番号でマッチ自体が失敗し、is_ext_destが
#    一度も呼ばれず無検査で許可されるCRITICALなバイパス経路になる ──
_wg_redirect_ext_hit() {
  local frag="$1" dest
  while IFS= read -r dest; do
    [ -z "$dest" ] && continue
    case "$dest" in
      '&'[0-9]) continue ;;
      /dev/null|/dev/stdout|/dev/stderr|/dev/tty) continue ;;
    esac
    dest="${dest%\"}"; dest="${dest#\"}"; dest="${dest%\'}"; dest="${dest#\'}"
    if is_ext_dest "$dest"; then printf '%s' "$dest"; return 0; fi
  done < <(printf '%s' "$frag" | grep -oP '(?:^|[^0-9>])[0-9]*>{1,2}\s*\K[^\s;|&<>]+')
  return 1
}

# ── 1フラグメントに対する全チェックの統括 ──
wg_check_fragment() {
  local frag ext_hit
  frag=$(_wg_norm_drive_colon "$1")
  _wg_check_obfuscation "$frag" || return 1

  ext_hit=$(_wg_redirect_ext_hit "$frag") && {
    echo "❌ BLOCKED: プロジェクト外へのリダイレクト書き込み: $ext_hit" >&2
    echo "   宛先がプロジェクト配下・\$CLAUDE_HOME配下・/tmp/claude-*/配下のいずれでもありません。" >&2
    return 1
  }

  # git rm は「rm」を単語として含むため、generic rm/rmdir/unlink トリガー
  # (\brm\b)より先に判定する必要がある(実装上の必須要件。順序を入れ替えると
  # 常にgeneric rm分岐に先取りされ、"git rm --cached <zone内>"が誤ブロックされる)。
  if printf '%s' "$frag" | grep -qiP "${WG_TRIGGER[gitrm]}"; then
    _wg_check_simple_zone_cmd "$frag" git rm && return 0
    echo "❌ BLOCKED: git rm はゾーン内のみ許可: $CMD" >&2
    return 1
  fi
  if printf '%s' "$frag" | grep -qiP "${WG_TRIGGER[rm]}"; then
    _wg_check_simple_zone_cmd "$frag" rm    && return 0
    _wg_check_simple_zone_cmd "$frag" rmdir && return 0
    _wg_check_simple_zone_cmd "$frag" unlink && return 0
    echo "❌ BLOCKED: rm等はプロジェクト配下/\$CLAUDE_HOME配下/セッション用tmp配下の子要素のみ許可: $CMD" >&2
    return 1
  fi
  if printf '%s' "$frag" | grep -qiP "${WG_TRIGGER[gitclean]}"; then
    _wg_check_gitclean_zone "$frag" && return 0
    echo "❌ BLOCKED: git clean -fd はゾーン内の明示パス指定のみ許可(パスなしは不可): $CMD" >&2
    return 1
  fi
  if printf '%s' "$frag" | grep -qiP "${WG_TRIGGER[find]}"; then
    _wg_check_find_zone "$frag" && return 0
    echo "❌ BLOCKED: find -delete はゾーン内のみ許可: $CMD" >&2
    return 1
  fi
  if printf '%s' "$frag" | grep -qiP "${WG_TRIGGER[rsync]}"; then
    _wg_check_rsync_zone "$frag" && return 0
    echo "❌ BLOCKED: rsync --delete はゾーン内のみ許可: $CMD" >&2
    return 1
  fi
  if _wg_chmod_trigger "$frag"; then
    _wg_check_chmod_zone "$frag" && return 0
    echo "❌ BLOCKED: chmod 000/-R777 はゾーン内のみ許可: $CMD" >&2
    return 1
  fi
  if _wg_secret_trigger "$frag"; then
    _wg_check_secret_zone "$frag" && return 0
    echo "❌ BLOCKED: 機密ファイル読取はゾーン内のみ許可: $CMD" >&2
    return 1
  fi
  return 0
}

case "$TOOL" in
  Write | Edit | MultiEdit | NotebookEdit)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [ -z "$FILE" ] && exit 0
    if ! is_allowed "$FILE"; then
      echo "❌ BLOCKED: プロジェクト外への書き込み: $FILE" >&2
      echo "   許可範囲: プロジェクト配下($PROJECT_DIR) または $CLAUDE_HOME 配下 または /tmp/claude-*/配下" >&2
      echo "   一時ファイルが必要ならプロジェクト配下、または現在のセッションのスクラッチパッド" >&2
      echo "   ディレクトリ(/tmp/claude-*/配下、システムプロンプトで案内されているパス)に作成してください。" >&2
      exit 2
    fi
    ;;
  Bash)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

    # ── 複合コマンド分割(bash-guard.shのSPLIT_OK/FRAGMENTSからの移植) ──
    SPLIT_OK=1
    printf '%s' "$CMD" | grep -qP '\$\(|`' && SPLIT_OK=0
    printf '%s' "$CMD" | grep -qiP '\b(cd|pushd|popd)\b' && SPLIT_OK=0
    if [ "$SPLIT_OK" -eq 1 ]; then
      mapfile -t WG_FRAGMENTS < <(printf '%s' "$CMD" | sed -E 's/(&&|;|\|)/\n/g')
    else
      WG_FRAGMENTS=("$CMD")
    fi
    for frag in "${WG_FRAGMENTS[@]}"; do
      [ -z "$(printf '%s' "$frag" | tr -d '[:space:]')" ] && continue
      wg_check_fragment "$frag" || exit 2
    done

    # ── cp/tee/mv/curl/wget のプロジェクト外書き込みを保守的にブロック ──────────────
    # 主要経路のみ・完全検出ではない（複雑な引数・エイリアス等は検出外）。
    # 明確な外部絶対パス宛先($HOME 直下や許可ゾーン外の絶対パス)のみを対象とする。
    # コマンド置換を含むセグメントは宛先を確定できないため保守的にスルーする。
    SEGMENTS=$(printf '%s' "$CMD" | sed -E 's/\|\||&&|;|\|/\n/g')
    ext_hit=""
    set -f
    while IFS= read -r seg; do
      printf '%s' "$seg" | grep -qE '`|\$\(' && continue   # コマンド置換 → スルー
      set -- $seg
      [ $# -eq 0 ] && continue
      c="$1"
      case "$c" in
        cp | mv)
          target="" prev=""
          for tok in "$@"; do
            case "$prev" in -t) target="$tok" ;; esac
            case "$tok" in --target-directory=*) target="${tok#--target-directory=}" ;; esac
            prev="$tok"
            last="$tok"
          done
          if [ -n "$target" ]; then
            is_ext_dest "$target" && ext_hit="$target"
          else
            is_ext_dest "$last" && ext_hit="$last"  # -t/--target-directory 未指定時は最終引数を宛先とみなす
          fi
          ;;
        tee)
          shift
          for tok in "$@"; do
            case "$tok" in -*) continue ;; esac
            is_ext_dest "$tok" && { ext_hit="$tok"; break; }
          done
          ;;
        curl | wget)
          prev=""
          for tok in "$@"; do
            case "$prev" in
              -o | -O | --output | --output-document) is_ext_dest "$tok" && { ext_hit="$tok"; break; } ;;
            esac
            case "$tok" in
              --output=* | --output-document=*) v="${tok#*=}"; is_ext_dest "$v" && { ext_hit="$v"; break; } ;;
            esac
            prev="$tok"
          done
          ;;
      esac
      [ -n "$ext_hit" ] && break
    done <<EOF
$SEGMENTS
EOF
    set +f
    if [ -n "$ext_hit" ]; then
      echo "❌ BLOCKED: プロジェクト外への cp/tee/mv/curl/wget 書き込み: $ext_hit" >&2
      echo "   宛先がプロジェクト配下・$CLAUDE_HOME 配下・/tmp/claude-*/配下(セッション用ディレクトリ)" >&2
      echo "   のいずれでもありません。" >&2
      echo "   ※主要経路のみの保守的検査です。誤検知時は宛先をプロジェクト配下にするか手動実行してください。" >&2
      exit 2
    fi
    ;;
esac

exit 0
