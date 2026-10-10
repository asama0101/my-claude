# スキル・プラグイン マニフェスト

自作以外のスキルとプラグインの名前と入手元だけを記録する。本体は管理しない。
最終確認: 2026-10-10（`~/.claude\` を読み取って作成）

## プラグイン

導入元のマーケットプレイス `claude-plugins-official` は GitHub の `anthropics/claude-plugins-official`。

導入手順（未検証、Claude Code 上で実行）:
```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install <プラグイン名>@claude-plugins-official
```

| プラグイン | 入手元 | メモ |
|---|---|---|
| skill-creator | claude-plugins-official | |
| frontend-design | claude-plugins-official | |
| superpowers | claude-plugins-official | 6.4.1 |
| code-review | claude-plugins-official | |
| playwright | claude-plugins-official | |
| claude-md-management | claude-plugins-official | 1.0.0 |

## 手動コピーのスキル

| スキル | 配置先 | 入手元 | メモ |
|---|---|---|---|
| grilling | `~/.claude\skills\grilling` | https://github.com/mattpocock/skills/blob/main/docs/productivity/grilling.md | 実体をコピーして配置している |

## 対象外

- 自作の `roundtable`（スキル）と `guild`（プラグイン兼ローカルマーケットプレイス）は、記録しない。
- `~/.claude\skills\synced` は Claude Code が自動で管理しているため記録しない。
