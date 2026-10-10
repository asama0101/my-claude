# user\ の内容を ~\.claude\ に反映する（user\ -> ~\.claude\ の一方向）
# 対象は Windows のみ（パス区切りに \ を前提にしている）
# 使い方: pwsh .\sync.ps1 [-Force]
#   既定: 反映先が反映元より新しいファイルはスキップして警告する（~\.claude 側で変更された可能性）
#   -Force: 上記のファイルも上書きする（MCP も、内容が違う同名サーバーを上書きする）
#
# プレースホルダ（user\ 内のテキストファイルで使える。反映時に実行環境の値へ置換する）
#   {{HOME}}      C:/Users/<ユーザ名>     （スラッシュ区切り）
#   {{HOME_JSON}} C:\\Users\\<ユーザ名>   （JSON 文字列内のバックスラッシュ区切り）

param([switch]$Force)

$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'user'
$dst = Join-Path $env:USERPROFILE '.claude'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$mcpDef = Join-Path $src 'mcp-servers.json'

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

Get-ChildItem -Path $src -Recurse -File | Where-Object { $_.FullName -ne $mcpDef } | ForEach-Object {
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

# MCP サーバーの登録（usermcp-servers.json -> ~.claude.json の user スコープ）
# 定義にないサーバーは触らない。env / headers にトークンを含むサーバーは定義に書かない。
if (Test-Path $mcpDef) {
    $defText = $utf8.GetString((Get-RenderedBytes $mcpDef))
    $defs = ($defText | ConvertFrom-Json).mcpServers
    $claudeJson = Join-Path $env:USERPROFILE '.claude.json'
    # ~.claude.json 全体は大文字小文字だけが違うキーを含み得て PowerShell 5.1 で読めないため、node で mcpServers だけ取り出す
    $current = $null
    if (Test-Path $claudeJson) {
        $currentJson = & node -e 'const c=JSON.parse(require(''fs'').readFileSync(process.argv[1],''utf8'')); console.log(JSON.stringify(c.mcpServers||{}))' $claudeJson
        if ($LASTEXITCODE -ne 0) { throw '~.claude.json の読み取りに失敗' }
        $current = $currentJson | ConvertFrom-Json
    }

    foreach ($def in $defs.PSObject.Properties) {
        $name = $def.Name
        $json = $def.Value | ConvertTo-Json -Compress -Depth 10
        $existing = if ($current) { $current.PSObject.Properties[$name] } else { $null }

        if ($existing) {
            if (($existing.Value | ConvertTo-Json -Compress -Depth 10) -eq $json) {
                Write-Host "同一: MCP $name"
                continue
            }
            if (-not $Force) {
                Write-Warning "スキップ（同名の MCP の内容が定義と違う）: $name  差分を確認し、必要なら定義に取り込むか -Force で上書き"
                continue
            }
            & claude mcp remove --scope user $name | Out-Null
        }

        # Windows PowerShell 5.1 はネイティブコマンドに渡す引数の " を落とすため、\" にして渡す
        & claude mcp add-json --scope user $name ($json.Replace('"', '\"')) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "MCP の登録に失敗: $name" }
        Write-Host "反映: MCP $name"
    }
}
