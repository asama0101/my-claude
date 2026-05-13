#!/bin/bash
cat << 'EOF'
CONTEXT7_REQUIRED: ライブラリ・フレームワーク・SDK・API・CLIツールに関する質問では、
トレーニングデータに頼らず必ず context7 MCP ツールを使用すること:
  1. mcp__plugin_context7_context7__resolve-library-id でライブラリIDを解決
  2. mcp__plugin_context7_context7__query-docs でドキュメントを取得
対象例: React, Next.js, FastAPI, Prisma, Django, Express, Tailwind CSS, Claude API など
EOF
