# self-improvement-loop 設計

- 日付: 2026-08-17
- 対象リポジトリ: my-claude（`~/.claude/` 設定管理）

## 背景・目的

`~/.claude/` の CLAUDE.md・skills・agents・hooks・settings.json は、これまで人間が気づいた時に手動で監査・改善してきた（tdd-gates 軽量化、CP-A 発火信頼性対応、config-context-slimming 等）。この改善サイクルを、セッション終了という利用イベントを契機に自動的に回す仕組みを作る。

目的は次の3点:

1. セッション中に出た feedback・不具合の兆候を、次のセッションまで放置せず拾い上げる
2. Claude のモデルバージョンが変わったときに、CLAUDE.md 等の記述が前提としているモデル世代とのズレを検知する
3. 低リスクな修正は即座に反映し、構造に関わる変更は必ず人間の承認を経由させる

## 全体アーキテクチャ

2段ゲート構成。Tier1 は決定論的チェックのみで毎セッション終了時に実行され、Tier2（LLM駆動の実処理）は Tier1 が何かを検知した場合のみ起動する。

```
セッション終了 (Stop event)
  → [Tier1] self-improve-trigger.sh（決定論的・LLM不使用・高速）
      ├─ transcript を grep: hook block/エラー/やり直しパターン検出
      ├─ state.json の last_reviewed_model と現行モデルIDを比較
      ├─ memory/ 配下ファイルの mtime がセッション開始後か確認
      └─ session_count_since_full_audit をインクリメント、閾値N到達か判定
  → シグナルなし → 通常終了
  → シグナルあり → decision:block でスキル起動を指示（stop_hook_active で多重発火防止）
      → [Tier2] self-improvement-loop スキル（LLM駆動）
          1. サブエージェントでシグナルを裏取り（grep結果だけで断定しない）
          2. 比例ルール表（trivial/small/substantial）で分類
          3. trivial → ~/.claude/ を直接編集
          4. 構造検証を実行（ファイル種別に応じた決定論的チェック。詳細は「構造検証」節）
             ├─ 問題検出 → 直前の編集をロールバック → 結果を報告して終了
             └─ 問題なし → 継続
          5. 編集対象に CLAUDE.md が含まれる場合、追加で `claude-md-improver` を実行
             → スコア・追加改善提案を取得（ブロッキングしない参考情報。次サイクルの検討材料として state.json に積む）
          6. small/substantial → 編集せず提案のみ（brainstormingへ引き継ぎ）
          7. state.json 更新（last_reviewed_model, カウンタリセット, last_full_audit_at）
          8. ユーザーに簡潔に報告
```

## コンポーネント

| コンポーネント | 役割 |
|---|---|
| `~/.claude/hooks/self-improve-trigger.sh` | 新規 Stop hook。決定論的チェックのみ・毎セッション実行でも軽量。settings.json の `hooks.Stop` に追加登録が必要（現状 Stop hook は未登録） |
| `~/.claude/state/self-improvement.json` | `last_reviewed_model` / `session_count_since_full_audit` / `last_full_audit_at` / `pending_improver_suggestions` を保持。**環境固有state** につき `sync.sh`/`install.sh` の対象外とする（`projects/`・`sessions/`・`logs/` と同枠の除外設定が必要） |
| `~/.claude/skills/self-improvement-loop/SKILL.md` | Tier2 本体。CLAUDE.md の監査・改善提案は既存 `claude-md-management:claude-md-improver` に委譲。skills/agents/hooks/settings.json の点検ロジックは新規実装 |

## シグナル検知（Tier1、決定論的）

| シグナル | 検知方法 |
|---|---|
| インシデント（hookブロック・エラー・やり直し） | transcript（JSONL）に `"is_error":true` が出現するか grep で確認（実transcriptで実測確認済み） |
| モデルバージョン不一致 | transcript 中の `"model":"<id>"`（実測確認済み）の最終出現値と `state.json.last_reviewed_model` を文字列比較 |
| feedback/project メモリ更新 | Stop hook 入力の `cwd` をスラッシュ→ハイフン変換したスラッグから `~/.claude/projects/<slug>/memory/` を動的に算出し、配下ファイルの mtime が `state.json.last_checked_at`（Tier1が毎回更新）より新しいか確認 |
| 累積傾向（複数セッション監査） | `session_count_since_full_audit` が閾値N（初期値は実装時に決定、目安10）に到達したか |

