# tdd-gates CP-D 常時起動本数の削減設計

## 背景・動機

ユーザーから「tdd-gatesはsuperpowers単体で十分ではないか」という疑問が提起され、本セッションで実証的な点検を行った。

1. **過去セッション履歴の監査**（`~/.claude/projects/`配下、tdd-evaluator実行242件を横断調査）: CP-A（要件ギャップレビュー）とCP-C（タスク証拠検証）は、superpowers標準（SDDの「実装者報告を信頼しフルスイート再実行しない」方針・セルフレビューのみ）では構造的に見逃すはずの欠陥を複数プロジェクト・複数回にわたって実際に検出していた（例: RED証拠の偽装〔実際はcollection ERRORで本物のFAILEDでない〕、循環アサーション〔テスト対象コードで再計算した値をそのまま期待値にし何も検証していない〕、計画書内の自己矛盾）。CP-A/Cは儀式ではなく機能している。
2. **CP-Dの実効性は今回の監査時間内では個別に裏取りできなかった**。次元別reviewer（correctness/test/maintainability常時＋security/performance条件付き、計3〜5本）が単独reviewerでは拾えない欠陥を検出した明確な実例は確認できなかった（判断材料不足であり、無効と断定する根拠でもない）。
3. **連携機構の精査**では、tdd-gatesがsuperpowers標準（SDDのround管理・Final Review出力形式・TDD Iron Law）を壊している箇所は見つからなかった。唯一の意図的上書き（CP-CがSDD標準の「再実行しない」方針を上書きする）は自己文書化済みで、事故的な破壊ではない。

以上を踏まえ、実証済みのCP-A/Cは現状維持し、判断材料が薄いCP-Dのみ、まず本数を削減してコストを下げ、実運用で様子を見る方針とする。

## スコープ

- **対象**: CP-Dの常時起動reviewer本数（`checkpoints.md` CP-D節、`SKILL.md` CP対応表、`final-scorecard-review-prompt.md`、`tdd-evaluator.md`）。
- **対象外**:
  - CP-A/C: 実証済みのため変更しない。
  - CP-B/E/F: 今回の監査で深掘りできておらず、判断材料が無いため据え置く（別途監査するかは本設計のスコープ外）。
  - CP-Dの集約ロジック・Critical判定基準（偽装テスト検出・ミューテーション検証義務）: 変更しない。起動本数のみを変更する。
  - CP-Dの条件付きreviewer（security/performance）の判定ロジック自体（CP-Bのフラグを再利用する既存の仕組み）: 変更しない。

## 変更: CP-D常時起動を3本→2本に削減し、maintainabilityを条件付き化

### 現状（`checkpoints.md:85`）

常時起動: `review-correctness`／`review-test`／`review-maintainability`（3本）
条件付き: `review-security`／`review-performance`（CP-Bのsecurity/perf敏感フラグに応じて追加、最大2本）
→ 計3〜5本

### 変更後

常時起動: `review-correctness`／`review-test`（2本）
条件付き: `review-maintainability`／`review-security`／`review-performance`（最大3本）
→ 計2〜5本

**maintainabilityの新規トリガー条件**: 「構造変更を伴う場合のみ（新規ファイル/ディレクトリの追加、責務分割の変更、命名体系の変更等）」。既存のsecurity/perf敏感判定（CP-Bで既に行っている）と同じ定性判定パターンに合わせる。行数等のマジックナンバーは使わない。判定はCP-Bで既存のsecurity/perf判定と同じタイミング（計画段階）で`tdd-evaluator`が行い、既存の2フラグに「構造変更フラグ」を1つ追加する形とする。

### 根拠

今回実証されたCP-A/Cの効果は、いずれも「テストの正当性」「実装の正確性」に直結する欠陥クラス（偽装RED証拠、循環アサーション）だった。correctness/testの2本はこれと直接対応する。maintainability（命名・構造・DRY）は、常時走らせる根拠となる実証データが今回得られなかったため、既存のsecurity/perfと同列の条件付き扱いに揃える。

### 効果

構造変更を伴わない差分（既存ファイル内でのロジック修正等、多くの小〜中粒度タスクが該当）では、CP-Dが2本で完結しコストが下がる。構造変更を伴う差分では従来通りmaintainabilityが起動され、観点の欠落は生じない。

### 影響ファイル

- `checkpoints.md`（CP-D「担当」行を「常時2本＋条件付き最大3本」に修正）
- `SKILL.md`（CP対応表のCP-D「担当」列を修正）
- `final-scorecard-review-prompt.md`（起動本数の可変範囲を2〜5本に修正し、maintainabilityの新規トリガー条件を明記）
- `tdd-evaluator.md`（「所見の充足チェック」節: 既定本数を「CP-D=CP-Bのフラグに基づく3〜5本」から「CP-D=CP-Bのフラグに基づく2〜5本（maintainability/security/performanceが条件付き）」に修正）
- `plan-quality-review-addendum.md`（CP-Bのsecurity/perf判定に「構造変更フラグ」の判定を追加する差分。既存の差分番号に続けて新設）

## 検証方針

本設計はトークン数・所要時間を自動計測する仕組みを持たない。成功の判定基準は定性的なものとする。

- 構造変更を伴わないタスクのCP-D起動本数が2本になっていること（実運用のディスパッチ例で確認）。
- 構造変更を伴うタスクではmaintainabilityが従来通り起動されていること。
- 既存のCritical即FAIL・証拠不信の原則（偽装テスト検出・ミューテーション検証義務）が一切緩んでいないこと。
- 数セッション運用した後、CP-Dのmaintainability非起動によって見逃された欠陥が無いか（他のCPやユーザー報告で顕在化していないか）を改めて確認する。顕在化した場合は常時起動に戻す。

## 実装上の注意（次工程への申し送り）

変更対象ファイルは`~/.claude/skills/tdd-gates/`および`~/.claude/agents/tdd-evaluator.md`の実体であり、`my-claude/claude/`はミラーのため直接編集しない（`scripts/sync.sh`で上書きされる）。実装後は`scripts/sync.sh`で本リポジトリへ同期する。

本変更はMarkdown指示文書の編集のみであり、コード・テストは存在しない。次工程（`writing-plans`）では、`doc-updater`による構成整合を伴う編集としての実装計画を検討すること。
