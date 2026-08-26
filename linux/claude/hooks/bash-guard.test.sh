#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/bash-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t.com
git -C "$REPO" config user.name t
git -C "$REPO" commit -q --allow-empty -m init

run_bash() {  # $1=command
  local input
  input=$(jq -n --arg cmd "$1" '{tool_name:"Bash", tool_input:{command:$cmd}}')
  printf '%s' "$input" | (cd "$REPO" && bash "$HOOK")
}

FAIL=0
assert_exit() {  # $1=expected $2=actual $3=label
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# ── (A) find -delete: ゾーン判定 ──
run_bash "find $REPO/sub -delete"; assert_exit 0 "$?" "(A) find -delete プロジェクト配下は許可"
run_bash "find /etc -delete"; assert_exit 2 "$?" "(A) find -delete ゾーン外はブロック"
run_bash "find $REPO/sub -name '*.tmp'"; assert_exit 0 "$?" "(A) -delete を含まない find は従来通り無条件許可"

# ── (A) rsync --delete: ゾーン判定 ──
mkdir -p /tmp/bg_test_src /tmp/bg_test_dst
run_bash "rsync -a --delete /tmp/bg_test_src/ /tmp/bg_test_dst/"; assert_exit 0 "$?" "(A) rsync --delete 両方/tmp配下は許可"
run_bash "rsync -a --delete /etc/ /tmp/bg_test_dst/"; assert_exit 2 "$?" "(A) rsync --delete 片方ゾーン外はブロック"
rm -rf /tmp/bg_test_src /tmp/bg_test_dst

# ── (A) chmod 000 / chmod -R 777: ゾーン判定 ──
touch /tmp/bg_test_file
run_bash "chmod 000 /tmp/bg_test_file"; assert_exit 0 "$?" "(A) chmod 000 /tmp配下は許可"
run_bash "chmod 000 /etc/passwd"; assert_exit 2 "$?" "(A) chmod 000 ゾーン外はブロック"
run_bash "chmod -R 777 /tmp/bg_test_file"; assert_exit 0 "$?" "(A) chmod -R 777 /tmp配下は許可"
run_bash "chmod -R 777 /"; assert_exit 2 "$?" "(A) chmod -R 777 / (ルート自体)はブロック"
rm -f /tmp/bg_test_file

# ── (A) 解析不能フォールバック ──
run_bash 'find $HOME -delete'; assert_exit 2 "$?" "(A) find -delete 変数展開は解析不能としてブロック"
run_bash 'cd /tmp && find . -delete'; assert_exit 2 "$?" "(A) find -delete cd混在は解析不能としてブロック"

# ── レビュー指摘の修正確認（正確性レビューで実測された穴）──
run_bash $'find /tmp/bg_ok -delete\nrm -rf /'; assert_exit 2 "$?" "CRITICAL修正: 改行密輸(find -delete\\nrm -rf /)はブロック"
run_bash $'find /tmp/bg_ok -delete\nchmod 000 /etc/passwd'; assert_exit 2 "$?" "CRITICAL修正: 改行密輸(find -delete\\nchmod 000)はブロック"
run_bash 'find /tmp/bg_ok -delete -fprint /etc/passwd'; assert_exit 2 "$?" "HIGH修正: find -fprint によるゾーン外書き込みはブロック"
run_bash 'find /tmp/bg_ok -fls /etc/shadow -delete'; assert_exit 2 "$?" "HIGH修正: find -fls によるゾーン外書き込みはブロック"
mkdir -p /tmp/find /tmp/bg_dst
run_bash "rsync -a --delete /tmp/find/ /tmp/bg_dst/"; assert_exit 0 "$?" "MEDIUM修正: パス名'find'(単語境界一致)を含むrsync --deleteが誤ブロックされない"
rm -rf /tmp/find /tmp/bg_dst
run_bash "chmod 777 -R /etc"; assert_exit 2 "$?" "MEDIUM修正: chmod 777 -R(フラグ後置)もゾーン判定にかかりブロック(ゾーン外)"
run_bash "chmod -R 0777 /etc"; assert_exit 2 "$?" "MEDIUM修正: chmod -R 0777(4桁)もゾーン判定にかかりブロック(ゾーン外)"
touch /tmp/bg_test_file2
run_bash "chmod 777 -R /tmp/bg_test_file2"; assert_exit 0 "$?" "MEDIUM修正: chmod 777 -R /tmp配下は許可"
rm -f /tmp/bg_test_file2

# ── 2周目の正確性レビュー指摘の修正確認 ──
# CRITICAL: クォート分割による難読化で find -delete/rsync --delete/chmod 000 の
# ゾーン判定トリガー自体を回避しようとする攻撃は、正規化後の危険パターン再判定で
# 無条件ブロックにフォールバックする（ゾーン内であっても難読化時点でブロック）。
run_bash 'f"i"nd /etc -de"l"ete'; assert_exit 2 "$?" "CRITICAL修正: クォート分割によるfind -delete難読化バイパスはブロック"
run_bash 'rs"y"nc -a --de"l"ete /etc/ /tmp/bg_test_dst2/'; assert_exit 2 "$?" "CRITICAL修正: クォート分割によるrsync --delete難読化バイパスはブロック"
run_bash 'chmod 0"0"0 /etc/passwd'; assert_exit 2 "$?" "CRITICAL修正: クォート分割によるchmod 000難読化バイパスはブロック"
# MEDIUM: rsyncの--delは--delete-duringの公式エイリアスであり、トリガー正規表現に
# --deleteしか無いと検知漏れになる。
mkdir -p /tmp/bg_del_src /tmp/bg_del_dst
run_bash "rsync -a --del /tmp/bg_del_src/ /tmp/bg_del_dst/"; assert_exit 0 "$?" "MEDIUM修正: rsync --del(エイリアス)も/tmp配下同士は許可"
run_bash "rsync -a --del /etc/ /tmp/bg_del_dst/"; assert_exit 2 "$?" "MEDIUM修正: rsync --del(エイリアス)もゾーン外はブロック"
rm -rf /tmp/bg_del_src /tmp/bg_del_dst
# MEDIUM: 安全文字集合からグロブ文字(*/?)を除去。グロブはhook内ではset -fで
# 展開されないが実行シェルでは展開されるため、静的判定と実行時の対象が
# 乖離しうる。グロブを含む対象は「解析不能」としてゾーン判定を通さない。
run_bash 'find /tmp/bg_glob* -delete'; assert_exit 2 "$?" "MEDIUM修正: findのグロブ対象は解析不能としてブロック"

# ── 既存 BLOCKED_PATTERNS の回帰確認（代表数件）──
run_bash 'shutdown -h now'; assert_exit 2 "$?" "既存: shutdown -h now は引き続きブロック"
run_bash 'dd if=/dev/zero of=/dev/sda'; assert_exit 2 "$?" "既存: dd ディスク上書きは引き続きブロック"
run_bash 'cat ~/.ssh/id_rsa'; assert_exit 2 "$?" "既存: 秘密鍵読取は引き続きブロック"
run_bash 'grep -r "shutdown" .'; assert_exit 0 "$?" "既存: read-only な shutdown 文字列検索は誤検知しない"
run_bash 'shutil.rmtree("/tmp/x")'; assert_exit 2 "$?" "既存: shutil.rmtree は無条件ブロックのまま(スコープ外)"

# バグ修正: 機密ファイル読取パターンの(cat|...|od|...)に\bが無く、"od"が"chmod"等の
# 部分文字列にマッチし、無関係なコマンドを誤ブロックしていた。
run_bash 'chmod 600 /tmp/x/credentials.toml'; assert_exit 0 "$?" "バグ修正: chmod 600 が'od'部分一致で誤ブロックされない"
run_bash 'chmod 644 /tmp/x/.env'; assert_exit 0 "$?" "バグ修正: chmodの.envファイルも'od'部分一致で誤ブロックされない"

# 仕様変更: 機密ファイル読取をゾーン判定方式へ変更（ユーザー承認済み）。
# プロジェクト配下／$CLAUDE_HOME配下／/tmp配下の読取は許可、それ以外は引き続きブロック。
run_bash 'od -c /tmp/x/credentials.toml'; assert_exit 0 "$?" "仕様変更: /tmp配下のod読取はゾーン内として許可"
run_bash 'cat /tmp/x/.env'; assert_exit 0 "$?" "仕様変更: /tmp配下の.env読取はゾーン内として許可"
run_bash 'cat somefile/.env'; assert_exit 0 "$?" "仕様変更: プロジェクト配下(相対パス)の.env読取はゾーン内として許可"
run_bash 'cat /etc/credentials'; assert_exit 2 "$?" "回帰確認: ゾーン外(/etc)の機密ファイル読取は引き続きブロック"
run_bash 'cat /tmp/x/.env | grep KEY'; assert_exit 2 "$?" "回帰確認: パイプを含む複合コマンドは解析不能としてブロック"
run_bash $'cat /tmp/x/.env\ncat /etc/credentials' ; assert_exit 2 "$?" "回帰確認: 改行密輸(1行目ゾーン内/2行目ゾーン外)はブロック"

# ── バグ修正: 単純な git rm --cached 単体が、無関係な箇所のクォート等で
#    「難読化」と誤診断されて誤ったメッセージでブロックされない ──
# git rm --cached <zone内path> 単体（連結なし）はゾーン判定を通り exit 0 になる。
run_bash "git rm --cached target.txt"; assert_exit 0 "$?" "バグ修正: git rm --cached単体(連結なし)はゾーン判定を通り許可される"

# ── 設計確認: git rm --cached を他コマンドと && や改行で連結したものは、
#    ゾーン判定自身の安全文字集合チェック（連結を弾く設計、コメント参照）により
#    引き続きブロックされる。これは意図的な設計であり今回のバグ修正の対象外。
#    連結せず個別のBash呼び出しに分けて実行するのが正しい回避策。
run_bash 'git rm --cached target.txt && git commit -m "message"'; assert_exit 2 "$?" "設計確認: git rm --cachedと他コマンドの連結(&&)は意図的にブロックされたまま(個別呼び出しに分割が正解)"
run_bash $'git rm --cached target.txt\ngit commit -m "$(cat <<\'EOF\'\nmsg\nEOF\n)"'; assert_exit 2 "$?" "設計確認: git rm --cached後続行の別コマンドとの複合も連結として引き続きブロックされたまま"

# ── 回帰確認: 削除語+変数展開が同一行に同居する本来の攻撃パターンは引き続きブロック ──
run_bash 'rm $(echo /etc/passwd)'; assert_exit 2 "$?" "回帰確認: rm自身の対象が変数展開/コマンド置換な場合は引き続き解析不能としてブロック"
run_bash 'rm `echo /etc/passwd`'; assert_exit 2 "$?" "回帰確認: rm自身の対象がバッククォート置換な場合は引き続き解析不能としてブロック"

# ── review-security指摘分の回帰テスト追加(Minor) ──
# 削除語を含む行自体には $/` が無いが、別行で変数展開/コマンド置換が行われる
# パターン。変更2のガード(削除語を含む行のみを見る)は素通りするが、最終
# catch-all(\b(rm|rmdir|unlink)(\s|$))が2行目の"rm"に直接一致するため、
# 別の防御層によって引き続きブロックされることを固定化する。
run_bash $'X=$(whoami)\nrm -rf /etc/passwd'; assert_exit 2 "$?" "review-security指摘: 削除語行と変数展開行が別行でも最終catch-allでブロック"

# 無害な文字列(echoの引数)でchmod\s+.*000パターンを事前一致させ変更1の
# 再判定ブロックを回避しても、chmod専用ゾーン判定はCHMOD_FIRSTがchmodと
# 完全一致しない複合コマンドを無条件不許可とするため、引き続きブロックされる
# ことを固定化する(find/rsync/機密ファイル読取のFIRSTトークン厳格チェックも同型)。
run_bash "echo \"chmod harmless000file\"; ch'mod' 0'0'0 /tmp/x"; assert_exit 2 "$?" "review-security指摘: 無害文字列での事前一致回避もchmodゾーン判定のFIRSTトークン厳格チェックでブロック"

rm -rf "$SCRATCH"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
