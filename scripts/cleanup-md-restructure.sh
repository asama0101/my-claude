#!/usr/bin/env bash
# ~/.claude MD 統廃合・命名統一（docs/2026-07-02-md-consolidation-naming-design.md 準拠）
# 実行はユーザーが `! bash scripts/cleanup-md-restructure.sh` で行う（フック回避のため）
set -euo pipefail

C="$HOME/.claude"

# 1) agents/ リネーム（対象→役割）
mv "$C/agents/reviewer-correctness.md"     "$C/agents/correctness-reviewer.md"
mv "$C/agents/reviewer-maintainability.md" "$C/agents/maintainability-reviewer.md"
mv "$C/agents/reviewer-performance.md"     "$C/agents/performance-reviewer.md"
mv "$C/agents/reviewer-security.md"        "$C/agents/security-reviewer.md"
mv "$C/agents/reviewer-test.md"            "$C/agents/test-reviewer.md"

# 2) agents/references/ リネーム（裸名詞）
mv "$C/agents/references/api-design-patterns.md"   "$C/agents/references/api-design.md"
mv "$C/agents/references/doc-building-patterns.md" "$C/agents/references/doc-building.md"
mv "$C/agents/references/fastapi-patterns.md"      "$C/agents/references/fastapi.md"
mv "$C/agents/references/pytest-patterns.md"       "$C/agents/references/pytest.md"
mv "$C/agents/references/python-patterns.md"       "$C/agents/references/python.md"
mv "$C/agents/references/planner-examples.md"      "$C/agents/references/planner.md"
mv "$C/agents/references/review-protocol.md"       "$C/agents/references/review.md"

# 3) plans/ 掃除: mtime 2026-06-26 より古い .md を削除（06-26 以降は保持）
echo "--- plans/ 削除対象 ---"
find "$C/plans" -maxdepth 1 -name '*.md' ! -newermt 2026-06-26 -print -delete

echo "--- 完了。残存 plans: $(find "$C/plans" -maxdepth 1 -name '*.md' | wc -l) 件 ---"
