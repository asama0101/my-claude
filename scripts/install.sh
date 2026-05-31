#!/bin/bash
set -euo pipefail

# install.sh — リポジトリの claude/ ミラーを ~/.claude/ へ展開（デプロイ）する。
#
# 方向: <repo>/claude/  →  ~/.claude/   （別環境での再現セットアップ用）
# 逆方向（~/.claude → repo）の同期は scripts/sync.sh を使う。
#
# 設計:
# - ホワイトリスト方式: claude/ にある特定の項目だけを展開する。
#   ~/.claude/ の projects・sessions・logs・daemon・plugins・settings.local.json などの
#   環境固有資産には一切触れない。
# - ディレクトリは rsync -a（--delete なし）。ユーザーが追加した hook/skill/agent を消さない。
#   （sync.sh は --delete あり = source が真実、install.sh は --delete なし = 足し込み、の非対称）
# - settings.json は repo 上ではプレースホルダ __CLAUDE_HOME__ を含む。展開時に DEST の絶対パスへ
#   実体化する（sync.sh の逆変換と対になる）。
# - 上書き対象は rsync --backup でタイムスタンプ付きバックアップへ退避。内容が同一なら rsync は
#   no-op となりバックアップも作られない（冪等）。
#
# 使い方:
#   bash scripts/install.sh [--dry-run] [--force] [--yes]
#   CLAUDE_HOME=/path/to/dest bash scripts/install.sh   # 展開先を変更（既定 $HOME/.claude）

# --- パス導出 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SRC="$REPO_ROOT/claude"
DEST="${CLAUDE_HOME:-$HOME/.claude}"

# --- 展開対象（ホワイトリスト）---
FILE_ITEMS=( "CLAUDE.md" "statusline-command.sh" )   # settings.json は別処理（プレースホルダ実体化）
DIR_ITEMS=( "hooks" "skills" "agents" )

# --- オプション ---
DRY_RUN=0
FORCE=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --force)   FORCE=1 ;;
        --yes|-y)  ASSUME_YES=1 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "不明な引数: $arg" >&2; exit 2 ;;
    esac
done

command -v rsync >/dev/null 2>&1 || { echo "rsync が見つかりません。インストールしてください。"; exit 1; }
[ -d "$SRC" ] || { echo "展開元が見つかりません: $SRC"; exit 1; }

echo "展開: $SRC  →  $DEST"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_DIR="$DEST/backups/install-$TIMESTAMP"

# settings.json を DEST 向けに実体化したものを一時ファイルへ生成
TMP_SETTINGS="$(mktemp)"
trap 'rm -f "$TMP_SETTINGS"' EXIT
if [ -f "$SRC/settings.json" ]; then
    sed "s|__CLAUDE_HOME__|$DEST|g" "$SRC/settings.json" > "$TMP_SETTINGS"
fi

# --- dry-run: 差分プレビューのみ ---
if [ "$DRY_RUN" -eq 1 ]; then
    echo "(dry-run: 変更は行いません)"
    [ -f "$SRC/settings.json" ] && rsync -acni "$TMP_SETTINGS" "$DEST/settings.json" 2>/dev/null | sed 's/^/  settings.json: /' || true
    for p in "${FILE_ITEMS[@]}"; do
        [ -e "$SRC/$p" ] && rsync -acni "$SRC/$p" "$DEST/" 2>/dev/null | sed "s|^|  $p: |" || true
    done
    for p in "${DIR_ITEMS[@]}"; do
        [ -d "$SRC/$p" ] && rsync -acni "$SRC/$p/" "$DEST/$p/" 2>/dev/null | sed "s|^|  $p/|" || true
    done
    echo "--- settings.json は __CLAUDE_HOME__ → $DEST に実体化されます ---"
    exit 0
fi

# --- 上書き確認（TTY かつ --force/--yes でない場合）---
if [ "$FORCE" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ] && [ -d "$DEST" ] && [ -t 0 ]; then
    echo "既存の $DEST に対象項目を上書きします（差分があれば $BACKUP_DIR へ退避）。続行しますか? [y/N]"
    read -r ans
    case "$ans" in y|Y|yes) ;; *) echo "中止しました。"; exit 0 ;; esac
fi

mkdir -p "$DEST"

BACKUP_OPT=()
[ "$FORCE" -eq 0 ] && BACKUP_OPT=( --backup --backup-dir="$BACKUP_DIR" )

# 内容ベース比較（-c）で冪等性を担保。settings.json は毎回再生成され mtime が変わるため必須。
# --- settings.json 展開（実体化済み一時ファイルから）---
if [ -f "$SRC/settings.json" ]; then
    rsync -ac "${BACKUP_OPT[@]}" "$TMP_SETTINGS" "$DEST/settings.json"
    echo "Done(file): settings.json (__CLAUDE_HOME__ → $DEST)"
fi

# --- その他ファイル展開 ---
for p in "${FILE_ITEMS[@]}"; do
    [ -e "$SRC/$p" ] || { echo "Skip(file): $p が repo に存在しません。"; continue; }
    rsync -ac "${BACKUP_OPT[@]}" "$SRC/$p" "$DEST/$p"
    echo "Done(file): $p"
done

# --- ディレクトリ展開（--delete なし）---
for p in "${DIR_ITEMS[@]}"; do
    [ -d "$SRC/$p" ] || { echo "Skip(dir): $p が repo に存在しません。"; continue; }
    mkdir -p "$DEST/$p"
    rsync -ac "${BACKUP_OPT[@]}" "$SRC/$p/" "$DEST/$p/"
    echo "Done(dir):  $p"
done

# --- バックアップが空（=変更なし）なら掃除 ---
if [ -d "$BACKUP_DIR" ] && [ -z "$(find "$BACKUP_DIR" -type f 2>/dev/null)" ]; then
    find "$BACKUP_DIR" -type d -empty -delete 2>/dev/null || true
    echo "変更なし（既に最新）。"
elif [ -d "$BACKUP_DIR" ]; then
    echo "既存ファイルを退避: $BACKUP_DIR"
fi

echo ""
echo "展開が完了しました。Claude Code を再起動すると新しい設定が読み込まれます。"
echo "（projects/ sessions/ logs/ settings.local.json などの環境固有資産は変更していません）"
