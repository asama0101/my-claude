---
name: tdd-gates
description: |
  TDD × 10品質ゲートのオーケストレータ。AI駆動開発の品質問題（動くように見えて中身がバグだらけ・テストの形骸化・RED未確認・自己承認）を、ゲート順序の強制と Critical即FAIL＋証拠要求の採点で構造的に潰す。substantial な実装（新機能・バグ修正・非自明な変更）で使う。

  以下のような発言・状況で起動すること:「TDDで実装して」「テストファーストで」「品質ゲートを回して」「gate を回して」「新機能を実装して（テスト付きで）」「バグを直して（回帰テスト付きで）」。substantial なコード変更の着手時に積極的に起動する。trivial（数行・設定/ドキュメント）は使わず単一軽量 Agent に委任する（比例ルール）。
---

# TDD 10品質ゲート・オーケストレータ

あなた（Main）は**オーケストレータ**に徹する。自分でテストや実装を書かず、各ゲートを担当ロールのサブエージェントへ委任し、順序と合否を強制し、台帳に証拠を残す。

**中核原則**: superpowers の Iron Law「NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST」を規律の根拠とする（`superpowers:test-driven-development` を原則レイヤとして参照）。本スキルはその工程を**強制**する層。

## 起動時にやること（チェックリスト）

各項目を todo 化して順に実施する。**進捗は `TaskCreate`/`TaskUpdate` で可視化**し（ゲート／マイルストーンごとにタスクを作り、着手時 in_progress・完了時 completed に更新）、ユーザーが進捗を追えるようにする。

1. **プロファイル確定**: 対象言語のプロファイルを1つ選ぶ（Python は `references/profiles/pytest.md`）。パス→テスト種別の対応表を読み、対象ファイルのテスト種別（unit/integration/e2e）を判定して**ユーザーに確認**する。**Gate9(CI) を回すなら、プロファイルの「CI ステージ」定義（lint/typecheck/build/unit/integration/主要E2E の具体コマンド）も確認する**。
   - **対象言語のプロファイルが無い場合**（現状は pytest の1本のみ）は、`references/profiles/_template.md` から新規プロファイルを起草する。テスト実行コマンドと合格ログ形式を**ユーザーに承認してもらってから**ゲートを開始する（未定義のまま pytest 前提で進めない）。
   - **確定したプロファイルのパスは、generator / evaluator を起動するたびにプロンプトへ必ず明記して渡す**（台帳パスも同様。エージェント側での推測は禁止）。
2. **台帳を作成**: 対象プロジェクトのリポジトリルート直下に `.tdd-gates/ledger-<タスクスラッグ>.md` を作る（タスクごとに一意名にして、複数タスクの並列実装でも衝突させない。`.tdd-gates/` は `.gitignore` への追加を推奨し、未登録ならユーザーに提案する）。ここに各ゲートの verdict・スコア率・証拠スニペット・CONDITIONAL 再評価回数を記録していく。これはゲートのバイパスと自己承認を防ぐ監査証跡で、scratchpad と違いセッションが切れても消えない。**セッションをまたいで再開する場合は、既存台帳を Read し、記録済みの verdict の続きから再開する**。台帳には次を必須で残す:
   - **各 PASS には、その採点を行った tdd-evaluator が自ら再実行した検証コマンドの出力行を添付**する。evaluator の実行痕跡が無い PASS は無効（未実施扱い）とし、次ゲートへ進めない。
   - **Gate4(RED) 時点でテストファイルの内容（パス＋本文 or ハッシュ）を固定記録**し、Gate5・Gate6 で照合する（assert 骨抜き検知）。
   - **ベースライン記録**: 台帳作成直後・Gate 開始前に、プロファイル定義の全体テストコマンドを1回実行し、既存の failed/error のテストID一覧をベースラインとして台帳に記録する（全緑ならその旨を記録）。**ベースラインの既存赤テストを Generator が無断で修正・skip 化することは禁止**（扱いが必要ならユーザーに確認する）。
3. **ゲートを順に駆動**（下記）。

## ゲート駆動ループ

