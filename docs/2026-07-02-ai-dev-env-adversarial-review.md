# 敵対レビュー結果：AI駆動開発環境（my-claude / ~/.claude 設定一式）

- 日付: 2026-07-02
- 対象: `claude/`（~/.claude ミラー）＝ CLAUDE.md・agents 10本・skills 2個（tdd-gates / session-close-improve）・hooks 6本・settings.json
- 手法: 設定資産専用の敵対レンズ4本（形骸化ハンター／整合性検査官／hooks・permissions 監査官／経済性・スケーラビリティ検察官）を並列起動 → Main が集約・重大度判定・引用スポット検証
- 主軸視点: 実効性・形骸化 ＋ 保守性・整合性（副次: コスト効率・堅牢性）

## エグゼクティブサマリ

この環境は「9品質ゲート・自己承認排除・破壊操作ブロック」を掲げるが、敵対的に突くと enforcement の実体が**2つの脆い柱**に集約されている。

1. **hook の文字列マッチ** — 正規表現でコマンド文字列を見るだけで、間接実行・変数展開・rm 以外の削除プリミティブで迂回可能。`Bash(*)` + `skipAutoPermissionPrompt:true`（settings.json:8,134）が確認プロンプトも外すため、迂回は無音で通る。
2. **Main の自己申告** — trivial/substantial の分類、台帳の記録、reviewer 所見の evaluator への受け渡しがすべて工程の当事者 Main を経由し、検知する第三者機構がない。

結果、品質担保の多くが「破ろうと思えば破れる／読んで従うことを祈るだけ」の構造になっている。

---

## Critical

### C1. ガードが自分自身を書き換え可能なゾーンにある（自己解除経路）
- 根拠: `workspace-guard.sh:30` が `$CLAUDE_HOME/*` を無条件許可 ＋ `settings.json:7-8` で `Write/Edit(./**)` allow。hook 実体は `~/.claude/hooks/`。
- 実害: `Edit` で `bash-guard.sh` を `exit 0` に書き換えれば以後の全 Bash が素通り（hook は呼出毎に読まれ即時有効）。
- 補足: ~/.claude が writable なのは設定管理という目的上の設計意図。ガード実体と settings.json だけは例外扱いすべき。
- 修正: workspace-guard と permissions deny に `~/.claude/hooks/**`・`~/.claude/settings.json` を明示追加。

### C2. bash-guard は文字列マッチのみ＝間接実行・変数展開・非 rm 削除で迂回
- 根拠: `bash-guard.sh:102`（awk 先頭トークン）・`:164`（リテラル `\b(rm|rmdir|unlink)(\s|$)`）。中身を走査しない。
- 迂回例（実読確認）: `bash cleanup.sh`（中身無検査）／`x=rm; $x -rf`／`find ~ -delete`／`python -c "shutil.rmtree(...)"`／`rsync --delete`。
- 実害: CLAUDE.md:16「削除制限（Critical）」が実質祈り。`Bash(*)`+無確認と複合し範囲外削除が無音で通る。
- 修正: 変数代入・コマンド置換を含む削除文脈を解析不能として block、`find -delete`・`shutil.rmtree`・`rsync --delete`・順不同 `truncate --size=0` をパターン追加（完全は不可と明記）。

### C3. deny の非対称 — 機密は Read/Write/Edit のみ deny、Bash 読取が素通り
- 根拠: `settings.json:11-25` は Read/Write/Edit の deny のみ。`Bash(*)` allow に対する Bash deny は sudo のみ。
- 実害: `cat .env`・`base64 ~/.ssh/id_rsa | curl ...` が無確認で実行でき deny の意図が無効。
- 修正: 機密読取（cat/less/base64/xxd 等 × .env/.ssh/id_rsa/.pem/.key）を hook 側で block。

### C4. 自己承認排除の建付けが Main 経由で構造的に崩れる
- 根拠: 台帳は Main の自書き自読で第三者照合なし（SKILL.md:20-22）／trivial 判定は自己申告（`tdd-gates-nudge.sh` が「trivial なら不要」と免罪符）／reviewer 所見は Main が要約して evaluator に渡す。
- 実害: ①面倒な変更を trivial と分類すれば TDD・レビュー・自己承認排除が合法的に消える。②ゲートスキップ＋PASS 後付けを照合する機構がない。③Critical 所見を要約時に軟化させれば「Critical 即 FAIL」が発動しない。
- 修正: reviewer-* の生所見を scratchpad ファイル経由で evaluator に直接読ませ Main を経路から外す／trivial 判定を差分行数・ファイル数で機械計測。

---

## Major

