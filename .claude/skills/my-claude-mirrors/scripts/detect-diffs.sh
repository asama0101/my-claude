#!/bin/bash
set -euo pipefail

# detect-diffs.sh — linux/claude/ と windows/claude/ を再帰比較し、
# 台帳(ledger.json)と照合した結果をJSONで標準出力に返す。
#
# 実機(~/.claude/ 等)には一切触れない。このリポジトリ内の2ミラーの比較専用。
#
# 出力: {"new_diffs":[...], "known_diffs":[...],
#         "only_in_linux":[...], "only_in_windows":[...],
#         "known_only_in_linux":[...], "known_only_in_windows":[...]}
# - new_diffs           : 内容が違い、台帳に未記録（またはハッシュが変化した）ファイル
# - known_diffs         : 内容が違うが、台帳に同じハッシュペアで記録済み（許容差分）
# - only_in_*           : 片方のミラーにしか存在しない、台帳に未記録のファイル／空ディレクトリ
# - known_only_in_*     : 片方のミラーにしか存在しないが、台帳に記録済み（許容差分）
#
# 改行コード(CRLF/LF)は比較前に正規化する。Windows側で編集されたファイルが
# CRLF化されただけの内容同一ファイルを「差分あり」として誤検知しないため。
#
# 実装はnode(lib/detect-diffs.js)。Claude Code自体の実行基盤であるnodeのみに依存し、
# jqには依存しない(jqがPATH上から消失する事故が実際に発生したため。#37参照)。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
LINUX_DIR="$REPO_ROOT/linux/claude"
WINDOWS_DIR="$REPO_ROOT/windows/claude"
LEDGER="$SKILL_DIR/ledger.json"

command -v node >/dev/null 2>&1 || { echo "node が見つかりません。" >&2; exit 1; }
[ -d "$LINUX_DIR" ] || { echo "$LINUX_DIR が見つかりません。" >&2; exit 1; }
[ -d "$WINDOWS_DIR" ] || { echo "$WINDOWS_DIR が見つかりません。" >&2; exit 1; }
[ -f "$LEDGER" ] || echo "[]" > "$LEDGER"

node "$SCRIPT_DIR/lib/detect-diffs.js" "$LINUX_DIR" "$WINDOWS_DIR" "$LEDGER"
