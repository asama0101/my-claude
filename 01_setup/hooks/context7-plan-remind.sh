#!/bin/bash
# context7-plan-remind.sh
# writing-plans スキル実行前に context7 確認を促す（PreToolUse: Skill）

SKILL=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('skill',''))" 2>/dev/null)

if [[ "$SKILL" == *"writing-plans"* ]]; then
    echo "📋 writing-plans を実行します"
    echo ""
    echo "⚠️  CONTEXT7 確認チェック:"
    echo "   実装で使うライブラリ（polars・psycopg2・TimescaleDB 等）の API を"
    echo "   resolve-library-id → query-docs の順で確認しましたか？"
    echo "   トレーニングデータで推定した API をプランに書かないでください。"
fi

exit 0