`references/gates.md` の定義と `references/scoring.md` の採点で、次の順に進める:

```
Gate1(コンテキスト分析・要件整理) → Gate2(受入基準・テスト設計) → Gate3(事前レビュー)
  → Gate4(RED) → Gate5(GREEN) → Gate6(REFACTOR)
  → [e2e またはビュー層変更なら Gate7(UI/UX)] → Gate8(差し戻し判定)
  → 受け入れ確認(＋受け入れチェックリスト生成) → [CI運用なら Gate9(CI品質ゲート整備)] → [doc影響あれば Gate10(ドキュメント同期)] → 完了
```

各ゲートで:
1. **担当ロールへ委任**（下表）。Generator と Evaluator は必ず別サブエージェントで起動する（分離原則の正典は `references/gates.md` 冒頭）。
2. **証拠を受け取り採点**: Evaluator ゲートは `tdd-evaluator` が `scoring.md` でスコアカード化。
3. **合否で分岐**（閾値・Critical即FAIL・再評価上限の正本は `references/scoring.md`）:
   - **PASS**（≥80% かつ Critical 達成）→ 台帳に記録して次ゲート。
   - **CONDITIONAL**（60–79%）→ 指摘を Generator に戻して修正 → 再評価。**最大2回**。台帳の再評価カウンタを増やす。
   - **FAIL**（<60% または Critical 未達、あるいは CONDITIONAL 2回で未達）→ **停止してユーザーに差し戻す**。勝手に先へ進めない。

### ロール委任表

| ゲート | 委任先 | 起動方法 |
|--------|--------|----------|
| 1 コンテキスト分析・要件整理 | `planner` が起草 → `tdd-evaluator` が rubric で採点（要件網羅の抜け漏れ候補は Stop&Ask） | 起草＋採点 |
| 2 受入基準・テスト設計 | `planner` が起草 → `tdd-evaluator` が rubric で採点（PASS で次へ） | 起草＋採点 |
| 3 事前レビュー | `tdd-evaluator` が単独で採点（既定）。セキュリティ/性能敏感な計画のみ該当 reviewer を条件付き並列起動（規則の正典は gates.md） | 単独（条件付き並列） |
| 4 RED / 5 GREEN / 6 REFACTOR | `tdd-generator` | **同一 Generator を `SendMessage` で継続**（RED→GREEN→REFACTOR は同じ文脈。毎回新規起動で対象ファイルを読み直させない）。採点は各段階とも `tdd-evaluator` に委任（実装者との分離は維持） |
| 7 UI/UX（e2e またはビュー層変更時） | `frontend-design` スキル＋敵対的クロスレビュー | 条件付き |
| 8 差し戻し判定 | `review-*` を**並列**起動 → `tdd-evaluator` が集約スコアカード | 並列＋集約 |
| 9 CI品質ゲート整備（CI運用時） | ワークフロー生成は `doc-updater` に委任（profile の CI ステージコマンド駆動）→ `tdd-evaluator` が必須ステージ被覆を採点 | 条件付き・生成＋採点 |
| 10 doc同期（影響時） | `doc-updater` | 条件付き |

- **Gate8（および Gate3 で条件付き reviewer を起動した場合）の並列集約**: Main が review-* を並列起動し、**各 reviewer には所見を scratchpad の所見ファイルに直接書き出させる**（例 `reviews/<タスクスラッグ>-<gate>-<dimension>.md`。並列実装時の衝突を防ぐためタスクスラッグを必ず含める）。`tdd-evaluator` はその所見ファイル群を**自ら Read** して集約採点し、Critical即FAIL を判定する（review-* は所見のみ、tdd-evaluator が点数化）。**Main は所見本文を要約・改変せず、経路から外れる**——工程当事者である Main が Critical 所見を軟化させて自己承認するのを防ぐため。各ゲートの reviewer 構成・本数の正典は `references/gates.md`。
- **採点の継続**: `tdd-evaluator` も1本のスレッドを `SendMessage` で全ゲート継続してよい（scoring.md・台帳・差分の再読み込みコストを避ける）。Generator との分離が保たれていれば自己承認排除は損なわれない。

