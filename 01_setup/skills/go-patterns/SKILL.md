---
name: go-patterns
description: Go イディオム・インターフェース・エラーハンドリング・goroutine・パッケージ構成のベストプラクティス。堅牢・効率的・保守性の高い Go アプリケーション構築のためのパターン集。
---

# Go 開発パターン

堅牢・効率的・保守性の高い Go アプリケーションを構築するためのパターンとベストプラクティス。

## 使用場面

- 新規 Go コードを書くとき
- Go コードをレビューするとき
- 既存 Go コードをリファクタリングするとき
- Go パッケージ/モジュールを設計するとき

## 基本原則

### 1. シンプルさを最優先に

Go は読みやすさと明示性を重視する:

```go
// Good: 明確で読みやすい
func getActiveUsers(users []User) []User {
    active := make([]User, 0, len(users))
    for _, u := range users {
        if u.IsActive {
            active = append(active, u)
        }
    }
    return active
}

// Bad: 巧みだが Go らしくない（過度な汎用化）
func filter[T any](items []T, pred func(T) bool) []T {
    // ... (小さなコードベースでは不要な抽象化)
}
```

### 2. エラーは値である

Go のエラーハンドリングは明示的:

```go
// Good: エラーを明示的に処理
user, err := repo.FindByID(ctx, id)
if err != nil {
    return fmt.Errorf("getUser %s: %w", id, err)
}

// Bad: エラーを無視
user, _ := repo.FindByID(ctx, id)
```

### 3. 並行処理よりシンプルさを

goroutine が必要か常に問い直す:

```go
// 並行処理が本当に必要か確認してから使う
// 単純なユースケースはシーケンシャルで十分なことが多い
```

## 型とインターフェース

### 構造体とコンストラクタ

```go
type UserService struct {
    repo   UserRepository  // インターフェース
    logger *slog.Logger
    clock  func() time.Time  // テスト可能にするための依存注入
}

// コンストラクタでバリデーション
func NewUserService(repo UserRepository, logger *slog.Logger) (*UserService, error) {
    if repo == nil {
        return nil, errors.New("repo is required")
    }
    if logger == nil {
        logger = slog.Default()
    }
    return &UserService{
        repo:   repo,
        logger: logger,
        clock:  time.Now,
    }, nil
}
```

### インターフェース設計

```go
// Good: 小さく用途に絞ったインターフェース（利用側で定義）
type UserFinder interface {
    FindByID(ctx context.Context, id string) (*User, error)
}

type UserSaver interface {
    Save(ctx context.Context, user *User) error
}

// 組み合わせ
type UserRepository interface {
    UserFinder
    UserSaver
    Delete(ctx context.Context, id string) error
}
```

### ジェネリクス（Go 1.18+）

```go
// シンプルなユーティリティには使う
func Map[T, U any](slice []T, f func(T) U) []U {
    result := make([]U, len(slice))
    for i, v := range slice {
        result[i] = f(v)
    }
    return result
}

// ドメインロジックには使わない（読みにくくなる）
```

## エラーハンドリングパターン

### エラーのラッピングと判定

```go
// カスタムエラー型
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
    ErrConflict     = errors.New("conflict")
)

// エラーをラップして文脈を付与
func (r *postgresRepo) FindByID(ctx context.Context, id string) (*User, error) {
    var user User
    err := r.db.QueryRowContext(ctx, "SELECT ...").Scan(&user)
    if errors.Is(err, sql.ErrNoRows) {
        return nil, fmt.Errorf("user %s: %w", id, ErrNotFound)
    }
    if err != nil {
        return nil, fmt.Errorf("findByID %s: %w", id, err)
    }
    return &user, nil
}

// 呼び出し側でエラーを判定
user, err := repo.FindByID(ctx, id)
if errors.Is(err, ErrNotFound) {
    // 404 を返す
}
```

### カスタムエラー型（詳細情報が必要な場合）

```go
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation error: %s %s", e.Field, e.Message)
}

// errors.As で取得
var valErr *ValidationError
if errors.As(err, &valErr) {
    // フィールド情報を使う
}
```

## コンテキスト

```go
// すべての I/O 関数の第一引数は context.Context
func (s *Service) ProcessOrder(ctx context.Context, orderID string) error {
    // ctx をそのまま伝播
    user, err := s.userRepo.FindByID(ctx, orderID)
    if err != nil {
        return err
    }

    // タイムアウト付きの子 context
    childCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    return s.paymentService.Charge(childCtx, user.PaymentMethod)
}
```

