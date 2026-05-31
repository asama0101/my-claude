---
name: session-close-improve
description: |
  セッション終了時の改善ワークフロー。実装・作業セッションを締め括る際に使う。サブエージェント使用を振り返り、必要最小限の更新のみ実施し、メモリを保存する。
  
  以下のような発言で起動すること:「終了します」「振り返りをしたい」「セッションを終える前に」「学びをまとめたい」「session ending」「wrap up」「このセッションの改善をしたい」「CLAUDE.mdを更新したい」「今回の学びを反映させたい」

  実装後・大きな機能追加後・長い作業セッションの終わりに積極的に起動する。
---

# セッション終了改善フロー

3ステップで完了する軽量ワークフロー。**過剰な更新は行わない**。

---

## Step 1: 振り返り（サブエージェント中心）

**主軸: サブエージェント使用の徹底チェック**

以下の必須エージェントが、必要な場面で使われたか:

| エージェント | 必須場面 | 使用できたか |
|------------|---------|-----------|
| tdd-guide | 新機能・バグ修正 | ✅ / ❌ |
| reviewer-*（run-reviewers スキル） | コード変更後 | ✅ / ❌ |
| python-dev | Python/FastAPI 実装 | ✅ / ❌ |
| api-designer | API 設計 | ✅ / ❌ |

追加チェック:
- 汎用 `claude` エージェントで代替した場面はなかったか
- 独立したタスクを並列起動できた場面を逐次実行していないか

**副軸: Skills の適切な使用**
- `brainstorming` → `writing-plans` → `subagent-driven-development` のフローが守られたか
- 省略されがちなステップ（spec 作成・タスクごとレビュー）が守られたか

### Step 1 → Step 2 への引継ぎ

❌ 項目を列挙:

```
【Step 2 への引継ぎ】
- ❌ <省略されたエージェント/スキル>: <根本原因> → <対策候補>
```

❌ がなければ Step 2 をスキップして Step 3 へ（ただし **Step 1.5 は ❌ の有無に関わらず必ず実施**する）。

---

## Step 1.5: superpowers spec/plan の完了確認とアーカイブ

superpowers の spec（brainstorming）/ plan（writing-plans）が「終わったのか」を後から確認できるよう、成果物ファイルベースで完了状態を可視化し、完全完了したものを `done/` へアーカイブする。

1. **対象の有無を確認**: cwd の `docs/superpowers/specs/` と `docs/superpowers/plans/` を確認。どちらも無ければ本ステップをスキップ（`done/` 配下のファイルは集計対象外）。

2. **状態を判定して一覧表示**:
   - **spec**: ファイルが存在すれば ✅（spec フェーズ完了）。
   - **plan**: チェックボックスを集計して実装進捗を出す。
     ```bash
     done=$(grep -cE '^[[:space:]]*- \[x\]' <plan.md>); todo=$(grep -cE '^[[:space:]]*- \[ \]' <plan.md>)
     # todo==0 かつ done>0 → ✅完全完了 / todo>0 → 🔄進行中 done/(done+todo) / done==0 → 未着手
     ```

   表示フォーマット:
   ```
   === superpowers spec/plan 状態 ===
   spec フェーズ : ✅ docs/superpowers/specs/2026-05-25-foo-design.md
   plan フェーズ : ✅ docs/superpowers/plans/2026-05-25-foo.md  実装 8/8 → done/ へ移動可
   plan フェーズ : 🔄 docs/superpowers/plans/2026-05-20-bar.md  実装 3/8（進行中・据え置き）
   =================================
   ```

3. **完了分のアーカイブ（承認必須）**: plan が 100%（todo==0 かつ done>0）のものを「アーカイブ候補」として提示し、**ユーザー承認を得てから** `git mv` で移動する:
   ```bash
   mkdir -p docs/superpowers/plans/done
   git mv docs/superpowers/plans/<file>.md docs/superpowers/plans/done/
   ```
   - 対応する spec も完了とみなせる場合は、対応関係（日付/トピックが異なりうるため自動マッチしない）を**ユーザーに確認**のうえ `mkdir -p docs/superpowers/specs/done && git mv` で移動する。
   - **非破壊原則**: 移動前に必ず承認を得る。未完了（チェックボックス未消化）のファイルは絶対に動かさない。

active フォルダ＝進行中、`done/`＝完了済み、という状態が後から一目で分かるようになる。

---

## Step 2: 最小更新

Step 1 の ❌ 項目について、**以下の3条件を全て満たすものだけ** 更新する:

```
① このセッションで実際に問題が起きた
② 解決策が明確（1行以内で言える）
③ 次回セッションでも再現する可能性が高い
```

1条件でも満たさなければ → Step 3 のメモリに気づきとして残すだけ。

### 更新の種類と閾値

| 種類 | 実施する条件 |
|------|------------|
| CLAUDE.md 修正 | 古い情報・誤記・フェーズ変化のみ。新規追記は3条件を全て満たす場合のみ |
| Hook 新規作成 | 「自動でなければ確実に忘れる」構造的問題のみ |
| Skill 新規作成 | 「複数セッションで繰り返す複雑なワークフロー」のみ |

### 実装時の注意

`~/.claude/CLAUDE.md` は Edit ツールが **HARD BLOCK** される → Python/Bash で編集すること:

```bash
python3 -c "
import os
p = os.path.expanduser('~/.claude/CLAUDE.md')
with open(p, 'r') as f:
    content = f.read()
# 変更処理
with open(p, 'w') as f:
    f.write(content)
"
```

Hook を追加した場合は `settings.json` への登録と CLAUDE.md 「アクティブなHooks」テーブルへの記載も必須。

ユーザーに変更案を提示し、承認を得てから実装する（テーブル形式）:

| # | 種類 | 箇所/名前 | 解決する問題 | 3条件充足 |
|---|------|---------|------------|---------|
| 1 | CLAUDE.md修正 | アクティブなHooks | 古い記述の修正 | ①②③ |

---

## Step 3: クローズ

### メモリ保存

次回セッションのために保存が必要な状態変化があれば記録（最小限に）:

保存先: `~/.claude/projects/<project-sanitized-path>/memory/`

- プロジェクトのフェーズ変化・次のステップ
- 次セッションで注意すべき非自明な制約

### CLAUDE.md 軽量確認

Step 2 で変更した場合のみ、目視で確認:
- 追加した記述が既存内容と重複していないか
- 古い情報を誤って残していないか

`claude-md-improver` 呼び出しは任意（大きな変更をした場合のみ推奨）。

---

## 終了宣言前チェックリスト

- [ ] Step 1: サブエージェント評価完了・❌ 項目を Step 2 に引き継いだ（またはなし）
- [ ] Step 1.5: spec/plan 完了確認・完了分を承認のうえ done/ へ移動（または該当なし）
- [ ] Step 2: 3条件を満たすものだけ更新した（またはスキップ）
- [ ] Step 3: メモリ保存完了・CLAUDE.md 確認済み
