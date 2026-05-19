---
paths:
  - "**/*.go"
---
# Go パターン

## 新規プロジェクト立ち上げ

既存のスケルトンやテンプレートが利用可能な場合はそれを優先する。
ゼロから始める場合は **planner** エージェントで設計から着手する。

## デザインパターン

### インターフェースパターン

「インターフェースを受け取り、構造体を返す」:

```go
// 利用側でインターフェースを定義する
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
    FindAll(ctx context.Context) ([]*User, error)
    Delete(ctx context.Context, id string) error
}

// 実装は別パッケージで
type postgresUserRepository struct {
    db *sql.DB
}

func NewUserRepository(db *sql.DB) UserRepository {
    return &postgresUserRepository{db: db}
}
```

ビジネスロジックは抽象インターフェースに依存し、ストレージの実装には依存しない — データソースの切り替えが容易になり、モックを使ったテストが簡単になる。

### APIレスポンス形式

すべての API レスポンスに一貫したエンベロープを使用する:

```go
type APIResponse[T any] struct {
    Success bool   `json:"success"`
    Data    T      `json:"data,omitempty"`
    Error   string `json:"error,omitempty"`
}

type PaginatedResponse[T any] struct {
    Success bool `json:"success"`
    Data    []T  `json:"data"`
    Total   int  `json:"total"`
    Page    int  `json:"page"`
    Limit   int  `json:"limit"`
}
```

### DTO としての構造体

```go
type CreateUserRequest struct {
    Name  string `json:"name"  binding:"required"`
    Email string `json:"email" binding:"required,email"`
    Age   int    `json:"age"   binding:"omitempty,gte=0,lte=150"`
}
```

## エラーラッピング

```go
// Good: %w でエラーをラップして文脈を付与
func (r *postgresUserRepository) FindByID(ctx context.Context, id string) (*User, error) {
    user, err := r.db.QueryContext(ctx, "SELECT ...")
    if err != nil {
        return nil, fmt.Errorf("findByID %s: %w", id, err)
    }
    return user, nil
}

// 呼び出し側でエラーの種類を判定
if errors.Is(err, sql.ErrNoRows) {
    return nil, ErrNotFound
}

// カスタムエラー型
var ErrNotFound = errors.New("not found")
var ErrUnauthorized = errors.New("unauthorized")
```

## Functional Options パターン

オプション引数を型安全に渡す:

```go
type Server struct {
    host    string
    port    int
    timeout time.Duration
}

type Option func(*Server)

func WithTimeout(d time.Duration) Option {
    return func(s *Server) { s.timeout = d }
}

func WithPort(port int) Option {
    return func(s *Server) { s.port = port }
}

func NewServer(opts ...Option) *Server {
    s := &Server{host: "localhost", port: 8080, timeout: 30 * time.Second}
    for _, opt := range opts {
        opt(s)
    }
    return s
}

// 使用例
srv := NewServer(WithPort(9090), WithTimeout(60*time.Second))
```

## Context 伝播

すべての I/O を伴う関数の第一引数は `context.Context`:

```go
// Good: context を必ず第一引数に
func (s *UserService) GetUser(ctx context.Context, id string) (*User, error) {
    return s.repo.FindByID(ctx, id)
}

// Bad: context がない
func (s *UserService) GetUser(id string) (*User, error) {
    return s.repo.FindByID(context.Background(), id)  // キャンセルが伝播しない
}
```

- `context.Background()` は main/テストのエントリーポイントのみで使う
- `context.TODO()` は後でリファクタリングが必要な一時的な placeholder

## goroutine / channel パターン

所有権とクローズ責任を明確にする:

```go
// Good: 送信側が channel をクローズ
func producer(ctx context.Context) <-chan int {
    ch := make(chan int)
    go func() {
        defer close(ch)  // 送信側がクローズ
        for i := 0; ; i++ {
            select {
            case <-ctx.Done():
                return
            case ch <- i:
            }
        }
    }()
    return ch
}

// goroutine リークを防ぐ: WaitGroup で待機
var wg sync.WaitGroup
wg.Add(1)
go func() {
    defer wg.Done()
    // work...
}()
wg.Wait()
```

## 参考

スキル: `go-patterns` でコンストラクタ・並行処理・パッケージ構成を含む包括的なパターンを参照。