## 分類基準（Tier2）

既存プロジェクトCLAUDE.mdの比例ルール表（trivial/small/substantial）をそのまま流用する。追加の安全策として:

- **hooks/settings.json への変更は行数によらず常に small/substantial 扱い固定**（enforcement・権限に関わるため trivial 自動適用の対象外）
- したがって trivial 自動適用が実際に触るのは CLAUDE.md・`skills/*/SKILL.md`・`agents/*.md`（すべて Markdown）のみになる
- 構造検証は合否判定（NGなら自動ロールバック）
- `claude-md-improver` は品質スコアリング（NGでもロールバックせず、次サイクルの改善材料として `state.json` に蓄積するのみ）

## 構造検証（trivial適用後の合否判定）

当初 `claude doctor` を安全網として想定したが、実機検証の結果、`claude doctor` は `settings.json` を意図的に破壊した状態でも exit 0・"No installation issues found." を返し、installation health（バージョン・自動更新状態）のみを見ていて設定ファイルの構文・整合性は検証していないことが判明した。よって以下の決定論的チェックに置き換える:

| 対象 | 検証方法 |
|---|---|
| JSON（`settings.json` / `state.json`） | `jq empty <file>` で構文検証 |
| シェルスクリプト（`hooks/*.sh`） | `bash -n <file>` で構文検証 |
| YAMLフロントマター付きMarkdown（`skills/*/SKILL.md` / `agents/*.md`） | フロントマターを抽出し YAML として parse できるか、かつ必須キー（`name`・`description`）が残っているかを検証 |
| プレーンMarkdown（`CLAUDE.md`） | 構文検証に意味がないため、非空であることのみ確認 |

hooks/settings.json は trivial 自動適用の対象外（常に提案止まり）なので、上記のうち JSON/シェルスクリプトの検証は実運用では発火しない（将来 trivial 判定基準を緩めた場合の安全網として残す）。実運用で主に効くのは YAMLフロントマター検証であり、trivial編集がSKILL.md/agents の frontmatter を壊していないかを担保する。

## 安全策まとめ

- ループは `~/.claude/` の実体ファイルを直接編集するのみ。**`git commit`/`push`/`sync.sh` は一切実行しない**。リポジトリへの反映は常にユーザーが手動で `sync.sh` を叩いたときのみ発生する
- 多重発火防止: 実装時に `stop_hook_active` フィールドが公式ドキュメントで未確認と判明したため、これに依拠しない。代わりに `state.json.last_handled_session_id`（Tier2が処理完了時に今回の `session_id` を記録）と Stop hook 入力の `session_id` を比較する自前のループガードを使う
- trivial 自動適用後に構造検証（前節）が問題を検出した場合は即座に自動ロールバックする

## テスト方針

- `self-improve-trigger.sh`: 単体で bash テスト（サンプル transcript を与えてシグナル検出/非検出を確認）
- スキル本体: 実セッションでのドライラン
  - trivial 検出 → 適用 → 構造検証 OK → 確定、の経路
  - trivial 検出 → 適用 → 構造検証 NG（frontmatter破壊等）→ ロールバック、の経路
  - substantial 検出 → 提案のみで終了、の経路
  - hooks/settings.json 変更が trivial 判定にならず常に提案止まりになることの確認

## 確認済み事項

- `scripts/sync.sh`/`scripts/install.sh` はいずれもホワイトリスト方式（`FILE_TARGETS`/`DIR_TARGETS`・`FILE_ITEMS`/`DIR_ITEMS`）で、明示的に列挙した項目しか対象にしない。`~/.claude/state/` はこのリストに含めない限り自動的に対象外になるため、除外のための追加実装は不要
- `~/.claude/hooks/self-improve-trigger.sh` と `~/.claude/skills/self-improvement-loop/` は、既存の `hooks`/`skills` ディレクトリ配下に置けば sync.sh/install.sh の対象に自動的に含まれる（追加設定不要）
- `claude doctor` は設定ファイルの構文・整合性を検証しないことを実機確認済み（「構造検証」節参照）

## 未決事項（実装計画で詰める）

- 閾値N（累積傾向監査の周期）の初期値と調整方法
- transcript からのインシデント検出パターン（grep 対象文字列）の具体的な列挙
