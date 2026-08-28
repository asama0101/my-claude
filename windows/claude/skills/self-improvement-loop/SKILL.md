---
name: self-improvement-loop
description: |
  セッション終了時に self-improve-trigger.sh（Stop hook）が検知したシグナル（インシデント・モデルバージョン不一致・feedback/projectメモリ更新・累積セッション数閾値到達・レビュー指摘の可能性）を受けて、~/.claude/ 配下（CLAUDE.md・skills・agents・references・hooks・settings.json）の改善要否を判定する。規模を問わず、編集前にユーザーへ差分案を提示し承認を得てから適用する。

  Stop hook が exit 2 で終了をブロックし、stderr に「self-improvement-loop スキルを起動してください」という指示とシグナル理由を出した直後に、その指示に従って起動すること。ユーザーが明示的に「自己改善ループを回して」と言った場合も起動する。
---

# self-improvement-loop

あなた（Main）は、Stop hook（`~/.claude/hooks/self-improve-trigger.sh`）が検知したシグナルを受けて、`~/.claude/` の設定を点検・改善する。**司令塔に徹し、シグナルの裏取りと実際の編集はサブエージェントに委任する**。

## 手順

1. **シグナルの裏取り**: stderr に出力されたシグナル理由（インシデント/モデル不一致/メモリ更新/累積閾値/レビュー指摘の可能性）を general-purpose サブエージェントに渡し、以下を確認させる。grep結果を鵜呑みにせず、実際にファイルを読ませて裏取りすること。
   - インシデント: `~/.claude/hooks/bash-guard.sh` 等のブロックが実際に発生したか、なぜブロックされたか、指示不足が原因ならどの記述を直すべきか
   - モデルバージョン不一致: まず `superpowers:subagent-driven-development` の Model Selection 節や `tdd-gates` の CP-C「evaluatorモデル階層化」節が示す意図的なサブエージェント多段モデル運用（implementer/evaluator役をhaiku等へ切り替える等）による一時的な差分でないかを確認する。該当すれば実害なしとして扱い、それでも解消しない場合のみ、現在のモデル世代で CLAUDE.md/skills/agents の記述が前提として古くないかを確認する
   - メモリ更新: 新規/更新された feedback・project メモリの内容と、現行の CLAUDE.md/skills/agents の記述に反映漏れがないか
   - 累積閾値到達: 直近の feedback/project メモリ群を俯瞰し、単発では気づけない繰り返しパターンがないか
   - レビュー指摘の可能性: 根本原因が CLAUDE.md/skills/agents/references の記述不足・誤りに起因するなら、どの記述を直すべきか

2. **ループガード記録の先行更新**（裏取り完了直後、承認を求めるより前に実行）: `handled_session_ids`（Tier1のループガード用の配列）に今回の `session_id` を**追記**する。**上書きしないこと**——マシン上で複数のMainセッションが同時に稼働することがあり、単一値で上書きすると他セッションの処理済み記録を消してしまい、セッション同士が互いを再ブロックし合う（実際に発生した不具合）。
   ```
   jq --arg sid "$SESSION_ID" \
     '.handled_session_ids = ((.handled_session_ids // []) - [$sid] + [$sid] | .[-20:])' \
     state.json
   ```
   （直近20件で切り詰め、同じIDの重複は除去）
   これを手順3より前に行う理由: 手順3bはユーザーの承認を待つためにターンを終える必要があるが、`handled_session_ids`の追記が手順の最後（旧設計）のままだと、承認待ちで終えたターンの直後の Stop で `self-improve-trigger.sh` が同じシグナルを再検知し exit 2 で再ブロックしてしまう（特に「レビュー指摘の可能性」シグナルは、この手順1でシグナルの裏取りをサブエージェントに依頼するprompt自体にレビュー関連キーワードが含まれるため、ほぼ毎回この再ブロックが発生する）。

   **既知の相互作用**: 起動元プロジェクトのリポジトリがmain/masterブランチ上にある場合、
   main-branch-guard.shはBashツールでの変更系コマンド（`rm`/`mv`/`cp`/`tee`/`touch`/
   `sed -i`/リダイレクト/`git commit`等）による`~/.claude`配下への書き込みも一律ブロック
   する（`$CLAUDE_HOME`はフック自身の改ざん防止のため意図的にexempt対象外）。`cd`での
   回避は同フックが`cd`を含むコマンドを一律非exempt扱いにするため無効、別コマンドでの
   `cd`もハーネスがBashコマンド後にcwdをプロジェクトルートへ自動リセットするため無効。
   回避を試みず、ユーザーに`! <コマンド>`での代理実行を依頼すること（`~/.claude`自体は
   gitリポジトリではないため、WriteやEditツールでの直接編集はこの制約の対象外）。

