---
name: anzen
description: |
  ネットワーク機器の作業手順書(Excel)を多観点でレビュー、またはパラメータシート(Excel)を自動入力する。
  「手順書をレビューして」「作業手順書チェック」「パラメータシート入力」「コンフィグ手順を確認」
  「/anzen」「ネットワークの手順書を見て」「xlsx の作業手順を安全確認」などの発言で起動する。
  対象は Cisco IOS/NX-OS・Juniper JunOS など。入出力は .xlsx。レビュー結果は HTML レポート。
---

# /anzen — ネットワーク作業の安全確認スキル

SE が使うネットワーク機器の **作業手順書レビュー** と **パラメータシート自動入力** を行う。
入口は1つ。引数の .xlsx と文脈から `review` / `fill` を自動判定し、対話で確定する。

## 使い方

```
/anzen <file.xlsx>                                  # 自動判定 → 対話で確定
/anzen <手順書.xlsx>                                # レビュー
/anzen <パラメータシート.xlsx> --source <設計書.xlsx> --config <show.txt>  # 自動入力
```

## スクリプト・エージェントの場所

- スクリプト: `.claude/skills/anzen/scripts/`（`excel_reader.py` / `excel_writer.py` / `show_parser.py` / `report_html.py`）
- 実行 Python: `~/notebook/OpsReviewer/.venv/bin/python`（openpyxl 導入済み）
- レビュアー: `ops-reviewer-syntax` / `ops-reviewer-consistency` / `ops-reviewer-procedure` / `ops-reviewer-excel`
- 自動入力: `ops-param-filler`

> 実行例ではコマンドが長くなるため、`PY=~/notebook/OpsReviewer/.venv/bin/python` を使うと読みやすい。

## Step 0: モード判定

1. 引数の .xlsx を `excel_reader.py` で JSON 化する:
   ```bash
   ~/notebook/OpsReviewer/.venv/bin/python .claude/skills/anzen/scripts/excel_reader.py <file.xlsx> > /tmp/anzen_target.json
   ```
2. 内容とユーザーの言葉からモードを推定する:
   - コマンド列・手順ステップが主 → **review**
   - 空欄のパラメータ項目が主、`--source`/`--config` がある → **fill**
3. `AskUserQuestion` で「レビュー / 自動入力」のどちらかを確定する（推定をデフォルト候補に）。

---

## Mode A: review（手順書レビュー）

### Step A1: 4 レビュアーを同一ターン内で並列起動

`Agent` ツールで **同時に 4 つ** のサブエージェントを呼ぶ（順次ではなく並列）。
各プロンプトに「`/tmp/anzen_target.json` のパス（または JSON 内容）」と「判明していれば対象ベンダー」を含める。

```
同一ターンで Agent を 4 回同時呼び出し:
  subagent_type: ops-reviewer-syntax       → "次の手順書JSONをレビュー: /tmp/anzen_target.json （ベンダー: ...）"
  subagent_type: ops-reviewer-consistency  → 同上
  subagent_type: ops-reviewer-procedure    → 同上
  subagent_type: ops-reviewer-excel        → 同上
```

各エージェントは末尾に `{"name", "verdict", "findings": [{"severity", "summary", "location", "detail", "fix"}]}` の JSON を返す。

### Step A2: 統合 findings JSON を組み立てる

4 つの JSON を集めて findings ファイルを作る:

```json
{
  "target": "<元ファイル名>",
  "generated_at": "<YYYY-MM-DDTHH:MM>",
  "reviewers": [ <syntax の JSON>, <consistency の JSON>, <procedure の JSON>, <excel の JSON> ]
}
```

これを `/tmp/anzen_findings.json` に Write する。

### Step A3: HTML レポート生成

```bash
~/notebook/OpsReviewer/.venv/bin/python .claude/skills/anzen/scripts/report_html.py \
  --input /tmp/anzen_findings.json \
  --output <元ファイルと同じディレクトリ>/review_<YYYYMMDD_HHMM>.html
```

### Step A4: 結果サマリーを提示

- 生成した HTML レポートのパスを伝える。
- overall verdict（approved / warning / blocked）と、CRITICAL・HIGH 件数を要約する。
- CRITICAL / HIGH の指摘を重大度降順で箇条書きする（MEDIUM 以下はユーザー希望時のみ）。

---

## Mode B: fill（パラメータシート自動入力）

### Step B1: 入力源を収集

- 対象シート: `/tmp/anzen_target.json`（Step 0 で生成済み）
- `--source <設計書.xlsx>` があれば `excel_reader.py` で JSON 化
- `--config <show.txt>` があれば `show_parser.py` で JSON 化:
  ```bash
  ~/notebook/OpsReviewer/.venv/bin/python .claude/skills/anzen/scripts/show_parser.py --config <show.txt> > /tmp/anzen_show.json
  ```
- 自然言語の要件はユーザー発言から拾う。

### Step B2: ops-param-filler を起動

`Agent` で `ops-param-filler` を呼び、上記の入力源パスと自然言語要件、対象 .xlsx の絶対パスを渡す。
エージェントがマッピングを作り `excel_writer.py` で `<対象>_filled_<日時>.xlsx` を生成する（元ファイル非破壊）。

### Step B3: 結果サマリーを提示

- 生成した記入済みファイルのパス。
- 記入件数 / 未記入件数 / 競合（要確認）を提示し、未記入・競合はユーザーに確認を促す。

---

## 注意

- 元の .xlsx は常に非破壊。レビューは HTML 出力、入力は別名 .xlsx 出力。
- ベンダー判定が曖昧なときは `AskUserQuestion` で確認する。
- スクリプトは必ず venv の Python（`~/notebook/OpsReviewer/.venv/bin/python`）で実行する。
