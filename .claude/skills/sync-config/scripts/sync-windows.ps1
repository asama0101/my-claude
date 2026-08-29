# sync-windows.ps1 — %USERPROFILE%\.claude\ の設定をリポジトリの windows/claude/ ミラーへ同期する。
#
# 方向: $CLAUDE_HOME  →  <repo>\windows\claude\   （source が真実の源）
# 逆方向（repo → $CLAUDE_HOME）の展開は Claude Code に直接依頼する（linux 版と同じ運用）。
# settings.json のプレースホルダ実体化（下記）を含め、展開手順はリポジトリ直下 CLAUDE.md を参照。
#
# 同期方式:
# - ファイル   : Copy-Item で windows/claude/ 直下へコピー（上書き）
# - ディレクトリ: robocopy /MIR で「完全同期」。source に無いファイルはミラーからも削除される。
# - settings.json のみ: 絶対パス ($CLAUDE_HOME) を git-bash 形式 (/c/Users/...) に変換した上で
#   プレースホルダ __CLAUDE_HOME__ へ逆変換して保存。
#   （Claude Code は settings.json 内で $HOME を展開しないため、repo にはプレースホルダを置く。
#     展開先の絶対パスへの実体化は、別環境セットアップ時に Claude Code へ依頼する。）
#
# commit/push は行わない（同期のみ）。反映後に commit/push が必要なら /pr-create を使う。
#
# パスはスクリプト位置から導出するので、どの環境でも動作する。
# 展開元は CLAUDE_HOME 環境変数で上書き可能（既定 $env:USERPROFILE\.claude）。

$ErrorActionPreference = "Stop"

# --- パス導出 ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir)))
$DestDir = Join-Path $RepoRoot "windows\claude"
$ClaudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $env:USERPROFILE ".claude" }

# --- 同期対象 ---
# 単一ファイル（DestDir 直下へコピー）
$FileTargets = @(
    "CLAUDE.md",
    "settings.json",
    "statusline-command.sh"
)
# ディレクトリ（/MIR で削除も伝播）
$DirTargets = @(
    "hooks",
    "skills",
    "agents",
    "rules",
    "assets",
    "commands"
)

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

Write-Output "同期を開始します ( $ClaudeHome -> $DestDir )..."

# 1) ファイル同期
foreach ($Name in $FileTargets) {
    $Src = Join-Path $ClaudeHome $Name
    if (Test-Path $Src -PathType Leaf) {
        Copy-Item -Path $Src -Destination $DestDir -Force
        Write-Output "Done(file): $Name"
    } else {
        Write-Output "Skip: $Src が見つかりません。"
    }
}

# 1.5) settings.json の逆変換: 絶対パス（git-bash形式） → プレースホルダ
$SettingsMirror = Join-Path $DestDir "settings.json"
if (Test-Path $SettingsMirror -PathType Leaf) {
    # Windows 形式パス (C:\Users\sioay\.claude) → git-bash 形式 (/c/Users/sioay/.claude) へ変換
    # ドライブレターを小文字化し、"\" を "/" に置換して "/" + ドライブレター + 残りパス とする
    $DriveLetter = $ClaudeHome.Substring(0, 1).ToLower()
    $RestPath = $ClaudeHome.Substring(2) -replace '\\', '/'
    $ClaudeHomeGitBash = "/$DriveLetter$RestPath"

    # -Encoding utf8 を明示しないと既定のシステムANSIコードページで読み込まれ、
    # 多バイト文字（em dash等）が文字化けする。書き込みは Set-Content -Encoding utf8 だと
    # Windows PowerShell 5.1 で常にBOM付きUTF-8になるため、.NET APIでBOMなしUTF-8を明示する。
    $Content = Get-Content -Path $SettingsMirror -Raw -Encoding utf8
    $Content = $Content.Replace($ClaudeHomeGitBash, "__CLAUDE_HOME__")
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($SettingsMirror, $Content, $Utf8NoBom)
    Write-Output "Done(subst): settings.json のパスを __CLAUDE_HOME__ に置換しました。"
}

# 2) ディレクトリ同期（削除も伝播、robocopy /MIR を使用）
foreach ($Name in $DirTargets) {
    $Src = Join-Path $ClaudeHome $Name
    $Dst = Join-Path $DestDir $Name
    if (Test-Path $Src -PathType Container) {
        robocopy $Src $Dst /MIR /NFL /NDL /NJH /NJS | Out-Null
        # robocopy の終了コードは 0〜7 が成功。8以上のみエラー扱い。
        if ($LASTEXITCODE -ge 8) {
            Write-Error "robocopy が失敗しました ($Name): 終了コード $LASTEXITCODE"
            exit 1
        }
        Write-Output "Done(dir):  $Name"
    } else {
        Write-Output "Skip: $Src が見つかりません。"
    }
}

Write-Output "すべての同期が完了しました。"
exit 0
