# Hooks（enforcement の正典）

| Hook | 効果 |
|------|------|
| bash-guard.sh | 破壊的コマンドをブロック。`rm`/`rmdir`/`unlink`/`git rm`・`find -delete`・`rsync --delete`・`chmod 000`/`chmod -R 777`・機密ファイル（`.env`/`.ssh`/鍵等）の`cat`/`less`/`head`等での読取は、プロジェクト配下／`$CLAUDE_HOME`配下／`/tmp`配下の子要素のみ許可（各ゾーンのルート自体は不可）。<br>`shutil.rmtree`、および`python`/`perl`等のワンライナー経由（`-c`/`-e`）での機密ファイル読取は無条件ブロック。<br>jq 不在時 fail-close。ブロック時は `! <コマンド>` 形式で依頼せよ |
| workspace-guard.sh | プロジェクト配下／`~/.claude` 配下／`/tmp` 配下以外への Write/Edit をブロック。<br>`~/.claude/hooks/` とハーネス設定（settings.json）は許可（実行前確認は settings.json の `permissions.ask` 側で担保）。<br>Bash の `/var/tmp` リダイレクト・プロジェクト外宛先の cp/tee/mv も保守的にブロック。誤検知時は Read で回避せよ |
| venv-guard.sh | venv 外への `pip install` 等をブロック。文字列一致で誤検知しうる。回避は Read |
| main-branch-guard.sh | main/master ブランチ上での Write/Edit/MultiEdit/NotebookEdit、および Bash の削除・変更系コマンド（`rm`/`mv`/`cp`/`tee`/`touch`/リダイレクト/`sed -i`/`git commit`/`git rm` 等）をブロック。<br>読み取り専用コマンド、および対象パスが全てプロジェクト外かつ`$CLAUDE_HOME`外の単純な rm/rmdir/unlink/mv/cp/touch/sed -i は対象外。<br>ローカルの当該ブランチが `origin/<branch>` の祖先で、かつ異なるコミットの場合のみ、ネットワークアクセスなしで `warn_if_stale()` が警告を追加する（`origin/<branch>` 参照が無い場合は対象外）。<br>ブロック時は `git checkout -b <branch>` でブランチを作成してから再試行せよ |
| self-improve-trigger.sh | Stop hook。transcriptの`is_error:true`出現・モデル世代不一致等をTier1として粗く検知し exit 2 でブロック、`self-improvement-loop`スキル起動を促す。<br>粗い検知のため誤検知あり: `is_error:true`は原因を区別せず安全ガードの正常ブロックも一律検知対象。モデル不一致はSDD/tdd-gatesの意図的なサブエージェント多段モデル運用（transcript内の最後の`model`フィールドを拾うため）でも発生しうる。裏取りはTier2（`self-improvement-loop`スキル）が担う |
