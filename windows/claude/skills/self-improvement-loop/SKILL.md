---
name: self-improvement-loop
description: |
  セッション終了時に self-improve-trigger.sh（Stop hook）が検知したシグナル（インシデント・モデルバージョン不一致・feedback/projectメモリ更新・累積セッション数閾値到達）を受けて、~/.claude/ 配下（CLAUDE.md・skills・agents・hooks・settings.json）の改善要否を判定し、低リスクな修正は自動適用、構造変更は提案に留める。

  Stop hook が exit 2 で終了をブロックし、stderr に「self-improvement-loop スキルを起動してください」という指示とシグナル理由を出した直後に、その指示に従って起動すること。ユーザーが明示的に「自己改善ループを回して」と言った場合も起動する。
---

# self-improvement-loop

あなた（Main）は、Stop hook（`~/.claude/hooks/self-improve-trigger.sh`）が検知したシグナルを受けて、`~/.claude/` の設定を点検・改善する。**司令塔に徹し、シグナルの裏取りと実際の編集はサブエージェントに委任する**。

## 手順

1. **シグナルの裏取り**: stderr に出力されたシグナル理由（インシデント/モデル不一致/メモリ更新/累積閾値）を general-purpose サブエージェントに渡し、以下を確認させる。grep結果を鵜呑みにせず、実際にファイルを読ませて裏取りすること。
   - インシデント: `~/.claude/hooks/bash-guard.sh` 等のブロックが実際に発生したか、なぜブロックされたか、指示不足が原因ならどの記述を直すべきか
   - モデルバージョン不一致: まず `superpowers:subagent-driven-development` の Model Selection 節や `tdd-gates` の CP-C「evaluatorモデル階層化」節が示す意図的なサブエージェント多段モデル運用（implementer/evaluator役をhaiku等へ切り替える等）による一時的な差分でないかを確認する。該当すれば実害なしとして扱い、それでも解消しない場合のみ、現在のモデル世代で CLAUDE.md/skills/agents の記述が前提として古くないかを確認する
   - メモリ更新: 新規/更新された feedback・project メモリの内容と、現行の CLAUDE.md/skills/agents の記述に反映漏れがないか
   - 累積閾値到達: 直近の feedback/project メモリ群を俯瞰し、単発では気づけない繰り返しパターンがないか

2. **分類**: 見つかった各改善項目を、プロジェクトCLAUDE.mdの比例ルール表（trivial/small/substantial）で分類する。**`hooks/*.sh` または `settings.json` に関わる変更は、行数によらず常に small/substantial 扱いに固定する**（trivial 自動適用の対象外）。

3. **trivial 項目の適用**（CLAUDE.md / `skills/*/SKILL.md` / `agents/*.md` の記述修正のみが対象）:
   a. 編集前に対象ファイルの内容をバックアップ変数として保持する（ロールバック用）
   b. `~/.claude/` の実ファイルを直接編集する
   c. 構造検証を実行する:
      - 対象が `skills/*/SKILL.md` または `agents/*.md`（YAMLフロントマター付き）の場合: フロントマターを抽出し、`name`・`description` キーが存在し YAML として parse できるか確認する
      - 対象が `CLAUDE.md`（プレーンMarkdown）の場合: ファイルが非空であることのみ確認する
   d. 検証NG（フロントマター破壊・ファイル空文字化等）→ 直前のバックアップ内容へ書き戻し、「適用したが構造検証で問題検出、ロールバックした」と報告してこの項目の処理を終える
   e. 検証OK → 継続
   f. 編集対象に CLAUDE.md が含まれる場合、`claude-md-management:claude-md-improver` スキルを起動してスコア・追加改善提案を取得する（ブロッキングしない。追加提案は state.json の `pending_improver_suggestions` に文字列として追記する）

4. **small/substantial 項目**: 編集しない。チャットで簡潔に提案を提示し、ユーザーが望めば `superpowers:brainstorming` へ引き継ぐ旨を伝える。

5. **state.json の更新**（必ず最後に実行、jq で patch）:
   - `last_reviewed_model` を今回のモデルIDへ更新
   - `session_count_since_full_audit`: 累積閾値到達シグナルで起動した場合のみ `0` にリセットし `last_full_audit_at` を現在epoch秒に更新する（Tier1が session_id ごとに1回だけ加算するため、Tier2 側での `+1` は行わない）
   - `handled_session_ids`（Tier1のループガード用の配列）に今回の `session_id` を**追記**する。**上書きしないこと**——マシン上で複数のMainセッションが同時に稼働することがあり、単一値で上書きすると他セッションの処理済み記録を消してしまい、セッション同士が互いを再ブロックし合う（実際に発生した不具合）。
     ```
     jq --arg sid "$SESSION_ID" \
       '.handled_session_ids = ((.handled_session_ids // []) - [$sid] + [$sid] | .[-20:])' \
       state.json
     ```
     （直近20件で切り詰め、同じIDの重複は除去）

6. **報告**: 「適用した内容」「ロールバックした内容（あれば）」「提案のみに留めた内容（あれば）」「claude-md-improver のスコア（CLAUDE.mdを触った場合）」を簡潔にユーザーへ報告する。git操作は一切行わないことを明記する。
