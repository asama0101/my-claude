---
name: go-testing
description: testify を使った Go テスト戦略：TDD メソドロジー・テーブル駆動テスト・モック・パラメトライズ・カバレッジ要件。
---

# Go テストパターン

testify、TDD メソドロジー、ベストプラクティスを使った Go アプリケーションの総合テスト戦略。

## 使用場面

- 新規 Go コードを書くとき（TDD に従う: レッド → グリーン → リファクタリング）
- Go プロジェクトのテストスイートを設計するとき
- Go のテストカバレッジをレビューするとき
- テストインフラをセットアップするとき

## テストの核心哲学

### テスト駆動開発（TDD）

常に TDD サイクルに従う:

1. **RED**: 期待する動作に対して失敗するテストを書く
2. **GREEN**: テストを通過させる最小限のコードを書く
3. **REFACTOR**: テストをグリーンに保ちながらコードを改善する

```go
// Step 1: 失敗するテストを書く（RED）
func TestAdd(t *testing.T) {
    result := Add(2, 3)
    assert.Equal(t, 5, result)
}

// Step 2: 最小限の実装を書く（GREEN）
func Add(a, b int) int {
    return a + b
}

// Step 3: 必要に応じてリファクタリング（REFACTOR）
```

### カバレッジ要件

- **目標**: コードカバレッジ 80% 以上
- **クリティカルパス**: 100% カバレッジが必須

```bash
go test -cover ./...
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out   # 関数別カバレッジ
go tool cover -html=coverage.out   # HTML レポート
```

## testify の基礎

### assert vs require

```go
import (
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestUser(t *testing.T) {
    user, err := NewUser("alice@example.com")

    // require: 失敗時に即停止（後続でpanicするリスクがある場合）
    require.NoError(t, err)
    require.NotNil(t, user)

    // assert: 失敗後も続行（複数の検証を一度に確認したい場合）
    assert.Equal(t, "alice@example.com", user.Email)
    assert.True(t, user.IsActive)
    assert.NotEmpty(t, user.ID)
}
```

**使い分けルール**:
- `require.*`: nil チェック直後、エラーチェック、テストが意味をなさなくなる前提条件
- `assert.*`: それ以外の検証（複数のアサーションを並べて全結果を確認したい）

### よく使うアサーション

```go
// 等値
assert.Equal(t, expected, actual)
assert.NotEqual(t, unexpected, actual)

// nil チェック
assert.Nil(t, err)
assert.NotNil(t, result)
require.NoError(t, err)    // エラーなしを要求

// 真偽値
assert.True(t, condition)
assert.False(t, condition)

// 文字列
assert.Contains(t, "hello world", "hello")
assert.HasPrefix(t, "error: something", "error:")

// コレクション
assert.Len(t, slice, 3)
assert.Empty(t, slice)
assert.ElementsMatch(t, expected, actual)  // 順序不問

// 数値
assert.Greater(t, actual, 0)
assert.InDelta(t, 1.0, actual, 0.001)  // 浮動小数点

// エラー型
assert.ErrorIs(t, err, ErrNotFound)
assert.ErrorAs(t, err, &myErr)

// パニック
assert.Panics(t, func() { doRiskyThing() })
assert.NotPanics(t, func() { safeThing() })
```

## テーブル駆動テスト（Go の標準パターン）

### 基本構造

```go
func TestCalculate(t *testing.T) {
    tests := []struct {
        name    string
        input   int
        want    int
        wantErr bool
    }{
        {"positive", 5, 25, false},
        {"zero", 0, 0, false},
        {"negative", -1, 0, true},
    }

    for _, tt := range tests {
        tt := tt // Go 1.22 未満では必須
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel() // 独立したテストは並列化

            got, err := Calculate(tt.input)

            if tt.wantErr {
                require.Error(t, err)
                return
            }
            require.NoError(t, err)
            assert.Equal(t, tt.want, got)
        })
    }
}
```

### エラーメッセージ付き

```go
tests := []struct {
    name        string
    input       string
    want        *User
    wantErr     error
}{
    {
        name:    "valid email",
        input:   "alice@example.com",
        want:    &User{Email: "alice@example.com"},
        wantErr: nil,
    },
    {
        name:    "invalid email",
        input:   "not-an-email",
        want:    nil,
        wantErr: ErrInvalidEmail,
    },
}

for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        got, err := NewUser(tt.input)
        if tt.wantErr != nil {
            assert.ErrorIs(t, err, tt.wantErr)
            assert.Nil(t, got)
        } else {
            require.NoError(t, err)
            assert.Equal(t, tt.want.Email, got.Email)
        }
    })
}
```

## モック（testify/mock）

### モック定義

