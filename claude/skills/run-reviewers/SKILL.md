---
name: run-reviewers
description: |
  コード変更後に複数のレビュアーエージェントを並列実行し、統合レビューレポートを生成する。
  実装完了後・PR作成前・テスト後のマージ前に必ず使用すること。
  「全レビューして」「レビューして」「reviewer を走らせて」「変更をレビューして」
  「コードをチェックして」「品質チェック」「マージ前確認」などの発言で起動する。
  単一レビュアーでなく複数を一括実行したい場合は必ずこのスキルを使うこと。
---

# run-reviewers — 統合レビュー実行スキル

コード変更後に 5 つのレビュアーエージェントを**並列実行**し、統合レビューレポートを生成する。

## 使用するレビュアー

| エージェント | 検査内容 |
|-------------|---------|
| reviewer-correctness | バグ・論理エラー・冪等性・エラーハンドリング・境界値 |
| reviewer-security | SQL injection・認証・機密情報・パストラバーサル |
| reviewer-performance | メモリ効率・DB / I/O 最適化・並列処理 |
| reviewer-maintainability | 命名・構造・複雑さ・DRY・YAGNI ＋ docstring・CLAUDE.md・仕様書 整合性 |
| reviewer-test | カバレッジ・フィクスチャ・エッジケース ＋ 仕様書要件・スキーマ適合・冪等性 |

## 実行手順

### Step 1: 変更内容の収集

変更範囲を把握する（Bash ツール使用）：

```bash
git diff HEAD --stat       # 変更の概要（ステージング未コミット）
git diff HEAD --name-only  # 変更ファイル一覧
```

コミット済みの場合：

```bash
git show --stat HEAD       # 直近コミットの変更概要
git show --name-only HEAD  # 直近コミットの変更ファイル
```

### Step 2: 5 つのレビュアーを同一ターン内で並列起動

`Agent` ツールで **同一ターン内・同時** に 5 つのサブエージェントを呼び出す（順次ではなく並列）。
各エージェントへのプロンプトには「変更されたファイル一覧と変更の概要」を含める。

さらに各プロンプトに**裏取り指示**を必ず含める：
「存在/不在・実装済み/未実装を断定する指摘は、仕様書・ドキュメントの記述だけで判断せず、必ず対象の実コード・テスト・生成物（ゴールデン等）を読んで裏取りすること。裏取りできない場合は断定せず『要確認』として報告する。」
（レビュアーは正本ドキュメントのみで断定しがちで、誤指摘の主因になるため）

```
同一ターンで Agent ツールを 5 回同時呼び出し:
  subagent_type: reviewer-correctness     → "以下の変更をレビューしてください: [ファイル一覧と変更概要]"
  subagent_type: reviewer-security        → "以下の変更をレビューしてください: [ファイル一覧と変更概要]"
  subagent_type: reviewer-performance     → "以下の変更をレビューしてください: [ファイル一覧と変更概要]"
  subagent_type: reviewer-maintainability → "以下の変更をレビューしてください: [ファイル一覧と変更概要]"
  subagent_type: reviewer-test            → "以下の変更をレビューしてください: [ファイル一覧と変更概要]"
```

### Step 3: 統合レポートの生成

全エージェント完了後、以下のフォーマットで統合レポートを出力する：

---

## 統合レビューレポート

### サマリーテーブル
| レビュアー | CRITICAL | HIGH | MEDIUM | LOW | 判定 |
|-----------|---------|------|--------|-----|------|
| correctness     | N | N | N | N | ✅/⚠️/🚫 |
| security        | N | N | N | N | ✅/⚠️/🚫 |
| performance     | N | N | N | N | ✅/⚠️/🚫 |
| maintainability（＋docs） | N | N | N | N | ✅/⚠️/🚫 |
| test（＋requirements）    | N | N | N | N | ✅/⚠️/🚫 |

### 全体判定
- ✅ **承認**（全レビュアーで CRITICAL / HIGH 問題なし）
- ⚠️ **警告**（HIGH 問題あり・要注意マージ）
- 🚫 **ブロック**（CRITICAL 問題あり・修正必須）

### 要対応事項（重大度降順）
各レビュアーの CRITICAL・HIGH 問題を重大度降順でリスト化する。
MEDIUM 以下はユーザーが確認したい場合のみ展開する。

---

## 選択的実行

一部のレビュアーのみ実行したい場合はユーザーが明示する：
- セキュリティのみ: `reviewer-security` を単独指定
- 品質重視: `reviewer-correctness` + `reviewer-test` + `reviewer-maintainability`
- リリース前チェック: `reviewer-test`（要件適合を内包）+ `reviewer-correctness` + `reviewer-security`

指定がなければ 5 つ全て並列実行する。
