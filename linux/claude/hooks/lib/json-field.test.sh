#!/bin/bash
set -uo pipefail
LIB="$(dirname "${BASH_SOURCE[0]}")/json-field.sh"
source "$LIB"

FAIL=0
assert_eq() {  # $1=expected $2=actual $3=label
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected [$1], got [$2])"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

JSON='{"a":{"b":"str"},"n":{"x":42},"zero":{"y":0},"cwd":"/fallback"}'

# ── 文字列フィールドを取得できる ──
RESULT=$(json_fields "$JSON" "a.b")
assert_eq "str" "$RESULT" "文字列フィールドを取得できる"

# ── 数値フィールドは文字列化されて返る(jq互換の要件) ──
RESULT=$(json_fields "$JSON" "n.x")
assert_eq "42" "$RESULT" "数値フィールドが文字列化されて返る"

# ── 数値0は空文字にならない(falsyだが有効値) ──
RESULT=$(json_fields "$JSON" "zero.y")
assert_eq "0" "$RESULT" "数値0が空文字に潰れない"

# ── 存在しないパスはフォールバックへ進む ──
RESULT=$(json_fields "$JSON" "missing.path,cwd")
assert_eq "/fallback" "$RESULT" "フォールバックchainで次候補を採用する"

# ── どのフォールバックも解決しなければ空文字 ──
RESULT=$(json_fields "$JSON" "missing.path")
assert_eq "" "$RESULT" "解決不能なパスは空文字を返す"

# ── 複数フィールドを1回の呼び出しで改行区切り取得できる(statuslineの多フィールド抽出用途) ──
mapfile -t FIELDS < <(json_fields "$JSON" "a.b" "n.x" "missing.path,cwd")
assert_eq "str" "${FIELDS[0]:-}" "複数フィールド一括取得: 1つ目"
assert_eq "42" "${FIELDS[1]:-}" "複数フィールド一括取得: 2つ目"
assert_eq "/fallback" "${FIELDS[2]:-}" "複数フィールド一括取得: 3つ目(フォールバック)"

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
