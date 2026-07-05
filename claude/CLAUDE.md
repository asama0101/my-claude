# CLAUDE.md - AI Development Guidelines

## 基本理念 (**Critical**)

- **シンプル第一**: 変更は最小限に。複雑さを避ける。
- **根本解決**: 対症療法ではなく、バグの真因を叩く。
- **影響の最小化**: 既存の正常なロジックを壊さない。
- **エレガントさ**: 「もっとスマートな解決策はないか」と自問する。ただし過剰設計は避ける。
- **コンテキスト衛生**: Main は司令塔に徹し、計画・指示・承認・進捗管理だけを担う。ファイルの読み込み・調査・実装・テスト・レビューは、サブエージェントや Explore に任せる。サブエージェントには結論・決定・`file:line`・短い差分だけを返させ、ファイル全文や長いログは受け取らない。Main が自分でファイルを読むのは、委任の指示を書くのに必要な最小限だけにする。処理速度よりも、Main のコンテキストを汚さないことを優先する。

## 禁止事項 (**Critical**)

- **非破壊**: README・既存ドキュメントの生成/変更は、ユーザーに確認してから行う。
- **テスト保護**: テストコードを確認なしに削除・コメントアウトしない。
- **無断リファクタリング禁止**: 動作中コードの書き換えは、ユーザーに確認してから行う。
- **削除制限**: `rm`/`rmdir`/`unlink` はプロジェクト配下の子要素のみ。範囲外は削除方法を提示し、ユーザーの実行を待つ（enforcement は bash-guard.sh、下表）。
- **作業範囲の限定**: 新規作成・編集・一時ファイルはプロジェクト配下のみ。例外はハーネス管理パス（plan `~/.claude/plans/`・メモリ `~/.claude/projects/.../memory/`）と `~/.claude/` の設定管理作業（enforcement は workspace-guard.sh、下表）。

## 作業ルーティング（比例ルール）

まず変更の規模で進め方を分ける。**迷ったら substantial 扱い**にする（安全側に倒す）。規模によって変わるのは「サブエージェントに委任するかどうか」ではなく、**工程の深さ（どこまで手厚くやるか）**である。

| 規模 | 定義 | 工程 |
|------|------|------|
| trivial | 数行・既存パターン踏襲でテスト不要。設定/ドキュメント/コメント/明白な誤記の修正 | 単一の軽量 Agent（`trivial-executor`＝haiku）に一括委任（Main は Read/Edit せず要約のみ受け取る）。Plan モード・planner・reviewer 群は省略可 |
| substantial | 新規ロジック・複数ファイル横断・公開インターフェース変更・非自明なバグ修正 | Plan モード → `tdd-gates` スキル（9品質ゲート）でフル工程。採点は実装者と別コンテキストで行い自己承認を排除 |
| small | 差分 ≤2ファイル・実装差分 ≤50行（テスト除く）・公開インターフェース不変・既存テストが対象範囲を被覆、を**すべて**満たす（1つでも外れたら substantial） | `tdd-gates` の Gate4–5(RED→GREEN) 中心の簡略パイプ（承認手順はスキル「段階導入の限界」が正典。tdd-evaluator が Gate1 で判定） |
| レビュー単独 | フル工程は不要だがコードレビューだけ独立して欲しい（小〜中規模・既存コード点検・PR 前チェック） | Main が `review-*` を並列起動 → `tdd-evaluator` が集約採点（実装者と別コンテキストで自己承認を排除。evaluator は reviewer を自分で起動しない） |

- 本ドキュメントの「必ず/必須」（Plan モード・reviewer・TDD）はすべて **substantial 前提**。
- 例外（Main 直接可）: 内容が事前確定した exact-edit・探索を伴わない機械的編集。

## タスク実行手順

1. **着手前にユーザー承認を得る（trivial 含む）**: substantial は Plan モードで計画を立案して承認を得る（計画は Main が組み、調査は Explore に委任）。trivial も方針を一言提示してから委任する。
2. 遂行中は進捗を随時マークし、各ステップで高レベルなサマリーを提供する。
3. **実装後（trivial 含む全変更）**: ユーザーの受け入れ確認 → OK なら関連ドキュメント（README・ガイド・`docs/CODEMAPS/*`・仕様書等）の更新を `doc-updater` に委任。NG なら修正に戻り、ドキュメントは更新しない。更新対象が無ければ何もしない。

## コミュニケーション

- **言語**: 応答は日本語（コード・変数名・シンボルは英語）。
- **Stop & Ask**: 不明点・曖昧な仕様は推測で進めず、必ず止めて質問する。
- **再計画**: 詰まったら無理に進めず、即座に立ち止まって再計画を提案する。
- **設計の徹底詰め（grill・substantial 限定）**: Plan／brainstorming の質問フェーズで設計を relentless に詰める。
  1. 決定ツリーを依存順に降りる（上流の判断を確定してから下流を問う）
  2. 質問は一度に1問
  3. 各質問に推奨回答を添えて提示する
  4. コードで答えられる問いはユーザーに聞かず Explore で事実を確定し、真に曖昧な点だけ質問する
