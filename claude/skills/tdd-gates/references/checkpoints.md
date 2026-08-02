# チェックポイント定義（checkpoints.md）

CP-A〜F。駆動順序の正典は SKILL.md「CP対応表」（重複掲載しない）。本ファイルは各CPの目的・上乗せ先・担当・Critical・証拠要件を定義する。
採点は `scoring.md` 準拠（CP-A/B用とCP-C〜F用で出力形式が異なる）。

## 3ロール分離（自己承認の構造的排除）

土台は SDD（`subagent-driven-development`）の **implementer / task-reviewer 分離**。tdd-gates はこの分離自体を作らない——**reviewer役を差し替えるだけ**の薄いレイヤーである。

- **Planner役**（CP-A/B）= superpowers の `brainstorming`／`writing-plans` が文書を起草する。`planner` エージェントが補助してよい。
- **Generator/Implementer役**（CP-C）= SDD の implementer subagent（`implementer-prompt.md` で起動）。tdd-gates 独自の生成役は持たない（`tdd-implementer` エージェントが SDD の report 契約に合わせて実装を担う）。
- **Evaluator役**（全CP共通）= `tdd-evaluator`。SDD が標準で使う汎用 task reviewer / final code-reviewer を、CP単位で `tdd-evaluator`（または CP-D の review-*条件付き3〜5本＋集約、CP-F の doc-verifier・review-doc-readability）に差し替える。

分離原則（正典）: 実装した本人（Implementer）が採点してはならない。CP-C 以降はこれを SDD の仕組みがそのまま担保し、tdd-gates は reviewer 役の中身だけを差し替える。

---

## テスト種別の自動判定（言語プロファイル依存）

編集/対象ファイルのパスから、書くべきテスト種別を判定し、**最後にユーザーへ確認**する（誤判定防止）。
具体的なパスパターンとテストランナーは言語プロファイル（`profiles/pytest.md` 等）に定義。判定結果（unit / integration / e2e）に応じて CP-C 内の UI/UX 追加検査の要否も決まる。

---

## CP-A: 要件ギャップレビュー（旧Gate1・brainstorming に寄生）

- **目的**: 依頼＋既存コード・ドメイン・制約を分析し、要件を抽出・構造化して抜け漏れなく確定する（受入基準の言語化・テスト設計は CP-B）。
- **上乗せ先**: `superpowers:brainstorming`（SKILL.md Checklist 項目7「Spec self-review」の直後、項目8「User Review Gate」の直前）。土台は `brainstorming/spec-document-reviewer-prompt.md` への差分追記（`templates/spec-gap-review-addendum.md`、Phase2で新設）。
- **担当**: `tdd-evaluator`。brainstorming が書いた spec 文書を敵対的に検査する（この段階では実装差分が無いため自己承認リスクは無いが、採点主体を明示するため tdd-evaluator を立てる）。
- **要件網羅の敵対的検査**: 要件集合の完全性を敵対的に点検し、「抜け漏れ候補リスト（未記載の要件・暗黙要件・未対応エッジ）」を必ず出力する。
- **抜け漏れはガードレール停止（GUARDRAIL_HALT）**: 要件の真実源はユーザーにあるため、非自明な抜け漏れ候補が出たら自動FAILせず、`scoring.md`「停止シグナル」形式（`requirement_gap`）で不足項目を構造化して提示しユーザーに確認する（正規のガードレールであり都度承認待ちではない）。確認結果を要件に反映して再採点。
- **Critical**: ①コンテキスト把握が的確（既存実装・制約を踏まえている）。②要件の網羅性——抜け漏れ候補リストが提示され、非自明な欠落はユーザー確認で解消済み。③スコープが単一。
- **採点項目**: コンテキスト把握の的確さ／要件抽出・構造化／要件の網羅性（抜け漏れ・暗黙要件）／スコープの単一性。
- **証拠**: 整理済み要件リスト＋抜け漏れ候補リスト（＋ユーザー確認の結果）＋参照した既存コードの `file:line`。
- **判定**: tdd-gates独自の PASS/CONDITIONAL/FAIL（最大2回、`scoring.md`）。専用台帳は持たない——spec文書自体（brainstormingがgit commitする）とスコアカード応答が記録になる（Mainがspec文書に追記してcommitする。詳細はSKILL.md「証拠の記録先」）。

## CP-B: 計画品質レビュー（旧Gate2+3・writing-plans に寄生）