## goroutine / channel パターン

### ファンアウト / ファンイン

```go
func processAll(ctx context.Context, items []Item) ([]Result, error) {
    results := make(chan Result, len(items))
    errCh := make(chan error, 1)

    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(item Item) {
            defer wg.Done()
            r, err := process(ctx, item)
            if err != nil {
                select {
                case errCh <- err: // 最初のエラーだけ送る
                default:
                }
                return
            }
            results <- r
        }(item)
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    select {
    case err := <-errCh:
        return nil, err
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }

    var out []Result
    for r := range results {
        out = append(out, r)
    }
    return out, nil
}
```

### Worker Pool

```go
func workerPool(ctx context.Context, jobs <-chan Job, numWorkers int) <-chan Result {
    results := make(chan Result)
    var wg sync.WaitGroup

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {
                select {
                case <-ctx.Done():
                    return
                case results <- process(job):
                }
            }
        }()
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    return results
}
```

## Functional Options パターン

```go
type Config struct {
    timeout    time.Duration
    maxRetries int
    baseURL    string
}

type Option func(*Config)

func WithTimeout(d time.Duration) Option {
    return func(c *Config) { c.timeout = d }
}

func WithMaxRetries(n int) Option {
    return func(c *Config) { c.maxRetries = n }
}

func NewClient(baseURL string, opts ...Option) *Client {
    cfg := &Config{
        timeout:    30 * time.Second,
        maxRetries: 3,
        baseURL:    baseURL,
    }
    for _, opt := range opts {
        opt(cfg)
    }
    return &Client{cfg: cfg}
}

// 使用例
client := NewClient("https://api.example.com",
    WithTimeout(10*time.Second),
    WithMaxRetries(5),
)
```

## パッケージ構成

### 標準プロジェクトレイアウト

```
myapp/
├── cmd/
│   └── server/
│       └── main.go        # エントリーポイント
├── internal/              # 外部非公開
│   ├── domain/            # ドメインモデル・インターフェース
│   │   └── user.go
│   ├── handler/           # HTTP ハンドラー
│   │   └── user_handler.go
│   ├── service/           # ビジネスロジック
│   │   └── user_service.go
│   └── repository/        # データアクセス
│       └── user_repo.go
├── pkg/                   # 外部公開ライブラリ
├── migrations/            # DB マイグレーション
├── go.mod
└── go.sum
```

### インポート規約

```go
import (
    // 標準ライブラリ
    "context"
    "fmt"
    "net/http"

    // サードパーティ
    "github.com/gin-gonic/gin"
    "github.com/stretchr/testify/assert"

    // 内部パッケージ
    "myapp/internal/domain"
    "myapp/internal/service"
)
```

## Go ツール連携

```bash
# フォーマット
gofmt -w .
goimports -w .

# 静的解析
go vet ./...
golangci-lint run

# テスト
go test ./...
go test -cover ./...
go test -race ./...  # データ競合検出

# セキュリティ
govulncheck ./...

# 依存関係管理
go mod tidy
go mod verify
```

## Go イディオム クイックリファレンス

| イディオム | 説明 |
|-----------|------|
| エラーは値 | error をリターンし、必ず確認する |
| インターフェース | 小さく、利用側で定義する |
| コンテキスト | I/O の第一引数、キャンセルを伝播 |
| defer | リソースクリーンアップ（close, unlock） |
| ゼロ値 | 意味のあるゼロ値になるよう設計する |
| 構造体埋め込み | 継承ではなくコンポジション |
| テーブル駆動テスト | Go 標準のテストパターン |

## 避けるべきアンチパターン

```go
// Bad: グローバル変数でステートを管理
var globalDB *sql.DB  // テスト困難、競合リスク

// Good: 構造体フィールドで管理
type Repository struct {
    db *sql.DB
}

// Bad: init() に重いロジック
func init() {
    db, _ = sql.Open(...)  // エラー無視 + テスト困難
}

// Good: コンストラクタで初期化
func NewRepository(db *sql.DB) *Repository {
    return &Repository{db: db}
}

// Bad: goroutine 漏れ
go func() {
    for {
        doWork() // キャンセル条件がない
    }
}()

// Good: context でキャンセル可能に
go func() {
    for {
        select {
        case <-ctx.Done():
            return
        default:
            doWork()
        }
    }
}()
```

**覚えておくこと**: Go コードはシンプルで明示的であるべきだ。「少ない機能で多くを表現する」が Go の哲学。迷ったときは、巧みさよりシンプルさを優先する。
