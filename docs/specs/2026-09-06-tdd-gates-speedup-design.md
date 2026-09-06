# tdd-gates 高速化設計（CP-C／CP-D の実施方法見直し）

作成: 2026-09-06
対象: `~/.claude/skills/tdd-gates/`（SKILL.md・references/・templates/）、`~/.claude/agents/tdd-evaluator.md`・`tdd-implementer.md`・`review-correctness.md`
前段の設計: `docs/specs/2026-08-02-tdd-gates-lightweight-design.md`（CP-C証拠圧縮・evaluatorモデル階層化・CP-D条件付き本数）、`docs/specs/2026-08-09-tdd-gates-cp-d-baseline-reduction-design.md`（CP-D常時起動2本化）

## 1. 背景と目的

- ユーザー提起「tdd-gatesの処理をもっと早くしたい。ステップや実施方法を見直したい」。
- 痛点は次の2つに確定した。
  - CP-C: タスクごとの implementer→evaluator 往復が長い。タスク数が乗数になる。
  - CP-D: review-* 並列＋evaluator 集約＋ミューテーション検証の最終レビューが長い。
- 目的: 実証済みの検出力を落とさずに、CP-C と CP-D の所要時間を削る。
- 判断材料は 2026-08-09 の実効性監査（tdd-evaluator 実行242件）に基づく。
  - CP-C は「Invalid RED（collection ERROR を FAILED と誤認）」「循環アサーション」を複数プロジェクトで検出した実証済み層である。いずれも対象テストの再実行とテスト本体の Read で捕まえたもので、フルスイート実行が寄与した記録はない。
  - CP-D 全体の実効性は裏取りできていない。ミューテーション検証が欠陥を捕まえた記録はゼロである。

## 2. 採用した変更（4件）

| 記号 | 変更 | 速度効果 | 手放さないもの |
|---|---|---|---|
| A' | CP-C のフルスイート再実行を evaluator から外し、CP-D 冒頭の1回へ集約する | タスク数×1〜2回のフルスイートが1回になる | evaluator の自力再実行（対象テスト）・別コンテキスト採点 |
| A'' | RED 再現手順を明文化する（RED コミット＋隔離 worktree） | evaluator の試行錯誤を消す | 読み取り専用 Bash・作業ツリー不変 |
| B | CP-D のミューテーション検証を徴候ありのみに限定する | 無条件スモーク1件分の削減 | 徴候時のミューテーション必須・CP-C の RED 時テスト照合 |
| E | `review-correctness` のモデルを opus から sonnet へ揃える | CP-D 並列段の律速を解消 | reviewer 本数・条件付き起動ルール |

## 3. 検討して見送った案

- **CP-C evaluator のバッチ化（複数タスクをまとめて1回検証）**: 唯一の実証済み層を弱める。差し戻し粒度が粗くなり、RED 再現が複数 HEAD にまたがり複雑化する。見送り。
- **REFACTOR フルスイートを関連テストのみに縮小**: A' に吸収されるため個別対応は不要。
- **CP-D の集約 evaluator 廃止（review-* 平行採点）**: CP-D の実効性が測れていない状態で構造を崩さない。所見の突合・重複排除・スコアカード出力を失う。今回は保留。
- **implementer のフルスイート実行も廃止（第1節の案2）**: タスク間回帰が CP-D まで一切見えず、Final Review の1修正波で複数タスク跨ぎの回帰を直す破目になる。見送り。
- **`planner.md` の opus 指定**: 今回のスコープ外。触らない。

## 4. 第1節: CP-C フルスイートの CP-D 冒頭への集約（A'）

### 4.1 変更内容

- evaluator（CP-C）の再実行範囲を対象テストのみに縮小する。
  - GREEN Critical: 「対象テストが passed」のみ。全体でのベースライン比 failed 0 の要求を外す。
  - REFACTOR: 「対象テストが不変で、再実行が緑（GREEN 確定コミット〜HEAD の差分が空なら省略）」。フルスイート再実行の要求を外す。
