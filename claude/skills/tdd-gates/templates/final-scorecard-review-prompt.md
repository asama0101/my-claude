# CP-D 最終スコアカード差し替え手順（final-scorecard-review-prompt）

**土台テンプレ**: `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0/skills/requesting-code-review/code-reviewer.md`

SDD の「## Final Review」は既定で `code-reviewer.md` を単独ディスパッチする。CP-D はこの単独ディスパッチを、**review-* 5本の並列起動 + `tdd-evaluator` 集約**に丸ごと差し替える。本ファイルは土台テンプレの本文を複製せず、差し替え後の手順のみを記述する（各 reviewer の詳細チェックリストは `~/.claude/agents/review-*.md` と `~/.claude/agents/references/review.md` が正典）。

## 手順1: 並列ディスパッチ（Main が実施）

`superpowers:dispatching-parallel-agents` の機構に従い、次の5エージェントを**同一メッセージ内で並列**に起動する。逐次起動しない。

- `review-correctness`
- `review-security`
- `review-performance`
- `review-test`
- `review-maintainability`

各エージェントへの指示に、対象の `[BASE_SHA]`・`[HEAD_SHA]`（土台テンプレと同じプレースホルダ）と、**所見の書き出し先ファイルパス**を明記する。

```
scratchpad/reviews/<タスクスラッグ>-cp-d-<dimension>.md
```

（`<dimension>` は correctness/security/performance/test/maintainability。並列実装時の衝突防止のため `<タスクスラッグ>` はタスクごとに一意にする。）

各 reviewer は `~/.claude/agents/references/review.md` の出力フォーマット（詳細ブロック＋サマリー表＋3択判定）に従い、**所見をこのファイルに直接書き出す**。Main には結論のみを返させ、所見本文を Main のコンテキストに流さない。

## 手順2: 集約（tdd-evaluator が実施）

Main は `tdd-evaluator` を起動し、上記5ファイルのパス一覧を渡す。`tdd-evaluator` は次を行う。

1. 5ファイルすべてを自ら Read する（Main による要約・選別を経由しない）。
2. 所見ファイル数が5本と一致するか照合する。不足があれば採点せず、不足次元を明記して Main に差し戻す。
3. `~/.claude/skills/tdd-gates/references/scoring.md`「スコアカード出力形式（CP-C〜F用）」の Spec Compliance 形式に集約する。5次元（正確性／セキュリティ／性能／テスト品質／保守性）それぞれの所見を反映する。
4. Critical 判定基準は `~/.claude/skills/tdd-gates/references/checkpoints.md` CP-D の Critical 行（仕様不適合／既存回帰／偽装テスト検出）に従う。
5. 集約後のスコアカードは Main が `progress.md` にも書き出す（`tdd-evaluator` は Bash 書き込みを持たないため。チャット報告のみで終わらせない）。

## 手順3: ミューテーション検証（tdd-evaluator が実施）

偽装テスト検出のため、目視に加えて能動的なバグ注入検証を行う。

- **実施条件**:
  - **必須**: 期待値が実装ロジックの写しに見える／assert が実装側の定数・内部関数を参照している／テストが実装から期待値を計算している——このような徴候が1つでもあるとき。
  - **スモーク**: 徴候が無くても、差分の中心となる代表1テストに1箇所バグを注入し、落ちることを確認する。
- **安全手順（実体を汚さない）**: 対象ファイル群を scratchpad（例 `scratchpad/mutation_ws_<タスクスラッグ>/`）に**コピー**し、コピーに対してのみバグ注入・テスト実行する。プロジェクトの実体ファイルは一切書き換えない。
- **事後確認**: 検証後に `md5sum`／`diff` で実体ファイルが無改変であることを確認し、その旨をスコアカードの証拠に含める。

（この検証手順は `~/.claude/agents/tdd-evaluator.md` に既に定義されている内容と同一である——CP-D 用に新設する手順ではなく、CP-D で必ず実施することをここで明記する。）

## リトライ機構

SDD 純正の Final Review（1修正波 + 1 scoped re-review、adjudicate residuals）にそのまま従う。tdd-gates 独自の再評価カウンタは持たない。修正波のディスパッチ先も `review-*` 5本ではなく、指摘された次元の実装者（SDD implementer）への差し戻しである点は SDD 標準と同じ。

## Main が埋めるプレースホルダ

- `[BASE_SHA]` / `[HEAD_SHA]`: 土台テンプレと同じ
- `[TASK_SLUG]`: 所見ファイル名に使う一意スラッグ
- 対象言語プロファイルのパス（review-test・review-performance が実行コマンドを把握するため）
