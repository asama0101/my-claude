---
paths:
  - "**/*_test.go"
  - "**/*.go"
---
# Go テスト

## フレームワーク

標準 `testing` パッケージ + **testify** を使用する。

## 最低テストカバレッジ: 80%

テスト種別（すべて必須）:
1. **ユニットテスト** — 個々の関数、ユーティリティ
2. **統合テスト** — HTTP ハンドラー、データベース操作
3. **E2Eテスト** — 重要なユーザーフロー

## テスト駆動開発

必須ワークフロー:
1. まずテストを書く（RED）
2. テストを実行 — 失敗するはず
3. 最小限の実装を書く（GREEN）
4. テストを実行 — 成功するはず
5. リファクタリング（IMPROVE）
6. カバレッジを確認（80%以上）

## カバレッジ

```bash
go test -cover ./...
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## テーブル駆動テスト（Go の標準パターン）

Go では**テーブル駆動テスト**が慣用的:

```go
func TestAdd(t *testing.T) {
    t.Parallel()

    tests := []struct {
        name string
        a, b int
        want int
    }{
        {"positive numbers", 2, 3, 5},
        {"zero", 0, 5, 5},
        {"negative", -1, 1, 0},
    }

    for _, tt := range tests {
        tt := tt // ループ変数のキャプチャ
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got := Add(tt.a, tt.b)
            assert.Equal(t, tt.want, got)
        })
    }
}
```

## テスト命名

`TestFunctionName_Scenario` 形式:

```go
func TestGetUser_ReturnsUser_WhenIDExists(t *testing.T) {...}
func TestGetUser_ReturnsError_WhenIDNotFound(t *testing.T) {...}
func TestCreateUser_ReturnsValidationError_WhenEmailMissing(t *testing.T) {...}
```

## テストの独立性（必須）

すべてのテストは **独立していなければならない**:

```go
// Good: t.Cleanup でクリーンアップ
func TestWithDB(t *testing.T) {
    db := setupTestDB(t)
    t.Cleanup(func() { db.Close() })

    // テスト実行...
}

// Good: defer でクリーンアップ
func TestWithFile(t *testing.T) {
    f, err := os.CreateTemp("", "test-*")
    require.NoError(t, err)
    defer os.Remove(f.Name())

    // テスト実行...
}
```

**禁止事項:**
- テスト間で状態を共有する（グローバル変数への書き込みなど）
- テスト後のクリーンアップを省略する
- DB テストでロールバック/削除なしにコミットしたままにする

## testify の使い方

```go
import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestSomething(t *testing.T) {
    // assert: テスト失敗後も続行する
    assert.Equal(t, expected, actual)
    assert.NoError(t, err)
    assert.True(t, condition)

    // require: テスト失敗時に即停止（nilチェック後の操作など）
    require.NoError(t, err)          // err が nil でなければ即停止
    require.NotNil(t, result)        // nil なら以降の操作が panic するため
    assert.Equal(t, expected, result.Value)
}
```

**使い分け**:
- `require.*` — nil ポインタ参照が起こりうる箇所の直前
- `assert.*` — それ以外の検証

## テスト構造（AAAパターン）

Arrange-Act-Assert（準備-実行-検証）構造を優先する:

```go
func TestCalculateSimilarity(t *testing.T) {
    // Arrange（準備）
    v1 := []float64{1, 0, 0}
    v2 := []float64{0, 1, 0}

    // Act（実行）
    similarity, err := CalculateCosineSimilarity(v1, v2)

    // Assert（検証）
    require.NoError(t, err)
    assert.InDelta(t, 0.0, similarity, 0.001)
}
```

## 並列テスト

独立したテストには `t.Parallel()` を使う:

```go
func TestExpensive(t *testing.T) {
    t.Parallel() // このテストを並列実行
    // ...
}
```

## テスト失敗のトラブルシューティング

1. **tdd-guide** エージェントを使用する
2. テストの独立性を確認する（前のテストの状態が残っていないか）
3. モックが正しいことを確認する
4. テストではなく実装を修正する（テストが間違っている場合を除く）

## エージェントサポート

- **tdd-guide** — 新機能に対して積極的に使用し、テストファーストを強制する

## 参考

スキル: `go-testing` で詳細な testify パターンとテーブル駆動テストを参照。