3. **差分案の提示と承認 → 適用**（規模を問わず事前承認必須。従来 trivial のみ承認なしで自動適用していた運用は廃止した）:
   a. 各改善項目について、編集前に差分案をユーザーへ提示する。
      - CLAUDE.md を含む変更 → `claude-md-management:claude-md-improver` スキルを起動してスコア・追加改善提案を取得し、提示に添える。追加提案は state.json の `pending_improver_suggestions` に文字列として追記する（この項目が却下されても、CLAUDE.md全体に対する独立した改善提案として残置してよい）
      - `skills/*/SKILL.md`・`agents/*.md`・`references/*.md` を含む変更 → `tdd-evaluator` を汎用スコアードレビュアーとして起動し、スコアを提示に添える
      - `hooks/*.sh`・`settings.json` を含む変更 → `review-security` を起動し、安全装置を弱める変更でないか（ブロック条件の削除・スコープ緩和・fail-open化等）を確認した所見を提示に添える。この2種は自己改善ループの安全装置そのものであり、構文チェック（e節）だけでなく意味的な安全性レビューを必ず経由させる
   b. ユーザーの承認を得る（承認が得られるまで編集しない）
   c. 承認後、編集前に対象ファイルの内容をバックアップ変数として保持する（ロールバック用）。`hooks/*.sh`・`settings.json` はこれに加え `~/.claude/state/self-improvement-backups/<ファイル名>.<epoch秒>.bak` としてファイルにも退避する（コンテキスト圧縮やセッション終了で変数保持のバックアップが失われても復元できるようにするため）
   d. `~/.claude/` の実ファイルを直接編集する
   e. 検証を実行する:
      - 対象が `skills/*/SKILL.md` または `agents/*.md`（YAMLフロントマター付き）の場合: フロントマターを抽出し、`name`・`description` キーが存在し YAML として parse できるか確認する
      - 対象が `CLAUDE.md`・`references/*.md`（プレーンMarkdown）の場合: ファイルが非空であることのみ確認する
      - 対象が `hooks/*.sh` の場合: `bash -n` で構文チェックする。加えて同名の `*.test.sh` が存在する場合は実行し、全件PASSすることを確認する（構文チェックだけでは検知できない安全装置の骨抜き化・fail-open化を回帰テストで防ぐ）
      - 対象が `settings.json` の場合: `jq .` で構文チェックする
   f. 検証NG（フロントマター破壊・ファイル空文字化・構文エラー・既存テストの失敗等）→ 直前のバックアップ（c節のファイル退避があればそれも使う）へ書き戻し、「適用したが検証で問題検出、ロールバックした」と報告してこの項目の処理を終える
   g. 検証OK → 継続

4. **state.json の残りフィールドの更新**（必ず最後に実行、jq で patch。`handled_session_ids` は手順2で追記済みのためここでは触らない）:
   - `last_reviewed_model` を今回のモデルIDへ更新
   - `session_count_since_full_audit`: 累積閾値到達シグナルで起動した場合のみ `0` にリセットし `last_full_audit_at` を現在epoch秒に更新する（Tier1が session_id ごとに1回だけ加算するため、Tier2 側での `+1` は行わない）

5. **報告**: 「適用した内容」「ロールバックした内容（あれば）」「承認が得られず見送った内容（あれば）」「claude-md-improver / tdd-evaluator / review-security の所見（該当する変更があった場合）」を簡潔にユーザーへ報告する。git操作は一切行わないことを明記する。
