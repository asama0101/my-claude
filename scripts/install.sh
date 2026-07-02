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
# - ディレクトリは足し込み（--delete 相当はしない）。ユーザーが追加した hook/skill/agent を消さない。
#   （sync.sh は --delete あり = source が真実、install.sh は足し込み、の非対称）
# - settings.json は repo 上ではプレースホルダ __CLAUDE_HOME__ を含む。展開時に DEST の絶対パスへ
#   実体化する（sync.sh の逆変換と対になる）。
# - 同期は rsync ではなく cp/cmp/find のみで実装（rsync 未導入の環境でも動く）。
# - 上書き対象はタイムスタンプ付きバックアップ（$DEST/backups/install-*）へ退避。内容が同一なら
#   cmp -s が一致を検出して no-op となり、バックアップも作られない（冪等）。
#
# 使い方:
#   bash scripts/install.sh [--dry-run] [--force] [--yes]
#   CLAUDE_HOME=/path/to/dest bash scripts/install.sh   # 展開先を変更（既定 $HOME/.claude）

# --- パス導出 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SRC="$REPO_ROOT/claude"
DEST="${CLAUDE_HOME:-$HOME/.claude}"
DEST="${DEST%/}"   # 末尾スラッシュを正規化（パス算出・出力で // を出さない）

# --- 展開対象（ホワイトリスト）---
FILE_ITEMS=( "CLAUDE.md" "statusline-command.sh" )   # settings.json は別処理（プレースホルダ実体化）
DIR_ITEMS=( "hooks" "skills" "agents" "rules" )   # rules は sync.sh の DIR_TARGETS と対称（将来の内容追加でも展開漏れしないように）

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

[ -d "$SRC" ] || { echo "展開元が見つかりません: $SRC"; exit 1; }

# --- 同期ヘルパー（rsync 非依存・cp/cmp/find のみ）---
# 内容が異なる時だけ上書きし、上書き前に既存を BACKUP_DIR へ退避（旧 rsync -ac --backup 相当）。
# 内容同一なら no-op（冪等・バックアップも作らない）。BACKUP_DIR/FORCE/DEST は呼び出し時に解決される。
deploy_file() {  # $1=src  $2=dest
    local src=$1 dest=$2 rel
    if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
        return
    fi
    if [ -e "$dest" ] && [ "$FORCE" -eq 0 ]; then
        rel="${dest#"$DEST"/}"
        mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
        cp -p "$dest" "$BACKUP_DIR/$rel"
    fi
    mkdir -p "$(dirname "$dest")"
    cp -p "$src" "$dest"
}
# ディレクトリを再帰展開（--delete なし＝足し込み）。各ファイルを deploy_file に流す。
# プロセス置換でループを現シェルで動かす（パイプのサブシェルを避け set -e を確実に伝播）。
deploy_dir() {  # $1=src_dir  $2=dest_dir
    local f rel
    while IFS= read -r f; do
        rel="${f#"$1"/}"
        deploy_file "$f" "$2/$rel"
    done < <(find "$1" -type f -print)
}
# 変更は一切行わず、差分があれば標準出力へ1行出すだけ（副作用なし・dry-run 用）。
preview() {  # $1=src  $2=dest  $3=label
    if   [ ! -e "$2" ];      then echo "  $3: 新規作成"
    elif ! cmp -s "$1" "$2"; then echo "  $3: 更新（差分あり）"
    fi
}

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
    if [ -f "$SRC/settings.json" ]; then
        preview "$TMP_SETTINGS" "$DEST/settings.json" "settings.json"
    fi
    for p in "${FILE_ITEMS[@]}"; do
        if [ -e "$SRC/$p" ]; then preview "$SRC/$p" "$DEST/$p" "$p"; fi
    done
    for p in "${DIR_ITEMS[@]}"; do
        [ -d "$SRC/$p" ] || continue
        while IFS= read -r f; do
            rel="${f#"$SRC"/}"
            preview "$f" "$DEST/$rel" "$rel"
        done < <(find "$SRC/$p" -type f -print)
    done
    echo "--- settings.json は __CLAUDE_HOME__ → $DEST に実体化されます ---"
    exit 0
fi

# --- 展開先確認（TTY かつ --force/--yes でない場合）---
# DEST の存在有無にかかわらず展開先パスを明示確認する（CLAUDE_HOME 指定ミスによる誤展開を防ぐ）。
if [ "$FORCE" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
    if [ -d "$DEST" ]; then
        echo "既存の $DEST に展開します（差分があれば $BACKUP_DIR へ退避）。続行しますか? [y/N]"
    else
        echo "新規ディレクトリ $DEST を作成して展開します。続行しますか? [y/N]"
    fi
    read -r ans
    case "$ans" in y|Y|yes) ;; *) echo "中止しました。"; exit 0 ;; esac
fi

mkdir -p "$DEST"

# 内容ベース比較（cmp -s）で冪等性を担保。settings.json は毎回再生成され mtime が変わるため必須。
# --- settings.json 展開（実体化済み一時ファイルから）---
if [ -f "$SRC/settings.json" ]; then
    deploy_file "$TMP_SETTINGS" "$DEST/settings.json"
    echo "Done(file): settings.json (__CLAUDE_HOME__ → $DEST)"
fi

# --- その他ファイル展開 ---
for p in "${FILE_ITEMS[@]}"; do
    [ -e "$SRC/$p" ] || { echo "Skip(file): $p が repo に存在しません。"; continue; }
    deploy_file "$SRC/$p" "$DEST/$p"
    echo "Done(file): $p"
done

# --- ディレクトリ展開（--delete なし）---
for p in "${DIR_ITEMS[@]}"; do
    [ -d "$SRC/$p" ] || { echo "Skip(dir): $p が repo に存在しません。"; continue; }
    deploy_dir "$SRC/$p" "$DEST/$p"
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