- **目的**: CP-Aで確定した要件を検証可能な受入基準・テストシナリオへ言語化し（旧Gate2）、実装着手前の既存コード・セキュリティ・分離リスクを監査する（旧Gate3）。
- **上乗せ先**: `superpowers:writing-plans`（SKILL.md「## Self-Review」の直後、「## Execution Handoff」の直前）。土台は `writing-plans/plan-document-reviewer-prompt.md` への差分追記（`templates/plan-quality-review-addendum.md`、Phase2。トレーサビリティ表・3層戦略・small/substantial判定・業務ロジック分離監査を追加）。
- **担当**: `tdd-evaluator`（既定は単独）。計画がセキュリティ敏感（認証・入力処理・機密データ）または性能敏感（大量データ・ホットパス）な場合のみ、`review-security`／`review-performance` を条件付きで並列起動する（最大2本）。
- **small route判定はここで行う**: `tdd-evaluator` が `git diff --stat` 見込みと既存テスト一覧を証拠に、次の4条件を照合する——①差分2ファイル以下 ②実装差分50行以下（テスト除く）③公開インターフェース不変 ④既存テストが変更対象範囲を被覆。1つでも外れたら substantial としてフル工程。`planner` は該当見込みを計画書に申告するのみで承認主体ではない。
- **Critical**: 受入基準↔要件↔シナリオのトレーサビリティに漏れがない（各要件に最低1受入基準・各受入基準に最低1シナリオ）／重大セキュリティ欠陥・設計破綻がない。
- **採点項目**: 受入基準の明確さ・検証可能性／シナリオ網羅（正常・異常・境界）／テスト種別の妥当性・3層割り当て／トレーサビリティ／既存構造の把握／セキュリティ観点（権限漏れ含む）／業務ロジックの分離（unitテスト可能性）／ファイルサイズ・責務分割（`review-maintainability` の基準に従う）／タスク粒度の妥当性（過剰分割・過小分割の検査、`templates/plan-quality-review-addendum.md`差分7）。
- **証拠**: 対応表（要件ID↔受入基準↔テストシナリオ↔対象ファイル↔テスト種別/層）＋レビュー所見。
- **判定**: tdd-gates独自の PASS/CONDITIONAL/FAIL（最大2回、`scoring.md`）。専用台帳は持たない——plan文書自体とスコアカード応答が記録になる（Mainがplan文書に追記してcommitする。詳細はSKILL.md「証拠の記録先」）。

### テスト3層戦略（CP-Bの層割り当て方針）

| 層 | 守るもの | 方針 |
|----|---------|------|
| unit | 業務ロジック | 業務ロジックを I/O・FW・UI から**分離**して高速・多数（分離の検査はCP-B） |
| integration | 機能品質 | **主軸**。機能の振る舞いを結合レベルで担保 |
| e2e | 品質の最後の砦 | **最小限**。重要導線のみ。むやみに増やさない |

CP-Bは各シナリオを「どの層で守るか」割り当て、E2Eは要否を明示判断して最小化する。層別の実行コマンドは言語プロファイル（`profiles/*.md`）に定義。

## CP-C: タスク証拠検証（旧Gate4-7・SDD に寄生）

- **目的**: RED（失敗するテストを先に書く）→GREEN（最小実装）→REFACTOR（振る舞い不変で整理）の各段階を、実行ログに基づいて検証する。UI/UXは条件付き。
- **上乗せ先**: `subagent-driven-development`の「### 3. Review the task」ステップ。SDDが標準ディスパッチする `task-reviewer-prompt.md` を、tdd-gates版アドオン（`templates/task-evidence-addendum.md`、Phase2）を追記したプロンプトに差し替える。`executing-plans`は独立レビュアーへのdispatchステップを持たず、実装者と評価者の分離が成立しないため対象外（サブエージェントへのアクセスが無い場合のフォールバックとして位置づけられており、その場合`tdd-evaluator`のdispatch自体が不可能）。
- **明示的な上書き（重要）**: SDDの `task-reviewer-prompt.md` にある **"Do not re-run the suite to confirm their report."**（実装者の報告を信頼し、再実行しない）は、tdd-gatesが乗る場面では**明示的に上書きする**。`tdd-evaluator` は RED/GREEN のテスト実行結果を実装者（SDD implementer）の報告のまま信用せず、**自ら再実行して確認する**。証拠不信の原則はtdd-gates最大の付加価値であり、ここが唯一 SDD の既定動作と正面から矛盾する箇所。
- **担当**: `tdd-evaluator`（SDDの通常task reviewerを差し替え）。実装作業自体はSDDのimplementer subagentがそのまま担う——tdd-gates独自の生成役は持たない。
- **RED の Critical（即FAIL）**:
  - `tdd-evaluator` が**対象テストのみ**（フルスイート不要）を自ら再実行し、テストが実際に失敗する（プロファイルの失敗ログ形式に一致）。「おそらく失敗する」は0点。
  - assertが対象の振る舞いを具体的に検証している（`assert False`/`assert True`/例外raiseだけ/トートロジー等の無条件失敗はCritical未達）。
  - evaluatorが自ら取得した `git diff` で、変更がテストファイルのみであること。
