# SPEC: README 更新の誘導 Hook

## 概要

- 目的: README.md があるプロジェクトで、関連する変更をしたときに、Claude が README の更新要否を確認し、必要なら更新するよう確実に誘導する。
- 背景: 公式ドキュメント（memory.md）は、CLAUDE.md を「context, not enforced configuration」とし、必ず実行させたい処理は Hook に書くよう案内している。
- 方針: `Stop` hook（command 型）で検知して block し、更新要否の意味判断は Claude 本体に任せる。`user\CLAUDE.md` にも1行の指示を置いて、事前の自発的な誘導とする。

## 流れ

1. `PostToolUse`（matcher: `Edit|Write`）の command hook が、編集したファイルのパスをセッションごとの一時ファイルに記録する。
2. `Stop` の command hook が、記録を読む。
   - プロジェクトに `README.md` がなければ何もしない。
   - `stop_hook_active` が true なら何もしない（1回だけ block する）。
   - 記録に「対象のソース／設定ファイルの編集」があり、その後に README の編集がなければ、`decision: "block"` と `reason` を返す。
   - `reason` の内容: README の更新要否を確認し、必要なら更新する。不要なら、その理由を述べてから終了する。
   - block したら、記録のうち対象ファイルの分をクリアする（次の応答で、新しい編集がない限り再度 block しない）。
3. `user\CLAUDE.md` に「README.md がある場合、関連する変更をしたら README の更新要否を確認する」旨を1行追加する。

## 決定ログ

- ゴール: 「必要な場合は README を必ず更新させる」（Q1: B）。
- Hook の種類: command 型で検知＋block の `reason` で Claude 自身に要否を申告させる（Q4: C）。agent 型は experimental のため使わない。
- 変更の検知: PostToolUse の記録のみ。Git には依存しない（Q9: A）。Git の状態を使うと、未コミット変更のあるリポジトリで毎回 block される誤検知が出るため。
- 対象ファイル: ドキュメント（`*.md` など）、テスト、ロックファイル等を除いた、ソース／設定ファイル（Q6: B）。除外パターンは実装時に確定する。
- 無限ブロックの防止: `stop_hook_active` が true なら通す。1回だけ block する（Q7: A）。
- 配置: Hook ＋ `user\CLAUDE.md` に1行（Q8: A）。
- 制約（Q3: A〜D）: `user\` を編集して `sync.ps1` で反映する。秘密情報を含めない。スキル・プラグインは追加しない。着手前に SPEC の承認を得る。
- 障壁（Q2: A〜D）: 更新要否の判定の曖昧さ、無限ブロック、Windows でのスクリプト実行（`py` 経由）、全プロジェクトへの影響。

## 受入条件

1. README.md があるプロジェクトで、対象ファイルを編集して README を編集せずに応答を終えようとすると、1回だけ block され、`reason` が Claude に渡る。
2. block 後、Claude が README を更新するか、更新不要の理由を述べれば、そのまま終了できる。
3. README を編集した後に対象ファイルを編集していない場合は、block されない。
4. README.md がないプロジェクトでは、block されない。
5. `*.md` やロックファイルだけの編集では、block されない。
6. `stop_hook_active` が true のとき、block されない（無限ループにならない）。
7. `user\settings.json` とスクリプトが `sync.ps1` で `~\.claude\` に反映され、`py` 経由で Windows 上で動く。
8. Hook とスクリプトに、秘密情報を含まない。

## 非目標

- README の内容の自動生成・自動更新（更新自体は Claude が行う）。
- 更新要否の意味判断を Hook 側で行うこと（agent 型・prompt 型は使わない）。
- Bash 経由（`sed`、リダイレクト等）の変更の検知。
- Git の状態を使った検知。
- README 以外のドキュメント（CHANGELOG、docs\ など）への拡張。
- スキル・プラグインの追加。

## リスク

- 検知の漏れ: Bash 経由の変更を拾えない。
- 誤検知: 除外パターンが不十分だと、軽微な変更でも block される。block は1回だけなので、影響は小さい。
- 全プロジェクトに影響する: ユーザレベルの settings.json に書くため、すべてのプロジェクトで動く。README の有無で早期に抜けるようにする。
- 公式ドキュメントで未確認の点: 連続続行の上限（8 回との記述）、`stop_hook_active` の原文。実装前に hooks.md の原文で確認する。
- 一時ファイルの管理: セッションごとの記録ファイルの置き場所と後始末を、実装時に決める。
- Windows でのコマンド記法: `py {{HOME}}/.claude/...` 形式が hooks の `command` で動くかを、実装時に検証する。