- CP-D 冒頭に「手順0: フルスイート1回」を新設する。
  - Main が review-* 起動前にプロファイル定義の全体実行コマンドを1回実行し、ログを scratchpad 配下にファイル化する。
  - 判定基準は「ベースライン比の新規 failed 0」。ベースラインはタスクループ開始前に Main がフルスイートを1回実行して progress.md に記録したものを用いる。
  - 現行文書はベースラインの生成主体を規定していない（`pytest.md:65` は「進捗記録のベースライン記録」を参照するだけ）。SKILL.md の起動時チェックリストに「ベースライン取得（フルスイート1回、結果を progress.md へ）」を明記して手順0 の前提を確定する。
  - 集約 evaluator へログのパスを渡す。evaluator は Bash 書き込みを持たないため、実行主体は Main とする。
  - CP-D Critical には既に「既存回帰」が含まれており、手順が未定義だった箇所を埋める位置付けとする。
- implementer のフルスイート実行は維持する。
  - `tdd-implementer.md` の報告雛形「全体実行の合格サマリ」を残す。
  - タスク単位の回帰シグナルは実装者の自己報告として残る。独立検証は CP-D 手順0 の1回に集約される。
- browser-manual-e2e プロファイルも同じ規則に揃える（対象シナリオのみ毎タスク、全件は CP-D 手順0）。

### 4.2 編集対象

| ファイル | 箇所 | 変更 |
|---|---|---|
| `references/checkpoints.md` | :69（GREEN Critical） | 「全体でベースライン比の新規 failed 0」を削り、対象 passed のみに |
| 同 | :73（REFACTOR） | 「フルスイート再実行」を「対象テスト再実行」に |
| 同 | :75 | 「全緑」を「対象テストが緑」に |
| 同 | :79（証拠） | 「全既存テスト緑を含む」を削る |
| 同 | :85（CP-D 担当） | 並列起動の直前に「手順0: Main がフルスイート1回を実行しログをファイル化」を追加 |
| 同 | :89（CP-D 証拠） | フルスイートログを証拠に追加 |
| `agents/tdd-evaluator.md` | :48-49 | 「対象＋全体を再実行」を「対象のみ再実行」に。REFACTOR のフルスイート文言を対象テストに |
| `templates/task-evidence-addendum.md` | :28 | GREEN／REFACTOR のフルスイート文言を対象テストに |
| `templates/final-scorecard-review-prompt.md` | :7 の前 | 「手順0: ベースライン取得」節を新設 |
| 同 | :26 | 集約 evaluator へ渡すパス一覧にフルスイートログを追加 |
| 同 | :50-53 | プレースホルダに `[FULL_SUITE_LOG]` を追加 |
| `references/profiles/pytest.md` | :25 | 全体コマンドのコメントを「CP-D 手順0 用」に |
| 同 | :65-66 | GREEN／REFACTOR を対象テストのみに |
| `references/profiles/_template.md` | :20, :55-56 | 同上（雛形） |
| `references/profiles/bash-hook-test.md` | :22, :45-46 | 同上 |
| `references/profiles/browser-manual-e2e.md` | :23-24, :66-67 | 全シナリオ再実行を CP-D 手順0 へ移す |
| `SKILL.md` | :33（CP-D 行） | 担当欄に手順0 を反映 |
| 同 | :23（起動時チェックリスト項目2「証拠の記録先」） | ベースライン取得（フルスイート1回→progress.md 記録）を追加 |

### 4.3 代償

- 実装者が回帰を虚偽報告した場合だけ、CP-D 手順0 まで回帰が残る。手順0 で検出した回帰は SDD Final Review の修正波で直す。

## 5. 第2節: RED 再現手順の明文化（A''）

### 5.1 現状の穴

