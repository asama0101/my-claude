#!/bin/bash
set -euo pipefail

# sync.sh — ~/.claude/ の設定をリポジトリの claude/ ミラーへ同期し、commit + push する。
#
# 方向: ~/.claude/  →  <repo>/claude/   （source が真実の源）
# 逆方向（repo → ~/.claude）の展開は scripts/install.sh を使う。
#
# 同期方式:
# - ファイル : rsync -a で claude/ 直下へコピー（上書き）
# - ディレクトリ: rsync -a --delete で「完全同期」。source に無いファイルはミラーからも削除される。
# - settings.json のみ: 絶対パス ($CLAUDE_HOME) → プレースホルダ __CLAUDE_HOME__ へ逆変換して保存。
#   （Claude Code は settings.json 内で $HOME を展開しないため、repo にはプレースホルダを置き、
#     install.sh が展開先の絶対パスへ実体化する。install.sh の順変換と対になる。）
#
# パスはスクリプト位置から導出するので、どのユーザー環境でも動作する。
# 展開元は CLAUDE_HOME 環境変数で上書き可能（既定 $HOME/.claude）。

# --- パス導出 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DEST_DIR="$REPO_ROOT/claude"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"

# --- 同期対象 ---
# 単一ファイル（DEST_DIR 直下へコピー）
FILE_TARGETS=(
    "$CLAUDE_HOME/CLAUDE.md"
    "$CLAUDE_HOME/settings.json"
    "$CLAUDE_HOME/statusline-command.sh"
)
# ディレクトリ（--delete で削除も伝播）
DIR_TARGETS=(
    "$CLAUDE_HOME/hooks"
    "$CLAUDE_HOME/skills"
    "$CLAUDE_HOME/agents"
    "$CLAUDE_HOME/rules"
)

command -v rsync >/dev/null 2>&1 || { echo "rsync が見つかりません。インストールしてください。"; exit 1; }

mkdir -p "$DEST_DIR"

echo "同期を開始します ( $CLAUDE_HOME → $DEST_DIR )..."

# 1) ファイル同期
for ITEM in "${FILE_TARGETS[@]}"; do
    if [ -e "$ITEM" ]; then
        rsync -a "$ITEM" "$DEST_DIR/"
        echo "Done(file): $(basename "$ITEM")"
    else
        echo "Skip: $ITEM が見つかりません。"
    fi
done

# 1.5) settings.json の逆変換: 絶対パス → プレースホルダ
SETTINGS_MIRROR="$DEST_DIR/settings.json"
if [ -f "$SETTINGS_MIRROR" ]; then
    sed -i "s|${CLAUDE_HOME}|__CLAUDE_HOME__|g" "$SETTINGS_MIRROR"
    echo "Done(subst): settings.json のパスを __CLAUDE_HOME__ に置換しました。"
fi

# 2) ディレクトリ同期（削除も伝播）
for ITEM in "${DIR_TARGETS[@]}"; do
    if [ -d "$ITEM" ]; then
        NAME=$(basename "$ITEM")
        mkdir -p "$DEST_DIR/$NAME"
        # 末尾スラッシュ必須: 「中身」を「専用サブディレクトリの中身」へ同期する
        rsync -a --delete "$ITEM/" "$DEST_DIR/$NAME/"
        echo "Done(dir):  $NAME"
    else
        echo "Skip: $ITEM が見つかりません。"
    fi
done

echo "すべての同期が完了しました。"
echo ""
echo "Git へ push します..."

cd "$REPO_ROOT" || { echo "リポジトリへの移動に失敗しました。"; exit 1; }

if [ -z "$(git status --porcelain)" ]; then
    echo "変更なし — push をスキップします。"
    exit 0
fi

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
git add -A
git commit -m "chore(setup): sync Claude config files ($TIMESTAMP)"
git push

echo "push 完了。"
