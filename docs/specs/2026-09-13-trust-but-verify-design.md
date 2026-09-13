# trust-but-verify プラグイン設計

最終更新: 2026-09-13

## 背景

`tdd-gates`という名前が実態と乖離している。実際には次の4役割を持つが、名前は「TDD限定」を連想させる。

- 設計文書の敵対的監査（旧CP-A）
- 実装計画の粒度監査（旧CP-B）
- 実装証拠の再検証（旧CP-C）
- 集約レビュー（旧CP-D）

一連のブレインストーミングで、名称・構造・各チェックポイントの要否を見直した。本文書はその結論を仕様として固定する。

## 目的

superpowers標準チェーン（`brainstorming`→`writing-plans`→`subagent-driven-development`→`finishing-a-development-branch`）に、自己承認を防ぐ独立検証を差し込むオーケストレーターを、`trust-but-verify`という名前のプラグインとして再構成する。

## スコープ

- 対象: 現行`~/.claude/skills/tdd-gates/`を`~/.claude/skills/trust-but-verify/`へ改名・再構成する。
- 対象: CP-A/B/C/Dを個別スキルに分割する。
- 対象外: superpowers本体・`tdd-evaluator`/`tdd-implementer`/`review-*`エージェントの実装は変更しない（参照のみ）。
- 対象外: CI整備タスク・文書同期タスク（旧CP-E/F）の実装は変更しない。

## 設計

### ディレクトリ構造

```
~/.claude/skills/trust-but-verify/
├── .claude-plugin/plugin.json
├── SKILL.md                          # オーケストレーター
├── skills/
│   ├── design-audit/SKILL.md         # 旧CP-A
│   ├── plan-audit/SKILL.md           # 旧CP-B
│   ├── evidence-check/SKILL.md       # 旧CP-C
│   └── review-aggregate/SKILL.md     # 旧CP-D
├── references/
│   ├── scoring.md
│   └── profiles/*.md
└── templates/
    ├── ci-gate-task-template.md      # 旧CP-E、テンプレートのまま維持
    └── doc-sync-task-template.md     # 旧CP-F、テンプレートのまま維持
```

### 各スキルの役割と変更点

| スキル | 旧名 | 変更内容 |
|---|---|---|
| `design-audit` | CP-A | 監査基準に「決定ツリーを一問一答で詰め、各分岐に推奨回答を示したか」を追加。それ以外は現行のまま維持（実効性監査で効果実証済み） |
| `plan-audit` | CP-B | 内容は変更なし。実効性の実証記録がCP-Aほど無いため、将来の運用実績を見て要否を再判断する対象として注記する |
| `evidence-check` | CP-C | 変更なし。実装者の申告を信じず`tdd-evaluator`が自ら再実行する中核機構を維持する |
| `review-aggregate` | CP-D | `review-maintainability`の判定基準をponytailのラダー式（既存流用→stdlib→ネイティブ→既存依存→一行→最小実装の降順チェック）に差し替える。プロファイル階層・独自モデル階層化ルールを削除し、`subagent-driven-development`本体のModel Selection節に一本化する |

### CI整備・文書同期タスク（旧CP-E/F）

`writing-plans`が条件付きで計画末尾に追加するタスクテンプレートであり、独立チェックポイントではない。`evidence-check`と同じSDDタスクループに乗るため、個別スキル化は不要。現状の`templates/ci-gate-task-template.md`・`templates/doc-sync-task-template.md`をそのまま`trust-but-verify/templates/`へ移設する。

### オーケストレーターの責務

`SKILL.md`（プラグイン直下）が以下を担う。

- Mainがsubstantial規模のタスクで本スキルを起動する。
- `brainstorming`→`design-audit`→`writing-plans`→`plan-audit`→`subagent-driven-development`（`evidence-check`を各タスクのレビュー役として自動組込）→`review-aggregate`→`finishing-a-development-branch`の順に指示する。
- `evidence-check`は必ずSDDのタスクレビュー段階に自動組込で使う。単体で呼び出し可能なスキルとしても存在するが、それは「レビュー単独」経路（`review-aggregate`の専門レビュアー群だけを単発利用する場合）向けであり、`evidence-check`自体を単体運用の起点にはしない。

## 移行対応

- `~/.claude/skills/tdd-gates/`の内容を`~/.claude/skills/trust-but-verify/`へ改名・再構成する。
- `~/.claude/agents/tdd-evaluator.md`・`tdd-implementer.md`・`review-*.md`は変更しない（汎用エージェントのため参照のみ）。
- `~/.claude/CLAUDE.md`のルーティング表・reference記載にある`tdd-gates`という名称を`trust-but-verify`に更新する。
- memory（`project-tdd-gates-harness.md`等）の名称反映は本タスクのスコープ外とし、別途対応する。
- `my-claude-pull`によるミラー同期は追加対応不要（`~/.claude/skills/`配下のため既存の同期対象に含まれる）。

## 次のステップ

`writing-plans`スキルで実装計画を作成する。