- **GREEN の Critical（即FAIL）**:
  - `tdd-evaluator` が自ら再実行し、テストが通過する（対象`passed`かつ全体でベースライン比の新規`failed`0）。
  - RED時点で固定したテストと同一で、assertを弱めていない。
  - 最小実装である（テスト非対応の実装branchを作り込んでいない）。
- **REFACTOR の Critical（即FAIL）**:
  - `tdd-evaluator`がGREEN確定コミット〜現在HEADの`git diff`を自ら取得する。**差分が空なら**GREENで確認済みの全緑結果を援用し、以下のフルスイート再実行を**省略**してよい（軽量化。`references/profiles/*.md`「CP-C証拠ルール」参照）。**差分がある場合**は以下を通常通り検証する。
  - 新機能・新しい振る舞いを追加していない。テストファイルとテスト設定ファイルが不変（skip/xfail等の実行除外追加を含め変更なし）かつ既存テストが到達しない新規branchが加わっていないことを確認する。
  - リファクタ後もプロファイル定義のテスト実行コマンドで全緑。
- **UI/UX条件付き検査**: テスト種別がe2e（ブラウザ）、または**テンプレート/ルーティング/ビュー層に変更がある場合**（unit申告でも回避不可）、`frontend-design`スキル＋敵対的クロスレビューを追加で必須化する。最大3ラウンド（確認→修正）。ブラウザ不可環境は静的解析で代替。
- **evaluatorモデル階層化（軽量化）**: `tdd-evaluator`をディスパッチするモデルは、CP-Bが確定したsmall-route判定を再利用する。small-route該当タスクは`haiku`、それ以外の全タスク（security/perf敏感タスクを含む）は現行の`sonnet`を指定する。CP-E（同じタスクループに乗る）も同じ規則に従う。新たな判定ロジックは追加しない。
- **リトライ機構**: **SDD純正の5ラウンドfix loopをそのまま使用**（独自カウンタ・独自CONDITIONALは持たない）。出力形式はSDD互換のSpec Compliance形式（`scoring.md`のCP-C〜F用）。
- **証拠**: RED失敗ログ／GREEN通過ログ（全既存テスト緑を含む）／REFACTOR後の緑ログ／（UI/UX該当時）スクショ・静的解析結果。SDDの `progress.md` に証拠行として追記する。

## CP-D: 最終スコアカード（旧Gate8・SDD Final Review に寄生）

- **目的**: 変更差分全体を多次元で採点し、マージ可否を判定する最終ゲート。
- **上乗せ先**: SDDの「## Final Review」。`requesting-code-review/code-reviewer.md`の単独ディスパッチを、review-*条件付き3〜5本並列起動＋`tdd-evaluator`集約に差し替える（`templates/final-scorecard-review-prompt.md`、Phase2）。
- **担当**: MainがCP-Bのsecurity/perf敏感フラグに基づき`review-*`を**条件付き並列起動**する——`review-correctness`／`review-test`／`review-maintainability`は常時起動、`review-security`／`review-performance`はCP-Bで該当と判定された場合のみ追加起動（計3〜5本）。`tdd-evaluator`が1枚のスコアカードに集約＋Critical判定。**各reviewerには所見をscratchpadの所見ファイルに直接書き出させ**（例`reviews/<タスクスラッグ>-cp-d-<dimension>.md`）、`tdd-evaluator`がそのファイル群を自らReadして集約採点する（review-*は所見のみ、tdd-evaluatorが点数化）。Mainは所見本文を要約・改変せず経路から外れる。
- **Critical（即FAIL）**: 仕様不適合／既存回帰／**偽装テスト検出**（assertなし・常に真・実装の写経。検出は目視に加えミューテーション検証を実施——徴候があれば必須・無くても代表1テストにスモーク）。
- **採点項目**: 起動した次元それぞれ（常時: 正確性／テスト品質／保守性。条件付き: セキュリティ／性能）。
- **リトライ機構**: **SDD純正のFinal Review**（1修正波+1 scoped re-review、adjudicate residuals）。tdd-gates独自の再評価カウンタは持たない。
- **証拠**: 集約スコアカード（review-*所見に裏付け）。Mainが`progress.md`にも書き出す（チャット報告のみで終わらせない。詳細はSKILL.md「証拠の記録先」）。

