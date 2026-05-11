# docs.md 改善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `rules/docs.md` の過不足・矛盾を修正し、ドキュメントルールの完全性・一貫性を確保する

**Architecture:** rules/docs.md を単一の編集対象とし、過剰コンテンツは `docs/templates/` へ切り出す。各タスクは独立した関心事を対応し、コミットも個別に行う。

**Tech Stack:** Markdown ファイル編集のみ。テストツール不要。

---

## 問題サマリーと修正方針

| 優先度 | 問題 | 修正方針 |
|---|---|---|
| 高 | paths frontmatter に `**/*.html` 欠落 | frontmatter に追加 |
| 高 | ADR 記述フォーマット未定義 | ADR テンプレートセクションを追加 |
| 高 | CHANGELOG 記法規約なし | Keep a Changelog 形式を明記 |
| 高 | `docs/spec.md` が Markdown ルールの対象外 | 記法セクションの適用範囲を修正 |
| 中 | HTML 共通テンプレートへの言及なし | `docs/templates/` を整備しルールから参照 |
| 中 | ドキュメント更新・廃止ルールなし | 更新・廃止セクションを追加 |
| 低 | curl コマンド・HTML スニペットの過剰埋め込み | テンプレートへ移動し本文を簡潔化 |
| 低 | design-review.md との作成指針の重複 | 重複削除・相互参照化 |

## ファイル構成

```
rules/
  docs.md                  ← 全タスクで変更
docs/
  templates/
    base.html              ← Task 5 で新規作成（HTML共通テンプレート）
    flow.html              ← Task 5 で新規作成（処理フロー設計テンプレート）
```

---

## Task 1: paths frontmatter の修正

**Files:**
- Modify: `rules/docs.md`（1–5行目）

### 問題詳細

CLAUDE.md 210行目では docs.md の適用パスを `docs/**`, `**/*.html` と定義しているが、docs.md 自体の frontmatter は `docs/**` のみ。`docs/` 外に置かれる `.html` ファイル（例: プロジェクトルートの HTML ページ）に rules が適用されない。

- [ ] **Step 1: frontmatter を修正する**

`rules/docs.md` の先頭を以下に変更する:

```yaml
---
paths:
  - "docs/**"
  - "**/*.html"
---
```

- [ ] **Step 2: CLAUDE.md の記載と一致していることを目視確認する**

