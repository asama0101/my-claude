# ~/.claude MD ファイル統廃合・命名統一 設計書

日付: 2026-07-02
状態: 承認済み（実装前）

## 背景と目的

`~/.claude/` 配下の MD ファイルが多く感じられるため統廃合し、残るファイルの命名に統一性を持たせる。調査（Explore による全 30 ファイルのインベントリ: 参照関係・内容重複・命名パターン）の結果、以下が判明した。

- 「多すぎる」の実体は `plans/` の堆積（79 件・792KB・2026-06-02〜07-02）
- agents/skills 本体 23 ファイルは全て参照経路が生存し、内容重複は単一ソース規約による明示委譲で排除済み。**削除・マージ候補はゼロ**
- 命名の揺れは 3 箇所: agents/ の語順混在（`reviewer-correctness` のみ役割→対象、他は対象→役割）、`agents/references/` のサフィックス 3 種混在、2 つの references/ ディレクトリ間の規則不一致

## 決定事項

### 1. 統廃合（削除）

| 対象 | 処置 |
|------|------|
| `~/.claude/plans/` 79 件 | mtime 2026-06-26 以降を残し、それ以前の約 50 件を削除 |
| agents/skills 本体 23 件 | 削除・マージなし（上記調査結果による） |
| `~/.claude/cache/changelog.md` | 対象外（Claude Code 製品の自動生成キャッシュ） |

### 2. 命名規約とリネーム（計 12 本）

**agents/ の規約**: `<対象・領域>-<役割>`。対象が特定されない汎用役割は裸名可（例: `planner`）。

| 旧名 | 新名 |
|------|------|
| reviewer-correctness.md | correctness-reviewer.md |
| reviewer-maintainability.md | maintainability-reviewer.md |
| reviewer-performance.md | performance-reviewer.md |
| reviewer-security.md | security-reviewer.md |
| reviewer-test.md | test-reviewer.md |

変更なし: planner / python-dev / doc-updater / trivial-executor / gate-generator / gate-evaluator（既に規約適合）。

**references/ の規約**: 裸名詞（主題名のみ）。ディレクトリ名 references/ が種別を示すためサフィックスは付けない。内容種別（作法集・記入例・共通手順）は冒頭の自己申告コメントで表す（既存慣習）。`_template.md` の `_` 接頭は「実体でなく雛形」を示す慣習として例外維持。

| 旧名（agents/references/） | 新名 |
|------|------|
| api-design-patterns.md | api-design.md |
| doc-building-patterns.md | doc-building.md |
| fastapi-patterns.md | fastapi.md |
| pytest-patterns.md | pytest.md |
| python-patterns.md | python.md |
| planner-examples.md | planner.md |
| review-protocol.md | review.md |

`skills/tdd-gates/references/`（gates.md・scoring.md・profiles/pytest.md・profiles/_template.md）は既に裸名詞規則に適合しており変更なし。

既知のトレードオフ: `references/planner.md` が `agents/planner.md` と同一ベース名になるが、ディレクトリで区別され参照は常にパス付きのため実害は小さい。

### 3. 参照の追随更新

リネームの参照漏れは「エージェントの参照切れ」として静かに壊れるため、網羅更新と検証を必須とする。

更新対象（旧名を参照するファイル）:

- `~/.claude/CLAUDE.md`（エージェント表・レビュー単独ルートの `reviewer-*` 表記 → `*-reviewer`）
- `skills/tdd-gates/references/gates.md`（reviewer 構成の正典）
- `skills/tdd-gates/SKILL.md`
- reviewer 5 本の冒頭（review-protocol.md への参照 → review.md）
- `agents/python-dev.md`（references/ 4 ファイルへの委譲パス）
- `agents/gate-generator.md`・`skills/tdd-gates/references/profiles/pytest.md`（pytest-patterns 参照）
- `agents/planner.md`（planner-examples 参照）
- `agents/doc-updater.md`（doc-building-patterns 参照）
- `agents/references/fastapi.md` ↔ `api-design.md` ↔ `python.md` の相互参照
- メモリファイル（`reviewer-*` 等の旧名に言及するもの）

検証: 実装後に旧名 12 個の全文 grep（`~/.claude` の md/sh/json とメモリ）で残存ゼロを確認。

### 4. 命名規約の記録先

`~/.claude/CLAUDE.md` には追記しない（2026-07 棚卸の単一ソース規約に従い肥大化を避ける）。メモリ `project-claude-config-inventory` に命名規約 2 行（agents: 対象→役割、references: 裸名詞）を追記する。

### 5. 実行上の制約と手順

- `~/.claude/agents/` はサブエージェントの編集がフックでブロックされるため、リネームと参照更新は **Main が直接実施**（内容が事前確定した機械的編集の例外ルート）
- `~/.claude` 配下への `mv`/`rm` はフック（bash-guard / workspace-guard）にブロックされるため、手順は「新名で Write → 参照を Edit → 旧ファイル削除リストをプロジェクト配下のスクリプトへ書き出し → ユーザーが `! bash` で実行」
- plans/ の削除も同じスクリプトに含め、削除系の実行依頼を 1 回にまとめる
- 完了後 `scripts/sync.sh` で `claude/` ミラーへ同期（auto commit+push のため実行前に余計な差分がないか確認する）。rsync の削除挙動により旧名ファイルがミラーに残らないことを確認する

## スコープ外

- リポジトリ側 `docs/`・`.superpowers/sdd/` の整理（対象は `~/.claude/` と明示指定されたため）
- api-design ↔ fastapi の接触面（HTTP ステータス/エラーレスポンス）は現状重複が薄く統合不要。今後の加筆で重複しやすい「要監視ペア」としてのみ記録
