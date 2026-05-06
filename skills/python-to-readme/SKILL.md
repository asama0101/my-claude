---
name: python-to-readme
description: Pythonプロジェクトのコードを読み込み、README.mdを自動生成するスキル。コードファイル・ディレクトリが提供された場合に必ず使用すること。「READMEを作って」「READMEを書いて」「README.mdを生成して」などのキーワードが含まれる場合にも積極的に使用する。Pythonスクリプト・パッケージ・JupyterノートブックなどすべてのPythonプロジェクトに対応する。
---

# Pythonプロジェクト → README.md 生成スキル

Pythonプロジェクトのコードを解析し、README.mdをプロジェクトルートに生成する。

---

## インプット

ユーザーは以下のいずれかの形式でコードを提供する。

| 形式 | 例 | 備考 |
|---|---|---|
| ディレクトリパス | `/path/to/project/` | プロジェクト全体を対象にする場合（推奨） |
| ファイルパス（複数） | `/path/to/main.py`, `/path/to/module.py` | 関連ファイルを列挙 |
| ファイルパス（1つ） | `/path/to/main.py` | 単一スクリプトの場合 |
| アップロードファイル | チャットに添付された `.py` ファイル | `/mnt/user-data/uploads/` に配置される |
| コードの直接貼り付け | チャットにコードをペースト | 一時ファイルとして `/home/claude/` に保存して処理する |

**不明な場合はユーザーに確認する:**
- 対象ファイル/ディレクトリのパスが指定されていない場合は、パスを教えてもらう

---

## README.mdの構成

以下のセクションを含める（コードの内容に応じて省略可）。

| セクション | 必須 | 内容 |
|---|---|---|
| バッジ行 | 条件付き | Python バージョン、ライセンス等のバッジ（判明する場合） |
| 概要・目的 | ✅ | プロジェクトの概要、解決する課題、特徴 |
| ディレクトリ構成 | ✅ | プロジェクトのファイル・フォルダ構造 |
| インストール手順 | ✅ | 必要な環境、依存関係のインストール方法 |
| 使い方（Usage） | ✅ | 基本的な実行方法、コマンド例、主要オプション |
| 設定・環境変数 | ✅ | 必要な環境変数、設定ファイルのキーと説明 |
| コントリビューション | ✅ | 開発への参加方法、ブランチ戦略、PR手順 |

---

## 手順

### Step 1: コードと設定ファイルを収集する

```bash
# ディレクトリ構造の把握
find <プロジェクトルート> -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' | sort

# 依存関係・設定ファイルを確認
cat requirements.txt 2>/dev/null || cat pyproject.toml 2>/dev/null || cat setup.py 2>/dev/null
cat .env.example 2>/dev/null; cat config.yaml 2>/dev/null

# エントリポイントを読む
cat main.py 2>/dev/null || cat __main__.py 2>/dev/null || cat app.py 2>/dev/null

# 既存のREADMEがある場合は参考にする
cat README.md 2>/dev/null
```

### Step 2: コードを解析する

以下の観点でコードを読み込む。

1. **プロジェクト概要**: モジュール名、docstring、コメントから目的を読み取る
2. **エントリポイント**: `main()`, `if __name__ == "__main__"`, CLIの引数定義（`argparse`, `click` 等）
3. **ディレクトリ構造**: ファイル・フォルダの役割を把握する
4. **インストール要件**: `requirements.txt` / `pyproject.toml` / `setup.py` からPythonバージョンと依存ライブラリを取得
5. **設定・環境変数**: `os.environ`, `os.getenv`, `dotenv`, `.env.example` 等から環境変数を列挙
6. **実行例**: CLIオプション、引数、典型的なユースケースを把握

### Step 3: README.mdを生成する

以下のテンプレートに沿ってREADME.mdを生成する。

---

## README.mdテンプレート

````markdown
<!-- バッジ（判明する場合のみ） -->
![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/License-MIT-green)

# <プロジェクト名>

> <プロジェクトの1行説明>

<プロジェクトの概要を3〜5文で記述。何を解決するか、誰が使うか、主な特徴を含める>

---

## 目次

- [ディレクトリ構成](#ディレクトリ構成)
- [インストール](#インストール)
- [使い方](#使い方)
- [設定・環境変数](#設定環境変数)
- [コントリビューション](#コントリビューション)

---

## ディレクトリ構成

```
<プロジェクト名>/
├── main.py          # エントリポイント
├── requirements.txt # 依存ライブラリ
├── .env.example     # 環境変数のサンプル
├── docs/
│   └── design.md   # 詳細設計書
└── <module>/
    ├── __init__.py
    └── ...
```

---

## インストール

### 前提条件

- Python 3.x 以上
- （その他必要なシステム要件）

### 手順

```bash
# リポジトリをクローン
git clone <repository-url>
cd <プロジェクト名>

# 仮想環境を作成・有効化（推奨）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存ライブラリをインストール
pip install -r requirements.txt
```

---

## 使い方

### 基本的な実行

```bash
python main.py
```

### オプション

```bash
python main.py --option value   # <説明>
python main.py --help           # ヘルプを表示
```

### 実行例

```bash
# <典型的なユースケースの説明>
python main.py --input data.csv --output result.json
```

---

## 設定・環境変数

`.env.example` をコピーして `.env` を作成し、各値を設定する。

```bash
cp .env.example .env
```

| 変数名 | デフォルト値 | 必須 | 説明 |
|---|---|---|---|
| `DATABASE_URL` | なし | ✅ | DB接続文字列 |
| `LOG_LEVEL` | `INFO` | - | ログレベル（DEBUG/INFO/WARNING/ERROR） |

---

## コントリビューション

1. このリポジトリをフォーク
2. フィーチャーブランチを作成する（`git checkout -b feature/your-feature`）
3. 変更をコミットする（`git commit -m 'Add your feature'`）
4. ブランチにプッシュする（`git push origin feature/your-feature`）
5. プルリクエストを作成する

バグ報告・機能要望は Issue にてお願いします。
````

---

## 品質チェックリスト

README.md を生成した後、以下を確認する。

- [ ] プロジェクト名・1行説明が具体的に記述されている
- [ ] ディレクトリ構成がコードの実際の構造と一致している
- [ ] インストール手順のPythonバージョンが `pyproject.toml` / `requires.txt` と一致している
- [ ] Usageのコマンド例がエントリポイントの実装と一致している
- [ ] 設定・環境変数がコード中の `os.getenv` 等と一致している
- [ ] バッジのPythonバージョン・ライセンスが判明する場合のみ記載している
- [ ] 目次のアンカーリンクがセクション見出しと対応している

---

## 出力

- ファイル名: `README.md`
- 出力先: `<プロジェクトルート>/`（プロジェクトのルートディレクトリ直下）
- 既存の `README.md` がある場合はユーザーに上書き確認をしてから生成する

---

## 注意事項

- CLIツールの場合は `--help` の出力をUsageセクションに活用する
- docstringが充実している場合はそこから概要を引用する
- `.env.example` が存在する場合はそこから環境変数を正確に列挙する
- ライセンスファイル（`LICENSE`）が存在する場合はバッジとフッターに反映する
