# Hooks（enforcement の正典）

| Hook | 効果 |
|------|------|
| venv-guard.sh | venv 外への `pip install`/`pip uninstall`/`uv add` 等をブロック。`VIRTUAL_ENV`環境変数ベースの文字列一致で誤検知しうるが、例外は認めない方針（誤検知時の回避経路は用意しない）。回避が必要な場合は Read で内容確認の上、判断せよ |
| branch-guard.sh | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンド（`rm`/`mv`/`cp`/`tee`/`touch`/リダイレクト/`sed -i`/`git commit`/`git rm`等）をブロック。<br>読み取り専用コマンド、および対象パスが全てプロジェクト外かつ`$CLAUDE_HOME`外の単純な rm/rmdir/unlink/mv/cp/touch/sed -i は対象外。<br>`.git`ディレクトリへの書込み権限が無い場合（ブランチ作成が実行不能な環境）は自動検知し、警告のみで許容する（`$CLAUDE_HOME`配下の`branch-guard-bypass.log`へ毎回記録=監査証跡）。<br>ローカルの当該ブランチが `origin/<branch>` の祖先で、かつ異なるコミットの場合のみ、ネットワークアクセスなしで `warn_if_stale()` が警告を追加する（`origin/<branch>` 参照が無い場合は対象外）。<br>ブロック時は `git checkout -b <branch>` でブランチを作成してから再試行せよ |

## フック以外の防御

- 破壊的コマンドや作業ディレクトリ外への書き込みは、auto モードの分類器が判定する（決定的ではない）。
- 認証情報・秘密鍵のRead/Editは、`settings.json`の`permissions.deny`が拒否する。
