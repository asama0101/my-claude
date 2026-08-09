# グローバルCLAUDE.md・自作skills・agentsのコンテキスト圧縮設計

## 背景・動機

ユーザーから「CLAUDE.md・skills・agents・referencesの記載を、遵守すべきルールのみに最小限化してコンテキスト汚染を極小化したい」という依頼があった。

当初は全成果物に「ルール文だけ残す」という単一基準を適用する想定だったが、Anthropic公式ドキュメント（Claude Code best practices、Agent Skills overview）を調査した結果、成果物の種別によってロードされるタイミングが異なり、適用すべき圧縮基準も異なることが判明した。

- **CLAUDE.md**: 毎セッション必ずロードされる。公式ガイダンスは「この行を消したらClaudeがミスするか？しないなら消せ」という基準を明示しており、「ルールのみに削る」という当初の依頼と合致する。
- **skills（SKILL.md本文）**: progressive disclosure設計が前提。frontmatter（name/description）だけが常時ロードされ、本文はスキル発火時のみロード（目安5000トークン未満）、`references/`配下は実際に参照した時だけロードされコストはほぼゼロ。本文の役割は公式に「procedural knowledge: workflows, best practices, and guidance」と定義されており、手順を「ルール文だけ」に削るとスキルとして機能しなくなる。
- **agents**: サブエージェント起動時に本文全体がそのコンテキストにロードされる点でskillsのLevel 2と同じ構造。

この事実誤認（一律「ルールのみ」を適用すると機能を壊す）をユーザーに提示し、成果物種別ごとに異なる基準を適用する方針の承認を得た。

## スコープ

### 対象

| 種別 | パス | 件数 |
|---|---|---|
| CLAUDE.md | `~/.claude/CLAUDE.md`（グローバルのみ） | 1 |
| skills | `~/.claude/skills/{tdd-gates,codemap,html-template-import}/SKILL.md` | 3 |
| agents | `~/.claude/agents/*.md` | 13 |

### 対象外

- プロジェクトCLAUDE.md（本リポジトリの`./CLAUDE.md`等）。
- pluginが提供するskills（superpowers/context7/frontend-design等）。バージョン管理・所有者が自分ではないため。
- `references/`配下（skills/agentsが参照する詳細資料）。参照時のみロードでコストが実質ゼロのため圧縮対象としない。ただし本文からの参照リンクが壊れないことは監査時に確認する。

## 監査基準（成果物種別ごと）

### CLAUDE.md

「この行を消したらClaudeがミスするか？」で判定する。以下を削除候補とする。

- Claudeがコードやfrontmatterから推論できる自明な事項。
- 発生頻度が低くCLAUDE.mdでなくskill化すべき知識（該当skillが既に存在する場合はCLAUDE.md側の重複記述を削り、skillへの言及のみ残す）。
- 実質的な強制力がなくフックで代替可能なリマインダー文（既存の削減基準を踏襲）。

### skills本文／agents本文

「この記述はスキル発火／エージェント起動の**都度**必要か？」で判定する。

- 都度必要な手順・制約・チェックリストは本文に残す（削らない）。
- 背景説明・非自明だが稀にしか要らない詳細情報・長い例示は`references/`へ外出しし、本文には参照リンク（例: `詳細は references/xxx.md を参照`）だけを残す。
- 既に`references/`が存在するagents（doc-updater等）は、その外出し粒度を基準に他のagentsへ一貫性を揃える。

## 実行方式

1. **監査フェーズ**: skills 3件・agents 13件を対象に、読み取り専用サブエージェント（Explore）を並列起動する。各エージェントは対象ファイルと既存`references/`を読み、上記基準に沿って「削除候補（CLAUDE.mdの場合）」または「references外出し候補（外出し先ファイルと、本文に残す参照文の文面）」を、具体的な行範囲付きで返す。CLAUDE.mdは1件のみのためMain自身が同一プロセスで監査する。
2. **レビューフェーズ**: Mainが全監査結果を集約し、過剰な圧縮（手順の欠落・スキルのdescriptionトリガー精度の低下・行動規範の意図しない弱体化）がないか確認する。判断に迷う削減候補はユーザーに提示し保留する。
3. **適用フェーズ**: 承認された差分を`~/.claude/`側に直接Edit適用する（`my-claude/claude/`はミラーのため直接編集しない）。
4. **同期フェーズ**: 全カテゴリの適用が完了した後、まとめて1回ユーザーに`scripts/sync.sh`（commit+push自動）の実行可否を確認する。Mainが自律的に実行することはない。

## 検証方針

本変更はMarkdown指示文書の編集のみであり、自動テストは存在しない。成功の判定基準は定性的なものとする。

- 各skill/agentのfrontmatter（description等）が変更されておらず、既存のトリガー条件が壊れていないこと。
- 本文から外出しした内容が`references/`に実在し、本文からのリンクが正しいパスを指していること。
- CLAUDE.mdから削除した行について、「skillへの委譲で代替されている」または「フックで代替されている」または「Claudeが推論可能」のいずれかの理由が監査結果に明記されていること。
- 適用後、本リポジトリの`docs/`や既存メモリ（`project-claude-config-inventory.md`・`project-agents-restructure.md`・`project-tdd-gates-harness.md`）が定めている正典箇所（reviewer本数・enforcement表・命名規約等）と矛盾が生じていないこと。

## 実装上の注意（次工程への申し送り）

- 変更対象ファイルの実体は`~/.claude/`配下であり、`my-claude/claude/`は同期後にのみ更新される（Gotchas準拠）。
- 本変更はコード・テストを含まないMarkdown指示文書の編集であり、TDD規律ではなくドキュメント整合性の観点で計画すべきである。次工程（`writing-plans`）では、16件の監査を並列サブエージェントで実施し、その結果をMainが集約・適用する構成として計画すること。
- agentsのうち`doc-updater`等は既に`references/`分割済みのため、監査対象ではあるが外出しの余地は小さい可能性が高い（過去のproject memoryに記録された既存の再編作業と重複しないよう、監査エージェントには既存の分割方針を事前情報として与えること）。
