# user\ の内容を ~\.claude\ に反映する（user\ -> ~\.claude\ の一方向）
# 対象は Windows のみ（パス区切りに \ を前提にしている）
# 使い方: pwsh .\sync.ps1 [-Force]
#   既定: 反映先が反映元より新しいファイルはスキップして警告する（~\.claude 側で変更された可能性）
#   -Force: 上記のファイルも上書きする
#
# プレースホルダ（user\ 内のテキストファイルで使える。反映時に実行環境の値へ置換する）
#   {{HOME}}      C:/Users/<ユーザ名>     （スラッシュ区切り）
#   {{HOME_JSON}} C:\\Users\\<ユーザ名>   （JSON 文字列内のバックスラッシュ区切り）

param([switch]$Force)

$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'user'
$dst = Join-Path $env:USERPROFILE '.claude'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$home_ = $env:USERPROFILE.Replace('\', '/')
$homeJson = $env:USERPROFILE.Replace('\', '\\')

# 反映後の内容をバイト列で返す。プレースホルダを含まなければ元のバイト列のまま返す。
function Get-RenderedBytes([string]$path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $text = $utf8.GetString($bytes)
    if ($text -notmatch '\{\{HOME(_JSON)?\}\}') { return , $bytes }
    $text = $text.Replace('{{HOME_JSON}}', $homeJson).Replace('{{HOME}}', $home_)
    return , $utf8.GetBytes($text)
}

function Get-BytesHash([byte[]]$bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    return [BitConverter]::ToString($sha.ComputeHash($bytes))
}

Get-ChildItem -Path $src -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length).TrimStart('\')
    $target = Join-Path $dst $rel
    $bytes = Get-RenderedBytes $_.FullName

    if (Test-Path $target) {
        $targetBytes = [System.IO.File]::ReadAllBytes($target)
        if ((Get-BytesHash $bytes) -eq (Get-BytesHash $targetBytes)) {
            Write-Host "同一: $rel"
            return
        }
        if (-not $Force -and (Get-Item $target).LastWriteTime -gt $_.LastWriteTime) {
            Write-Warning "スキップ（反映先のほうが新しい）: $rel  差分を確認し、必要なら user\ に取り込むか -Force で上書き"
            return
        }
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    [System.IO.File]::WriteAllBytes($target, $bytes)
    Write-Host "反映: $rel"
}