## CP-E: CI品質ゲート整備（旧Gate9・条件付き・writing-plansが末尾タスクとして追加）

- **スキップ条件**: CIを運用しないプロジェクトは、plan文書にスキップ理由を記して丸ごとスキップする。
- **上乗せ先**: `writing-plans`が条件を満たせば、計画の末尾タスクとして自動追加する（`templates/ci-gate-task-template.md`、Phase2。writing-plansの Task Structure 形式に沿う）。追加後はCP-Cと同じ仕組み（SDDの通常タスクループ）に乗る——CP-Eは「タスクの中身」を規定するだけで、独自のディスパッチ・リトライ機構は持たない。
- **内容**: プロジェクトのCIが次のステージを自動実行するよう整備・検証する。**必須ステージ（抽象・言語非依存）**: lint／typecheck／build／unit test／integration test／主要E2E。**任意**: preview環境デプロイ（web系のみ・既定off）。
- **担当**: 実装は`doc-updater`（各ステージの具体コマンドは言語プロファイル`profiles/*.md`が供給。CIプロバイダはGitHub Actionsを既定としprofileで差し替え可。ワークフロー実体は各プロジェクトに生成）。レビューはCP-Cの仕組みに乗った`tdd-evaluator`が必須ステージの被覆を採点する。
- **同期性の限界**: 「CIがグリーン」はpush後の非同期事象。本CPはCI定義の存在・被覆をゲートし、green-on-pushはマージ後のenforcement前提として記録する（エージェントループ内でgreenを待たない）。
- **Critical**: 必須ステージのいずれかがCI定義から欠落している（previewは任意なので対象外）。
- **証拠**: 生成/検証したワークフロー定義の該当行＋被覆したステージ一覧。

## CP-F: ドキュメント同期（旧Gate10・条件付き・CI整備タスクの後に追加）

- **スキップ条件**: リファクタのみ等、選択したドキュメントプロファイルの全カテゴリが非該当ならスキップ。
- **ドキュメントプロファイル確定**: プロジェクトが使うドキュメントプロファイル（既定 `references/profiles/docs-generic.md`。SSH/Telnet通信・ネットワーク機器連携・監視/アラート等のツールは `references/profiles/docs-network-tool.md`）は、CP-E同様プロジェクト側で宣言済みのものを使う（宣言場所はSKILL.md起動時チェックリスト項目1参照）。確定したプロファイルのパスは、CP-Fタスクのdoc-updater/doc-verifier/review-doc-readability起動時に必ず明記して渡す。
- **上乗せ先**: CP-Eタスクの後、`writing-plans`が同様に計画末尾へ自動追加するタスク（`templates/doc-sync-task-template.md`、Phase2）。実装タスクとしてはCP-Cと同じSDDの通常タスクループに乗るが、**レビュー役だけがCP-C/Eのtdd-evaluatorではなくdoc-verifier・review-doc-readabilityになる点が異なる**（執筆者と検証者の分離を保つため）。
- **内容**: `doc-updater`で、選択したドキュメントプロファイルの「対象カテゴリ」表（README・ガイド・API仕様は常時、セキュリティ設計書・リリースノート・（network-tool時）検証環境トポロジー・監視アラート定義書・ランブックは各カテゴリのトリガー条件に該当する場合のみ）に沿って変更に同期。AI臭い定型表現を検出・修正。各カテゴリの該当可否はdiffの根拠`file:line`で判定し、根拠を示せないカテゴリは生成しない（無条件生成の禁止）。
- **手段（執筆・検証の分離）**: `doc-updater`が執筆・更新→Mainが**別コンテキストで`doc-verifier`と`review-doc-readability`を並列起動**する（事実照合と構成・可読性判定は独立した観点のため並列化する。CLAUDE.mdの並列化原則）。`doc-verifier`は記載事実（数値・コマンド・スキーマ・挙動）をソースと照合し、`review-doc-readability`は`references/doc/writing.md`の基準（要約先出し・段落設計・箇条書き/表/図の使い分け・見出し階層）に照らして構成・可読性を判定する。不一致・要改善はいずれも`doc-updater`へ差し戻して修正させ、再検証では前回指摘を1件ずつ解消／部分解消／未解消で判定する。
- **不発明制約（委任指示の定型文）**: `doc-updater`への委任プロンプトには「ソースに根拠の無い数値・目標値・事実を発明しない。導出できる事実のみ記載し、根拠が無い項目は『未規定』と明示する」を必ず含める。`doc-verifier`には「文書に新規登場した数値・事実の裏取り（発明された値の検出）」を照合観点として指示する。
- **Critical**:
  - doc-verifierの照合で、裏付けの無い事実主張（実装に無い挙動・根拠の無い数値の記載）が未解消のまま残っている。
  - review-doc-readabilityの判定で、writing.mdの基準（要約先出し・段落設計・見出し階層等）を満たさない「要改善」が未解消のまま残っている。
  - カテゴリ選定の誤り: トリガー条件に該当するのに生成対象から漏れているカテゴリがある（欠落）、または該当しないのに生成している（過剰生成・無条件生成の混入）。判定はプロファイルのカテゴリ表とdiffの`file:line`照合による。
