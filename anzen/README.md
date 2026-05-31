# anzen — ネットワーク作業手順書レビュー／パラメータシート自動入力バンドル

ネットワーク機器（Cisco IOS/NX-OS・Juniper JunOS など）の **作業手順書(Excel)を多観点でレビュー** し、
また **パラメータシート(Excel)を自動入力** する Claude Code スキル `anzen` と、その関連エージェント・ルールを
ひとまとめにした **プロジェクト用バンドル**。

## なぜここにあるか（グローバル同期対象外）

`anzen` は全プロジェクトで常時必要なものではなく **特定のネットワーク作業プロジェクトでのみ使う「プロジェクト用スキル」** である。
そのため `~/.claude/`（グローバル設定）には置かず、この repo 直下の専用ディレクトリ `anzen/` に独立資産として版管理する。

このディレクトリは `scripts/sync.sh` / `scripts/install.sh` の同期ホワイトリスト（`hooks` / `skills` / `agents` / `rules`）の**対象外**であり、
グローバル設定の同期・展開からは完全に分離されている。

## 構成

```
anzen/
├── README.md
├── skills/
│   └── anzen/
│       ├── SKILL.md                # /anzen スキル本体（review / fill の入口）
│       └── scripts/
│           ├── excel_reader.py     # .xlsx → JSON
│           ├── excel_writer.py     # マッピング JSON → 記入済み .xlsx（別名保存）
│           ├── show_parser.py      # show コマンド出力 → JSON
│           ├── report_html.py      # findings JSON → HTML レビューレポート
│           └── requirements.txt    # 依存（openpyxl 等）
└── agents/
    ├── ops-param-filler.md         # fill: パラメータ自動入力
    ├── ops-reviewer-syntax.md      # review: コマンド構文・危険コマンド
    ├── ops-reviewer-consistency.md # review: IP/VLAN/マスク等の整合性
    ├── ops-reviewer-procedure.md   # review: 手順順序・ロールバック・影響
    ├── ops-reviewer-excel.md       # review: シート品質（数式エラー・誤字・空欄）
    └── prompts/
        ├── rules_cisco.md          # Cisco 系レビュールール
        └── rules_juniper.md        # Juniper 系レビュールール
```

## 対象プロジェクトへの導入

利用するプロジェクトの `.claude/` 配下へコピーする。パス参照は `.claude/skills/anzen/...`・`.claude/agents/prompts/...` の
**プロジェクト相対**で記述済みなので、プロジェクトルートを CWD として実行する想定。

```bash
PROJ=/path/to/your/network-project
mkdir -p "$PROJ/.claude/skills" "$PROJ/.claude/agents"
cp -r anzen/skills/anzen "$PROJ/.claude/skills/"
cp -r anzen/agents/.      "$PROJ/.claude/agents/"
```

## 依存

スクリプトは `openpyxl` を必要とする（`skills/anzen/scripts/requirements.txt`）。任意の Python 仮想環境に導入して使う。

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r anzen/skills/anzen/scripts/requirements.txt
```

> SKILL.md / エージェント内の実行例は作者環境の venv（`~/notebook/OpsReviewer/.venv/bin/python`）を参照している。
> 別環境では自分の Python（openpyxl 導入済み）に読み替えること。

## 使い方

導入後、対象プロジェクトで `/anzen <file.xlsx>` を実行する。詳細は `skills/anzen/SKILL.md` を参照。