- RED（テストのみ）と GREEN（実装）を別コミットにする規定がない。implementer の報告雛形にコミット SHA 欄がない。
- evaluator は「対象テストを再実行し実際に失敗するか確認せよ」とあるが、GREEN 後の作業ツリーで RED 時点を作る手順が未定義。
- evaluator は読み取り専用 Bash（`tdd-evaluator.md:16`）で「実体を1バイトでも変更したら手続き違反」（:22）。`git stash`／`checkout` は作業ツリーを変えるため使えない。

### 5.2 変更内容

- implementer にコミット粒度を規定する。
  - RED コミット（テストファイルのみ）→ GREEN コミット（実装）→ REFACTOR コミット（任意）の順で切る。
  - TDD Evidence 雛形に RED／GREEN の short SHA 欄を追加する。
  - progress.md の証拠行に RED SHA を追記する。
  - SDD の「Commit your work」は複数コミットを禁じておらず、最終メッセージ欄も複数形のため衝突しない。
- evaluator の RED 再現手順を確定する。
  - scratchpad 配下に `git worktree add <scratchpad>/red-<slug> <RED_SHA>` で展開し、そこでプロファイル定義の RED 再現コマンドを実行して失敗を確認し、`git worktree remove` で片付ける。
  - `tdd-evaluator.md:16` の禁止列挙に「scratchpad 配下への worktree 追加・削除のみ許可。`git stash`／`checkout`／`reset` は引き続き禁止」を明記する。
- 「実装差分ゼロ検証」を厳密化する。
  - `git diff --stat <RED_SHA>^ <RED_SHA>` の変更ファイルがテストファイルのみであることを確認する形に置き換える。

### 5.3 プロファイル層の注意

- pytest の editable install は `src/` を本体作業ツリーに固定する。worktree 内でそのまま `pytest` を実行すると GREEN 済みコードが読み込まれ、RED が再現しない。
- 抽象手順（worktree で再現）は checkpoints.md に置き、具体コマンドはプロファイルに置く既存設計に従う。
- `pytest.md` の RED 再現コマンドは `PYTHONPATH=<worktree>/src` を前置し、`-p no:cacheprovider` を付ける。
- 他プロファイル（bash-hook-test・browser-manual-e2e・_template）にも「RED 再現コマンド」行を追加する。browser-manual-e2e は手動 E2E のため、RED 再現は「RED コミット時点のシナリオ手順書と実行記録の照合」で代替し、その旨を明記する。

### 5.4 代替案と却下理由

- BASE の worktree に HEAD のテストファイルだけを重ねて RED を再構成する案は、タスクが fixture や共通ヘルパを変更したときに壊れる。却下。
- 実装者の RED ログを信頼して再実行しない案は、2026-07-04 敵対レビューの核心教訓（貼付ログを信じない）に反する。却下。

### 5.5 編集対象

| ファイル | 箇所 | 変更 |
|---|---|---|
| `agents/tdd-implementer.md` | :13 直後 | コミット粒度規定（RED→GREEN→REFACTOR）を追加 |
| 同 | :37-45 | TDD Evidence 雛形に RED／GREEN SHA 欄を追加 |
| 同 | :57 | 最終メッセージのコミット列挙を RED／GREEN／REFACTOR 別に |
| `agents/tdd-evaluator.md` | :16 | worktree 例外と stash／checkout／reset 禁止を追記 |
| 同 | :47 | RED 再現手順（worktree）を追記。実装差分ゼロ検証を `git diff --stat` 形式に |
| `references/checkpoints.md` | :65（RED Critical） | 再現手順（RED コミットを隔離 worktree で再現）を追記 |
| 同 | :79（証拠） | RED SHA を証拠行に追加 |
| `SKILL.md` | :23 | progress.md 証拠行のスキーマに RED SHA を追加 |
| `templates/task-evidence-addendum.md` | :28 | RED 再現手順を worktree 方式で具体化 |
| `references/profiles/pytest.md` | コマンド節 | RED 再現コマンド（`PYTHONPATH` 前置）を追加 |
| `references/profiles/_template.md` | コマンド節 | RED 再現コマンド行を雛形に追加 |
| `references/profiles/bash-hook-test.md` | コマンド節 | RED 再現コマンド行を追加 |
| `references/profiles/browser-manual-e2e.md` | コマンド節 | RED 再現の代替（手順書照合）を明記 |