- **証拠**: 更新差分＋doc-verifierの照合結果（✓/不一致の表）＋review-doc-readabilityの判定結果（✓/要改善の表）＋カテゴリ選定根拠（該当/非該当の判定表とdiff `file:line`）。

---

## 文書・設計成果物の敵対レビューパターン（オプション）

要件定義書・設計文書・計画書など**文書・設計成果物**の品質を問うとき（CP-Aの要件整理レビュー・CP-Fの大規模doc整備・TDD文脈外の文書レビュー）は、次元別チェックリスト（コード用のreview-*、条件付き3〜5次元）の代わりに**命題駆動の敵対レビュー**を使ってよい。**コード差分のCP-Dはこのパターンで置き換えない**（review-*の次元別チェックリストが確立済みのため現行維持）。

- **相補的な逆方向2命題**: 「過剰の立証」と「欠落の立証」の対になる命題を立て、それぞれ独立エージェントに検察官スタンスで立証させる（例:「この文書は要件定義書を名乗る設計書である」×「要件定義書として必須の要素を欠いている」）。過剰系と欠落系で挟むと、次元分割では出ない被覆が得られる。
- **正例・負例ペアのルーブリック埋め込み**: 各命題のプロンプトに具体例で判定基準を与える（例:「flush→fsync→renameの手順は設計／書きかけが読者に見えないことは要件」）。あわせて**境界事例は安易に断ぜず理由付きで判定させ、「弁護側に譲った事例」も報告させる**（`agents/references/review.md`の過剰指摘抑制と同旨）。
- **同一レビュアーによる再判定**: 修正後の再レビューは新規エージェントでなく**同一レビュアーに（コンテキスト保持のまま）再判定を依頼**し、前回指摘の逐項目3値判定（解消／部分解消／未解消、`scoring.md`と同型）＋修正による新規混入の検査をさせる。所見の回帰テストに相当し、新規レビューより収束が速く確実。
- **規範検証と事実検証の分離並列**: 「あるべき姿か」（敵対レビュー）と「記載事実が実体と一致するか」（`doc-verifier`の照合）は検出領域が重ならないため、**別エージェントで分離し並列**に走らせる。

---

## CP順序と分岐

チェーン全体の流れの正典はSKILL.md「CP対応表」（重複掲載しない）。分岐ルール:

- CP-A/B: 各CPはPASSで次へ。CONDITIONALは同CPを再評価（最大2回、`scoring.md`）。**この再評価ループはワークフローの正規工程であり、Mainは各回のユーザー承認を待たずに自動で回す**。停止するのは再評価上限到達でFAILが確定した時のみ（構造化フォーマットは`scoring.md`「停止シグナル」）。
- CP-C〜F: SDD純正のリトライ機構（5ラウンドfix loop／Final Reviewの1修正波+1 scoped re-review）にそのまま従う。**このfix loopも例外処理でなく正規工程**であり、ラウンド上限到達で収束しない場合のみガードレール停止としてユーザーへ差し戻す。tdd-gatesは採点語彙（0–3ルーブリック・Critical即FAIL）とreviewer役の差し替えだけを提供する。
- **受け入れ確認のタイミングはSKILL.md「CP-A〜Fを1サイクルとして自動で通し、受け入れ確認は最後に一度だけ」節が正典**（CP-F完了後に一度だけ。重複掲載しない）。