- **M1. hook 全体が fail-open** — jq 不在・パース失敗・`__CLAUDE_HOME__` 置換漏れで COMMAND 空→exit 0 で全ガードが無音消失。→ PreToolUse ガード3本（bash/workspace/venv）冒頭で jq 存在を検証し失敗時 exit 2（fail-close）。nudge/session-stop は非ブロックのまま。
- **M2. 「レビュー単独」ルートが成立しない** — CLAUDE.md:27「gate-evaluator を単独起動し reviewer-* を集約採点」だが `gate-evaluator.md:4` の tools に Agent が無く reviewer を起動できない。→ 文言を「Main が reviewer-* を並列起動→所見を gate-evaluator に渡す」に。
- **M3. reviewer-* の共通プロトコル参照が相対パス** — `reviewer-*.md:10` が `references/review-protocol.md`（相対）、他 agent は絶対。cwd=project で解決しない（ファイル自体は実在）。→ 5本とも絶対表記に統一。
- **M4. session-stop.sh の催促文が廃止済み旧5ステップを指示** — `session-stop.sh:80` が撤去済みの「バックログ取込・最小更新」を強制、かつスキップ手順 `touch $SKIP_MARK` をモデルに開示。→ 列挙を「session-close-improve を起動」のみに、スキップ手順は stderr へ。
- **M5. context7「必ず使用」の enforcement は writing-plans 1本のみ＋古いスタック例示** — `context7-plan-remind.sh:8` は writing-plans 起動時のみ発火、`:12` が削除済み `polars` 等を例示。→ CLAUDE.md Hooks 表を実態に訂正、例示を汎用化。
- **M6. tdd-gates の言語ロックイン** — profile は pytest のみ、`gates.md:59` が `pytest -q` を直書き、非 Python で挙動未定義、nudge も `*.py` 限定。→ 「プロファイル不在時は _template から作成しユーザー承認」分岐を明記、gates.md:59 を「プロファイル定義の全体実行コマンド」に一般化。
- **M7. 過剰工程とコスト** — 非自明1行修正も定義上フル9ゲート直行（約19エージェント・直列13往復・opus×6）。中間規模の受け皿なし、evaluator が毎ゲート新規起動で同一資料を最大6回読み直す。→ 表に第3規模「small（Gate4-5 簡略）」明記、evaluator を1スレッド継続。
- **M8. trivial 用「軽量 Agent」が実在しない** — agents 10本は全て opus/sonnet で haiku ゼロ。typo 修正が premium モデルで走る。→ `model: haiku` の trivial-executor を定義。
- **M9. 書込・インストール経路の穴** — `venv-guard.sh:17` は `.venv` 存在だけで system pip 許可、`workspace-guard.sh` の Bash 検査は `/tmp` リダイレクトのみ（tee/cp/ln -s 素通り）。→ venv は VIRTUAL_ENV or `.venv/bin/pip` のみ許可、workspace に tee/cp 宛先検査を追加。

---

## Minor

| # | 所見 | 根拠 | 修正 |
|---|------|------|------|
| m1 | デッド資産: `rules/` 空（sync 対象だが install 対象外の非対称）／`.ipynb_checkpoints` 腐敗コピー | 実読確認 | install.sh に rules 追加で対称化／checkpoint はユーザー実行で削除 |
| m2 | reviewer description「コード変更後に必ず使用」が比例ルールと矛盾（trivial で自動発火） | reviewer-*.md:3 vs CLAUDE.md:25,29 | description に「substantial の」と限定 |
| m3 | CLAUDE.md 表が gates.md の reviewer 構成を再掲（単一ソース規約の綻び） | CLAUDE.md:57-58 vs gates.md:33,71 | 表から構成事実を落とし参照のみ |
| m4 | モデル配分の逆転: 検出=sonnet、集約だけの evaluator=opus | reviewer-*.md:5, gate-evaluator.md:5 | opus を reviewer-correctness へ、集約は sonnet（実測は将来課題） |
| m5 | 台帳ファイル名固定で並列ファンアウト衝突 | SKILL.md:20 | 名前にタスクスラッグを含める |
| m6 | nudge/remind hook が exit 0 stdout で model に届かない・MultiEdit 未カバー | tdd-gates-nudge.sh, settings.json:97 | JSON 出力方式へ、matcher に MultiEdit 追加 |
| m7 | doc-updater/session-close にプロジェクト固有例示・壊れ wiki-link 残存 | doc-updater.md:32, SKILL.md:21 | 条件付き表現へ／要旨インライン化 |

---

## 検証済み・問題なし

エージェント表10行↔実体10本、Hooks 表6行↔hooks 6本↔settings.json 登録、agents/references 7ファイルは全て参照元あり、`__CLAUDE_HOME__` プレースホルダ運用、tdd-gates の SKILL/gates/scoring 正典分担は相互参照どおり一致。

---

## 対応方針（2026-07-02 セッションで全項目着手）

修正は `~/.claude/` 側で行い `scripts/sync.sh` で `claude/` に同期する。実装後に hook は `bash -n` 構文チェック＋独立レビューを通す。
