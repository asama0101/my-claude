#!/bin/bash
set -uo pipefail
# settings.jsonが宣言する各hookコマンドが、実際にsettings.json記載通りの
# 起動方法(裸のコマンドパスとして、シェル経由で実行)で動作するかを検証する。
# 個々のフックのロジック検証は各hookの*.test.shが担当。このテストは
# 「実行権限・シェバン・パス解決」という、ロジックテストが構造的にカバー
# できない層のみを対象とする(bash "$HOOK"での直接起動はexec bitを経由
# しないため、この種の欠陥を検知できない。2026-08-29最終レビューで
# branch-guard.shの実行権限欠落を見逃した直接の原因への対応)。
#
# 既知の限界(Windows/NTFS): Git BashのchmodはNTFS上で実行ビット(x)を実効的に
# 制御しないため、`[ -x ]`は常に真を返す(実機検証で確認済み。chmod -xしても
# `ls -l`のパーミッション表示・`[ -x ]`結果が変化しない)。そのため本テストの
# 「実行権限が無い」分岐はWindows実機では実質的に到達不能であり、このチェックは
# 主にファイル存在確認・シェバン・パス解決の検証としてのみ機能する。
#
# 既知の限界(Windows/jq): この環境のjq.exeはstdoutをテキストモードで開くため、
# 出力の各行末に(最終行を除き)CRが付与される。`read -r`はCRを行末とみなさず
# 値の一部として取り込んでしまうため、末尾CRを明示的に除去しないと
# 「ファイルが存在しない」という偽陽性FAILになる(実機検証で確認済み)。
SETTINGS="$HOME/.claude/settings.json"

FAIL=0
CMDS=$(jq -r '.hooks.PreToolUse[].hooks[].command' "$SETTINGS")
while IFS= read -r hook; do
  hook="${hook%$'\r'}"
  [ -z "$hook" ] && continue
  if [ ! -f "$hook" ]; then
    echo "FAIL: $hook が存在しない"
    FAIL=1
    continue
  fi
  if [ ! -x "$hook" ]; then
    echo "FAIL: $hook に実行権限が無い(settings.jsonは裸のコマンドパスとして呼ぶため実行権限が必須)"
    FAIL=1
    continue
  fi
  OUT=$(printf '{"tool_name":"Bash","tool_input":{"command":"true"}}' | sh -c "$hook" 2>&1)
  CODE=$?
  case "$CODE" in
    0 | 2) echo "PASS: $hook は実行可能でexit $CODE を返す" ;;
    *) echo "FAIL: $hook がsettings.json記載の起動方法で異常終了(exit $CODE): $OUT"; FAIL=1 ;;
  esac
done <<< "$CMDS"

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
