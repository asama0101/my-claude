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
          4. `claude doctor` を実行
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
| インシデント（hookブロック・エラー・やり直し） | Stop hook が受け取る transcript_path を grep し、bash-guard/main-branch-guard 等のブロックメッセージパターンやツールエラーを検出 |
| モデルバージョン不一致 | `state.json.last_reviewed_model` と現セッションのモデルIDを文字列比較 |
| feedback/project メモリ更新 | `~/.claude/projects/-home-asama-my-claude/memory/` 配下ファイルの mtime がセッション開始時刻より新しいか確認 |
| 累積傾向（複数セッション監査） | `session_count_since_full_audit` が閾値N（初期値は実装時に決定、目安10）に到達したか |

## 分類基準（Tier2）

既存プロジェクトCLAUDE.mdの比例ルール表（trivial/small/substantial）をそのまま流用する。追加の安全策として:

- **hooks/settings.json への変更は行数によらず常に small/substantial 扱い固定**（enforcement・権限に関わるため trivial 自動適用の対象外）
- `claude doctor` は合否判定（NGなら自動ロールバック）
- `claude-md-improver` は品質スコアリング（NGでもロールバックせず、次サイクルの改善材料として `state.json` に蓄積するのみ）

## 安全策まとめ

- ループは `~/.claude/` の実体ファイルを直接編集するのみ。**`git commit`/`push`/`sync.sh` は一切実行しない**。リポジトリへの反映は常にユーザーが手動で `sync.sh` を叩いたときのみ発生する
- 多重発火防止は Claude Code の `stop_hook_active` フラグに依拠する
- trivial 自動適用後に `claude doctor` が問題を検出した場合は即座に自動ロールバックする

## テスト方針

- `self-improve-trigger.sh`: 単体で bash テスト（サンプル transcript を与えてシグナル検出/非検出を確認）
- スキル本体: 実セッションでのドライラン
  - trivial 検出 → 適用 → doctor OK → 確定、の経路
  - trivial 検出 → 適用 → doctor NG → ロールバック、の経路
  - substantial 検出 → 提案のみで終了、の経路
  - hooks/settings.json 変更が trivial 判定にならず常に提案止まりになることの確認

## 未決事項（実装計画で詰める）

- 閾値N（累積傾向監査の周期）の初期値と調整方法
- `state.json` を `sync.sh`/`install.sh` の除外リストへ具体的にどう追加するか（既存の `projects/`・`sessions/` 除外実装を参照）
- transcript からのインシデント検出パターン（grep 対象文字列）の具体的な列挙
- `claude doctor` の呼び出し形態（CLIコマンドとして呼べるか、hook/skill内からの実行方法）