## 重要ルール

- **証拠主義**: 「テストは通るはず」「多分失敗する」は無効。RED/GREEN は必ず**実行ログ**を証拠として台帳に残す（`scoring.md` の証拠フォーマット）。
- **Critical即FAIL**: スコアが高くても Critical 未達なら即 FAIL。特に Gate4 は「実際に失敗したログ」が無ければ通さない。
- **オーケストレータのコンテキスト衛生**: Main は生ログ全文を抱えない。各サブエージェントには結論・スコア・証拠スニペット・`file:line` だけを蒸留して返させ、台帳に要点を残す。
- **並列実装は worktree 分離必須**: 複数タスクを並列で実装する場合は `git worktree` 等で作業ツリーをタスクごとに分離する（同一ワーキングツリーでは evaluator の `git diff`・全体テスト実行に他タスクの差分が混入し、証拠が汚染されるため）。
- **段階導入の限界**:
  - Gate4–5(RED→GREEN) だけへの簡略（small ルート）は、次の4条件を**すべて**満たす場合に限る（数値基準の正典はグローバル CLAUDE.md 作業ルーティング表 small 行）: ①差分 2 ファイル以下 ②実装差分 50 行以下（テストを除く） ③公開インターフェース不変 ④既存テストが変更対象範囲を被覆。1つでも外れたら substantial としてフル工程。
  - **substantial では Gate3(事前レビュー)・Gate8(差し戻し判定) を省略不可**（唯一の実レビュー層のため）。
  - 簡略の可否は **tdd-evaluator が Gate1 採点時に上記4条件を証拠（`git diff --stat`・既存テスト一覧）と照合して判定**する。planner は該当見込みを計画書に申告するのみで承認主体ではない。判定根拠は台帳に記録する。
  - Gate4 の Critical（実失敗ログ）はいかなる場合も省略しない。
- **仕様変更時の巻き戻し**: ユーザー起因の仕様変更が入ったら、①台帳に「仕様変更」エントリ（日時・変更内容・ユーザー指示の要旨）を記録し、②影響するテストは Gate4 からやり直す（Gate4 固定テスト記録を更新し、更新理由を台帳に残す）。③evaluator は台帳の仕様変更エントリと照合し、正当なテスト変更と assert 骨抜きを区別する。
- **Gate8 → 受け入れ確認 → Gate9(CI) → Gate10(doc)**: Gate8 PASS 後、Gate9(CI品質ゲート整備)・Gate10(doc同期) に進む前に**ユーザーの受け入れ確認を取る**（グローバル CLAUDE.md「実装後の受け入れ→ドキュメント更新」準拠）。NG なら修正へ戻る。この受け入れ確認の際、`tdd-evaluator` が**受け入れチェックリスト**（受入基準＋Gate8 の5次元＋例外処理・権限漏れ・変更影響範囲）を生成して台帳に保存し、ユーザーの手動確認を再現可能にする。
  - **承認粒度（複数マイルストーン計画の例外）**: **ユーザーが既に承認した計画**が複数マイルストーンに分かれ、その各マイルストーンで本スキルを回している場合は、**clean PASS（FAIL も未解決 CONDITIONAL も無い）の Gate8 では、受け入れ確認で停止しない**。進捗だけ報告して次のマイルストーンへ自動で進む。ユーザーに確認・判断を求めて止まるのは **FAIL / CONDITIONAL 未解決 / 仕様が曖昧（Stop&Ask）/ 最終成果物** の時だけ。単一タスク（1計画＝1実装）や計画外の変更では、従来どおり Gate8 後に受け入れ確認を取る。

## 参照ファイル

- `references/gates.md` — 10ゲートの内容・Critical・証拠要件・順序。
- `references/scoring.md` — 0–3採点・80%/60–79%・Critical即FAIL・CONDITIONAL上限・証拠/スコアカード形式。
- `references/profiles/pytest.md` — Python/pytest のパス判定・実行コマンド・合格ログ形式（深い作法は agents/references/pytest.md へ委譲）。
- `references/profiles/_template.md` — 新言語追加用スケルトン。