CLAUDE.md 210行目:
```
| `.claude/rules/docs.md` | `docs/**`, `**/*.html` | ドキュメント配置・記法、図示ガイドライン |
```
と一致していれば OK。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "fix(docs): docs.md の paths に **/*.html を追加"
```

---

## Task 2: ADR 記述フォーマットの追加

**Files:**
- Modify: `rules/docs.md`（プロジェクトドキュメント表の後ろに追記）

### 問題詳細

プロジェクトドキュメント表に「ADR: `docs/design/decisions/*.html`」が記載されているが、ADR の書き方が未規定。開発者ごとに書き方がバラバラになるリスクがある。ADR は設計判断の根拠を将来の開発者（= 自分たち）に伝えるドキュメントであり、フォーマットの統一が特に重要。

- [ ] **Step 1: ADR セクションを「プロジェクトドキュメント」表の直後に追記する**

```markdown
### ADR（アーキテクチャ決定記録）

重要な設計判断を `docs/design/decisions/ADR-NNN-<タイトル>.html` に記録する。
番号 NNN は連番（001, 002, …）。

**必須セクション:**

| セクション | 内容 |
|---|---|
| ステータス | `Proposed` / `Accepted` / `Deprecated` / `Superseded by ADR-NNN` のいずれか |
| コンテキスト | この決定が必要になった背景・制約・問題 |
| 決定 | 何を採用したか（1文で明言する） |
| 影響 | この決定がもたらすトレードオフ・副作用 |
| 代替案 | 検討したが採用しなかった案と却下理由 |

ステータスが `Superseded` の場合、後継 ADR へのリンクを本文先頭に置く。
```

- [ ] **Step 2: 目視確認**

ADR 番号・必須5セクションが過不足なく記載されていることを確認する。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "docs(rules): docs.md に ADR 記述フォーマットを追加"
```

---

## Task 3: CHANGELOG 記法規約の追加

**Files:**
- Modify: `rules/docs.md`（プロジェクトドキュメント表の直後、ADR セクションの後ろに追記）

### 問題詳細

プロジェクトドキュメント表に「CHANGELOG | リリース」が載っているが、記法が未規定。リリースノートの質が属人化し、レビューの基準も作れない。Keep a Changelog（https://keepachangelog.com/ja/）を採用し、一貫した形式を保証する。

- [ ] **Step 1: CHANGELOG セクションを追記する**

```markdown
### CHANGELOG

[Keep a Changelog](https://keepachangelog.com/ja/) 形式を採用する。
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う。

**セクション構造:**

```
## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [1.0.0] - YYYY-MM-DD
### Added
- 初回リリース
```

**ルール:**
- リリース前の変更はすべて `[Unreleased]` に追記する
- リリース時に `[Unreleased]` を `[x.y.z] - YYYY-MM-DD` に変更し、新しい `[Unreleased]` セクションを追加する
- 各変更は動詞（過去形）で始める: 「〇〇を追加した」「〇〇を修正した」
- Breaking Change は `### Changed` に `**破壊的変更:**` プレフィックスを付ける
```

- [ ] **Step 2: 目視確認**

セクション名 Added / Changed / Deprecated / Removed / Fixed / Security がすべて記載されていることを確認する。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "docs(rules): docs.md に CHANGELOG 記法規約を追加"
```

---

## Task 4: Markdown ルールの適用範囲修正と詳細記法追加

**Files:**
- Modify: `rules/docs.md`（「ドキュメント記法 > Markdown」セクション）

### 問題詳細

「ドキュメント記法 > Markdown `(.claude/)`」と対象を `.claude/` に限定しているため、`docs/spec.md`（外部仕様書）など他の Markdown ファイルにルールが適用されない。また見出し・リスト・テーブルの基本ルールが一切書かれておらず品質が属人化する。

- [ ] **Step 1: Markdown セクションの見出しを修正し、基本ルールを追記する**

現在の「### Markdown（.claude/）」セクション全体を以下に置き換える:

```markdown
### Markdown（`.claude/`・`docs/spec.md` 等）

**見出し:**
- H1（`#`）はファイルごとに1つ、ドキュメントタイトルのみ
- H2（`##`）で主要章、H3（`###`）で節。H4以下は原則使わない
- 見出しの前後に空行を置く

**リスト:**
- 箇条書きは `-` を使用（`*` は禁止）
- 番号付きリストは手順・順序に意味がある場合のみ
- ネストは2段階以内

**テーブル:**
- ヘッダー行は必須
- セル内改行は `<br>` で代替（Markdown テーブルは改行不可）
- 4列超・長文セルは箇条書きへの変換を検討する

**注意ボックス**（各章1〜2個まで）。GitHub Flavored Markdown の記法:

```markdown
> [!NOTE]
> 補足情報

> [!TIP]
> 推奨事項

> [!WARNING]
> 注意喚起

> [!CAUTION]
> 重大な警告・不可逆操作
```

**コードブロック:** 言語指定必須。
```

- [ ] **Step 2: 目視確認**

`.claude/` の限定表現が消え、`docs/spec.md` が対象に含まれていることを確認する。見出し・リスト・テーブル・注意ボックス・コードブロックの5項目がすべて記載されていることを確認する。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "docs(rules): Markdown ルールの適用範囲を spec.md まで拡張し詳細記法を追加"
```

---

## Task 5: HTML 共通テンプレートの整備

**Files:**
- Create: `docs/templates/base.html`（HTML 共通テンプレート）
- Create: `docs/templates/flow.html`（処理フロー設計テンプレート）
- Modify: `rules/docs.md`（「ドキュメント形式」or「作成の指針」セクションにテンプレート参照を追記）

### 問題詳細

全ドキュメントに「共通必須セクション（対象読者・前提知識 / 目的 / 関連リンク / 改訂履歴）」を課しているが、テンプレートファイルが存在せず、各ドキュメントが独自に実装する状態になっている。また Mermaid の実装コードが docs.md に直接埋め込まれており、実際の HTML ファイルを作るときに参照できない。

- [ ] **Step 1: `docs/templates/base.html` を作成する**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[ドキュメントタイトル]</title>
  <link rel="stylesheet" href="../assets/style.css">
  <script src="../assets/mermaid.min.js"></script>
  <script>mermaid.initialize({ startOnLoad: true });</script>
</head>
<body>

<header>
  <h1>[ドキュメントタイトル]</h1>
</header>

<section id="meta">
  <h2>基本情報</h2>
  <table>
    <tr><th>対象読者</th><td>[例: バックエンド開発者、インフラ担当]</td></tr>
    <tr><th>前提知識</th><td>[例: Python 基礎、REST API の概念]</td></tr>
    <tr><th>本ドキュメントの目的</th><td>[1〜2文で記載]</td></tr>
  </table>
</section>

<section id="related">
  <h2>関連ドキュメント</h2>
  <ul>
    <li><a href="./architecture.html">アーキテクチャ設計書</a></li>
    <!-- 他の関連ドキュメントを追加 -->
  </ul>
</section>

<!-- ドキュメント本文をここに追加 -->

<section id="history">
  <h2>改訂履歴</h2>
  <table>
    <thead>
      <tr><th>日付</th><th>バージョン</th><th>変更内容</th><th>担当</th></tr>
    </thead>
    <tbody>
      <tr><td>YYYY-MM-DD</td><td>1.0</td><td>初版作成</td><td></td></tr>
    </tbody>
  </table>
</section>

</body>
</html>
```

- [ ] **Step 2: `docs/templates/flow.html` を作成する**

処理フロー設計専用のテンプレートを作成する。base.html を継承した構成とする:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[機能名]の処理フロー</title>
  <link rel="stylesheet" href="../../assets/style.css">
  <script src="../../assets/mermaid.min.js"></script>
  <script>mermaid.initialize({ startOnLoad: true });</script>
</head>
<body>

<header>
  <h1>[機能名]の処理フロー</h1>
</header>

<section id="meta">
  <h2>基本情報</h2>
  <table>
    <tr><th>対象読者</th><td>[例: バックエンド開発者]</td></tr>
    <tr><th>前提知識</th><td>[例: アーキテクチャ設計書を読了していること]</td></tr>
    <tr><th>本ドキュメントの目的</th><td>[機能名]の処理の流れ・分岐・エラーハンドリングを明示する</td></tr>
  </table>
  <p>関連: <a href="../architecture.html">アーキテクチャ設計書</a> / <a href="../../docs/spec.md">外部仕様書</a></p>
</section>

<section id="overview">
  <h2>1. 全体フロー（概略）</h2>
  <p>入力: [入力データの説明]<br>出力: [出力データの説明]</p>

  <pre class="mermaid">
flowchart TD
    Start([開始]) --> Input[入力受付]
    Input --> Process[処理]
    Process --> |成功| Output([出力])
    Process --> |失敗| Error([エラー処理])
  </pre>

  <p><strong>凡例:</strong> 角丸四角 = 端点、四角 = 処理、菱形 = 分岐</p>
</section>

<section id="sub-process-1">
  <h2>2. [サブ処理1の名前]</h2>
  <p>§1 の「[ステップ名]」の詳細。</p>
  <!-- Mermaid 図を追加 -->
</section>

<!-- 必要に応じてサブ処理セクションを追加 -->

<section id="history">
  <h2>改訂履歴</h2>
  <table>
    <thead>
      <tr><th>日付</th><th>バージョン</th><th>変更内容</th><th>担当</th></tr>
    </thead>
    <tbody>
      <tr><td>YYYY-MM-DD</td><td>1.0</td><td>初版作成</td><td></td></tr>
    </tbody>
  </table>
</section>

</body>
</html>
```

- [ ] **Step 3: docs.md にテンプレート参照を追記する**

「ドキュメント形式」セクションの末尾に以下を追加する:

```markdown
新規ドキュメント作成時は `docs/templates/base.html` をコピーして使用する。
処理フロー設計書は `docs/templates/flow.html` をコピーして使用する。
Mermaid（`mermaid.min.js`）は `docs/assets/mermaid.min.js` にローカル保存する（CDN 直参照禁止）。
インストール: `curl -o docs/assets/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js`
```

- [ ] **Step 4: 目視確認**

`docs/templates/base.html` と `docs/templates/flow.html` が作成され、docs.md からテンプレートファイルが参照されていることを確認する。

- [ ] **Step 5: コミット**

```bash
git add docs/templates/base.html docs/templates/flow.html rules/docs.md
git commit -m "docs(rules): HTML共通テンプレートを整備しdocs.mdから参照"
```

---

## Task 6: ドキュメント更新・廃止ルールの追加

**Files:**
- Modify: `rules/docs.md`（「作成の指針」セクションの後ろに追記）

### 問題詳細

「仕様の検討・変更は `docs/` で合意してからコードへ反映する」（CLAUDE.md）とあるが、逆方向の「コード変更後にドキュメントをどう更新するか」「古くなったドキュメントをどう扱うか」のルールがない。実際には実装中に仕様が変わることは多く、更新漏れが起きやすい。廃止ドキュメントが残り続けると誤解の原因になる。

- [ ] **Step 1: 「ドキュメント更新・廃止」セクションを「作成の指針」の後ろに追記する**

```markdown
## ドキュメント更新・廃止

### 更新タイミング

- 機能追加・変更・削除 PR には、対応するドキュメント更新を同梱する（後回し禁止）
- 実装中に仕様が変わった場合は、コードをマージする前に `docs/` を更新する
- 更新対象の判断基準: 変更が外部 I/F・データモデル・セキュリティ要件・処理フローに影響する場合は必ず更新する

### 廃止・削除

廃止されたドキュメントはすぐに削除せず、以下の手順を踏む:

1. ファイル先頭の `<header>` 内に廃止バナーを追加する:
   ```html
   <p class="deprecated">【廃止】このドキュメントは廃止されました。後継: <a href="./新ドキュメント.html">新ドキュメント名</a></p>
   ```
2. 後継ドキュメントが確定し、参照元のリンクをすべて更新してから削除する
3. 削除は単独コミットとし、コミットメッセージに廃止理由を記載する
```

- [ ] **Step 2: 目視確認**

更新タイミング・廃止・削除の3段階が記載されていることを確認する。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "docs(rules): docs.md にドキュメント更新・廃止ルールを追加"
```

---

## Task 7: 過剰コンテンツの整理

**Files:**
- Modify: `rules/docs.md`（「HTML での Mermaid 実装」サブセクション、「ファイル構成例」サブセクション）

### 問題詳細

docs.md に以下の「手順・実装サンプル」が直接埋め込まれている。これらはルールではなくテンプレート・セットアップ手順であり、Task 5 で作成したテンプレートファイルへの参照に置き換えることで docs.md の責務を明確化する。

- curl インストールコマンド → Task 5 のテンプレート参照に移動済み
- HTML `<script>` タグと `<pre class="mermaid">` のコードスニペット → テンプレートで提供
- 処理フロー設計の `<h1>`, `<section>` HTML スケルトン → flow.html テンプレートで提供

- [ ] **Step 1: 「HTML での Mermaid 実装」サブセクションを削除・簡潔化する**

現在の「### HTML での Mermaid 実装」セクション（curl コマンド + HTML コードブロック）を削除し、Task 5 で追記したテンプレート参照の文言に統合されていることを確認する。

- [ ] **Step 2: 処理フロー設計の「ファイル構成例」サブセクションを削除する**

「### ファイル構成例」の `<h1>`, `<section>` タグを列挙したブロックを削除し、以下の1行で置き換える:

```markdown
新規作成時は `docs/templates/flow.html` を使用する（「処理フロー設計」セクション参照）。
```

- [ ] **Step 3: 目視確認**

docs.md に HTML コードブロックが残っていないこと、curl コマンドが「ドキュメント形式」セクションの1行参照のみであることを確認する。

- [ ] **Step 4: コミット**

```bash
git add rules/docs.md
git commit -m "refactor(rules): docs.md の過剰コンテンツをテンプレート参照に置き換え"
```

---

## Task 8: design-review.md との重複除去

**Files:**
- Modify: `rules/docs.md`（「作成の指針」セクション）

### 問題詳細

docs.md「作成の指針」5項目のうち3項目が design-review.md「ドキュメント完全性」と実質的に重複している。

| docs.md「作成の指針」| design-review.md「ドキュメント完全性」|
|---|---|
| 前提知識に依存せずドキュメント単体で伝わるよう記述する | 対象読者・前提知識の明記 |
| 略語は初出時に正式名称を併記、ドメイン固有概念は説明を付ける | 専門用語の初出時定義 |
| 要件 → 設計 → 実装の各段階で前段への参照を明示する | 前フェーズへのトレース |

「作成時の心得」と「レビュー時の観点」は役割が異なるが、同じ内容を両方に書くと更新漏れが起きる。docs.md は「書き方の規範」に特化し、「チェック観点」は design-review.md に一本化する。

- [ ] **Step 1: 重複3項目を削除し、design-review.md への参照を追加する**

「## 作成の指針」セクションを以下に置き換える:

```markdown
## 作成の指針

- What だけでなく Why（採用理由・却下した代替案）を書く
- 用語集を `docs/glossary.html` に集約し各ドキュメントから参照する

> レビュー時のチェック観点（対象読者の明記・専門用語の定義・前フェーズへのトレース等）は `.claude/rules/design-review.md` を参照する。
```

- [ ] **Step 2: 目視確認**

「作成の指針」が2項目 + design-review.md への参照1行になっていること。削除した3項目が design-review.md「ドキュメント完全性」に存在することを確認する。

- [ ] **Step 3: コミット**

```bash
git add rules/docs.md
git commit -m "refactor(rules): docs.mdの作成指針からdesign-review.mdと重複する項目を削除"
```

---

## セルフレビューチェックリスト

### 1. 問題カバレッジ

| 問題 | 対応タスク |
|---|---|
| paths `**/*.html` 欠落 | Task 1 ✓ |
| ADR フォーマット未定義 | Task 2 ✓ |
| CHANGELOG 記法なし | Task 3 ✓ |
| spec.md の Markdown ルール漏れ | Task 4 ✓ |
| HTML テンプレート未整備 | Task 5 ✓ |
| ドキュメント更新・廃止ルールなし | Task 6 ✓ |
| curl・HTML スニペット過剰埋め込み | Task 7 ✓ |
| design-review.md との重複 | Task 8 ✓ |

### 2. プレースホルダーチェック

- 各タスクのコードブロックに `[プレースホルダー]` が残っているが、これらはテンプレートとして意図的に残す表現（例: `[ドキュメントタイトル]`）であり実装上の穴ではない ✓

### 3. 一貫性チェック

- Task 5 でテンプレートファイルに curl コマンドを移動し、Task 7 で docs.md 本文から削除する → 順序依存あり。Task 5 → Task 7 の順で実行する ✓
- `docs/assets/mermaid.min.js` の参照パスが base.html（`../assets/`）と flow.html（`../../assets/`）で異なる → ディレクトリ階層の違いによるものであり正しい ✓