- **並列実行**: 並列は「互いに独立した作業」でのみ効果がある。対象は3つ——① 複数の Explore で同時に調べる、② 複数の review-* で同時にレビューし tdd-evaluator が結果をまとめる、③ 依存関係のない複数ファイル/タスクを同時に実装する（`dispatching-parallel-agents`／`subagent-driven-development`）。一方、設計→実装→テストのように前工程の結果を次工程が使う「直列依存」は、並列にしても速くならない。並列に渡す各エージェントは前後の文脈を持たない（cold start）ため、タスクの分け方と渡す情報は Plan モードで設計し、plan ファイルに書き込んでから起動する。

## 利用可能なエージェント（~/.claude/agents/）

| Agent | Purpose | 使用タイミング |
|-------|---------|--------------|
| planner | 実装計画の素材づくり（ステップ分解・依存関係・順序）＋設計判断・トレードオフ・ADR | 複雑な機能・リファクタリング着手前、設計判断・スケーラビリティ検討時。planner は素材を作り、最終計画は Main が組む |
| tdd-generator | TDD Generator（RED→GREEN→REFACTOR・実行ログを証拠に） | 新機能・バグ修正時、`tdd-gates` から段階起動。汎用 Agent で代替しない |
| tdd-evaluator | TDD Evaluator（review-* を集約採点・Critical 即 FAIL） | `tdd-gates` の採点全般（Gate1–8。Gate8=差し戻し判定）。レビュー単独時は単独起動（作業ルーティング表参照） |
| review-correctness / review-performance / review-security / review-maintainability | 1次元ずつのレビュー（正確性／性能／セキュリティ／保守性・doc 整合） | substantial のコード変更後（ゲート別の構成・本数は gates.md が正典） |
| review-test | テスト品質・要件適合レビュー（カバレッジ・仕様適合・冪等性） | 同上（適用ゲートは gates.md が正典） |
| dev-python | Python 実装（スタイル・設計パターン・イディオム） | Python コードを書くとき（FastAPI/REST 設計は `references/` 参照） |
| trivial-executor | trivial 変更の軽量実行（haiku）。設定/ドキュメント/コメント/誤記/機械的編集 | 比例ルールの trivial ルートで一括委任（substantial と気づいたら止めて差し戻す） |
| doc-updater | ドキュメント・コードマップ更新 | 受け入れ OK 後のドキュメント同期・README/ガイド/コードマップ更新時 |

ゲートごとの reviewer 構成・本数の正典は `~/.claude/skills/tdd-gates/references/gates.md`。

## スキル

- **tdd-gates**（ローカル）: TDD×9品質ゲートを統括するスキル。substantial 実装で使用。
- プラグイン（superpowers / context7 / frontend-design 等）は `enabledPlugins` で有効化済み。
- **context7 は必ず使用**: ライブラリ・SDK・API の質問時。`resolve-library-id` → `query-docs` の順。
- **frontend-design は必ず使用**: UI・Web ページ・HTML 成果物（レポート/構成図等）・スライド等の資料をデザイン・生成・変更するとき（スキルの description は Web アプリ寄りで資料系に自動発火しないため、ここで明示）。
- **HTML 成果物**: 提出前に独立サブエージェントで敵対的クロスレビュー→修正→再レビューを通す（ブラウザ不可環境では `node --check`＋JS ロジック追跡等の静的解析で代替）。

## アクティブな Hooks

| Hook | 効果 |
|------|------|
| bash-guard.sh | 破壊的コマンドをブロック。`rm`/`rmdir`/`unlink` はプロジェクト配下の子要素のみ許可（配下外・ルート自体・解析不能・変数難読化はブロック）。`find -delete`・`shutil.rmtree`・`rsync --delete` 等の非 rm 削除、機密ファイル（`.env`/`.ssh`/鍵）の読取・持ち出しもブロック。jq 不在時は fail-close。代表パターンのみで網羅ではない。ブロック時はユーザーへ `! <コマンド>` 形式で依頼 |
| workspace-guard.sh | プロジェクト配下／`~/.claude` 配下以外への Write/Edit をブロック（`exit 2`）。ただし `~/.claude/hooks/` とハーネス設定（settings.json）は `~/.claude` 配下でも自己書換防止でブロック。Bash は `/tmp` リダイレクトと cp/tee/mv のプロジェクト外宛先を保守的にブロック。jq 不在時は fail-close。誤検知時は Read ツールで回避 |
| tdd-gates-nudge.sh | `tests/` 外の Python 実装ファイル編集時に `tdd-gates` 使用を非ブロッキングで促す（言語追加は profile 用意後に拡張） |
| venv-guard.sh | venv 外への `pip install` 等をブロック。コマンド文字列に含まれるだけで誤検知する場合あり（回避は Read ツール） |
| context7-plan-remind.sh | `writing-plans` スキル実行前（PreToolUse→Skill）に限り context7 確認を促す（通常のライブラリ質問では発火しない。「context7 必ず使用」自体はモデルの規律で担保する） |