## 6. 第3節: CP-D ミューテーションの徴候ベース化（B）

### 6.1 変更内容

- CP-D Critical を「徴候が1つでもあれば必須」に改め、無条件スモークの文言を削る。徴候リストは変えない。
- CP-C と CP-D の実施条件が同一になるため、`tdd-evaluator.md:18` の「実施条件は CP によって異なる」を「CP-C／CP-D とも徴候ベース」に書き換える。
- `final-scorecard-review-prompt.md:44` の「この手順は tdd-evaluator.md と同一」という主張は、両方を同時に編集して保つ。
- scoring.md はミューテーション採点項目を持たず checkpoints.md へ委譲済みのため変更しない。

### 6.2 編集対象

| ファイル | 箇所 | 変更 |
|---|---|---|
| `references/checkpoints.md` | :86 | 「無くても代表1テストにスモーク」を削る |
| `agents/tdd-evaluator.md` | :3（description） | 「ミューテーション検証込みで」を「徴候時はミューテーション検証込みで」に |
| 同 | :18 | 実施条件の見出し文を統一 |
| 同 | :20 | CP-D の無条件スモーク文を徴候ベースに |
| `templates/final-scorecard-review-prompt.md` | :38-40 | スモーク項目を削る |
| `SKILL.md` | :33（CP-D 行） | 「ミューテーション検証必須」を「徴候時必須」に |

## 7. 第4節: review-correctness のモデル統一（E）

- `agents/review-correctness.md:5` の `model: opus` を `model: sonnet` に変更する。
- 他の review-* 4本は全て sonnet。tdd-gates 文書側に opus への言及は0件、参照元もないため連動修正はない。
- opus 指定は 2026-07-02 の一括同期コミット（`36178dc`）で導入され、理由の記録がない。

## 8. 実装ルート

- `~/.claude` は git リポジトリではない。2026-08-02 の軽量化と同じく、事前確定した編集リストを Main が直接適用する。
- 適用順: 第4節（1行）→ 第3節 → 第1節 → 第2節。依存はないが、grep 検証の単純さのために単純なものから進める。
- 適用後、`my-claude-pull` で `linux/claude/` へ同期し、`my-claude-mirrors` で `windows/claude/` へ揃える。両ミラーは現在一致しているため機械的に揃う。
- `git status`／`git diff --stat` で実体を確認したうえで `/pr-create` で PR を作る。

## 9. 検証

- grep 検証: 編集後に次の語で tdd-gates 一式と3エージェントを grep し、写し先の取り残しがないことを確認する。
  - 「フルスイート」「全体で」「全緑」「新規 failed 0」（第1節。残るのは CP-D 手順0 と implementer 雛形のみであること）
  - 「スモーク」「徴候の有無にかかわらず」「徴候なしでも」（第3節。0件であること）
  - 「opus」（第4節。`planner.md` のみであること）
- 整合検証: `tdd-evaluator` を単独起動し、本設計文書と実ファイルを敵対的に照合させる（設計文書に書いた編集が全て入っているか、書いていない変更が入っていないか）。
- 動作検証: 次に tdd-gates を使う substantial タスクで、CP-C の evaluator が worktree で RED を再現できること、CP-D 手順0 が実行されることを確認する。本設計の範囲では実施しない。

## 10. 記録すべき判断

- 「CP-C evaluator のバッチ化」は実証済み層を弱めるため却下した。再提案しない。
- 「CP-D 集約 evaluator の廃止」は実効性が測れるまで保留とした。
- 実装者のフルスイート実行は残す（信頼ベースの早期シグナルとして）。