```go
// モック構造体
type MockUserRepository struct {
    mock.Mock
}

func (m *MockUserRepository) FindByID(ctx context.Context, id string) (*User, error) {
    args := m.Called(ctx, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*User), args.Error(1)
}

func (m *MockUserRepository) Save(ctx context.Context, user *User) error {
    args := m.Called(ctx, user)
    return args.Error(0)
}
```

### モック使用

```go
func TestGetUser_ReturnsUser(t *testing.T) {
    // Arrange
    mockRepo := new(MockUserRepository)
    mockRepo.On("FindByID", mock.Anything, "123").
        Return(&User{ID: "123", Name: "Alice"}, nil)

    svc := NewUserService(mockRepo)

    // Act
    user, err := svc.GetUser(context.Background(), "123")

    // Assert
    require.NoError(t, err)
    assert.Equal(t, "Alice", user.Name)
    mockRepo.AssertExpectations(t)  // 必ず確認
}

func TestGetUser_ReturnsError_WhenNotFound(t *testing.T) {
    mockRepo := new(MockUserRepository)
    mockRepo.On("FindByID", mock.Anything, "999").
        Return(nil, ErrNotFound)

    svc := NewUserService(mockRepo)
    _, err := svc.GetUser(context.Background(), "999")

    assert.ErrorIs(t, err, ErrNotFound)
    mockRepo.AssertExpectations(t)
}
```

### mock.Anything と具体的な引数

```go
// 引数を問わない
mockRepo.On("FindByID", mock.Anything, mock.Anything).Return(...)

// 特定の引数のみマッチ
mockRepo.On("FindByID", mock.Anything, "specific-id").Return(...)

// カスタムマッチャー
mockRepo.On("Save", mock.Anything, mock.MatchedBy(func(u *User) bool {
    return u.Email != ""
})).Return(nil)
```

## フィクスチャとセットアップ

### TestMain でのグローバルセットアップ

```go
func TestMain(m *testing.M) {
    // テストスイート開始前のセットアップ
    db := setupTestDatabase()

    code := m.Run()

    // テストスイート終了後のクリーンアップ
    db.Close()
    os.Exit(code)
}
```

### t.Cleanup でのテスト別クリーンアップ

```go
func setupTestDB(t *testing.T) *sql.DB {
    t.Helper()
    db, err := sql.Open("postgres", testDSN)
    require.NoError(t, err)

    t.Cleanup(func() {
        db.Close()
    })

    return db
}

func TestWithDatabase(t *testing.T) {
    db := setupTestDB(t)  // t.Cleanup が自動登録される

    // テスト実行...
}
```

## HTTP ハンドラーのテスト

```go
func TestUserHandler_GetUser(t *testing.T) {
    tests := []struct {
        name       string
        userID     string
        setupMock  func(*MockUserService)
        wantCode   int
        wantBody   string
    }{
        {
            name:   "success",
            userID: "123",
            setupMock: func(m *MockUserService) {
                m.On("GetUser", mock.Anything, "123").
                    Return(&User{ID: "123", Name: "Alice"}, nil)
            },
            wantCode: http.StatusOK,
        },
        {
            name:   "not found",
            userID: "999",
            setupMock: func(m *MockUserService) {
                m.On("GetUser", mock.Anything, "999").
                    Return(nil, ErrNotFound)
            },
            wantCode: http.StatusNotFound,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mockSvc := new(MockUserService)
            tt.setupMock(mockSvc)

            handler := NewUserHandler(mockSvc)
            router := gin.New()
            router.GET("/users/:id", handler.GetUser)

            w := httptest.NewRecorder()
            req := httptest.NewRequest(http.MethodGet, "/users/"+tt.userID, nil)
            router.ServeHTTP(w, req)

            assert.Equal(t, tt.wantCode, w.Code)
            mockSvc.AssertExpectations(t)
        })
    }
}
```

## ベンチマークテスト

```go
func BenchmarkCalculate(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Calculate(100)
    }
}

// 実行: go test -bench=. -benchmem ./...
```

## テスト失敗のトラブルシューティング

1. **tdd-guide** エージェントを使用する
2. テストの独立性を確認する
3. `t.Logf` でデバッグ情報を出力
4. `-v` フラグで詳細出力: `go test -v ./...`
5. `-run` フラグで特定テストのみ実行: `go test -run TestGetUser ./...`
6. `-race` でデータ競合検出: `go test -race ./...`

## テストの品質チェックリスト

- [ ] テーブル駆動テストでエッジケースをカバーしている
- [ ] `require.NoError` でエラーチェックしてから結果を検証している
- [ ] `t.Parallel()` で独立したテストを並列化している
- [ ] モックの `AssertExpectations` を必ず呼んでいる
- [ ] `t.Cleanup` または `defer` でリソースをクリーンアップしている
- [ ] カバレッジが 80% 以上
- [ ] エラーパス（ハッピーパスだけでなく）をテストしている
