#!/bin/bash
# Task 完了時にコードレビュー提案
# 
# トリガー: TaskUpdate で status=completed に設定されたとき
# 動作: セキュリティレビュー、code-reviewer の適用が必要か提案

# stdin から JSON を受け取る
input=$(cat)

# status が completed かチェック
status=$(echo "$input" | jq -r '.params.status // empty' 2>/dev/null)
if [ "$status" != "completed" ]; then
    # 完了以外は何もしない
    exit 0
fi

# taskId 取得
taskId=$(echo "$input" | jq -r '.params.taskId // empty' 2>/dev/null)
if [ -z "$taskId" ]; then
    exit 0
fi

# 提案メッセージを stderr に出力（ユーザーに見える）
echo "💡 Hint: Task $taskId が完了されようとしています。" >&2
echo "  - コード変更があれば、code-reviewer または security-review を実施してから完了マークしてください" >&2
echo "  - テストが追加されていれば、テストカバレッジが 80% 以上か確認してください" >&2

exit 0
