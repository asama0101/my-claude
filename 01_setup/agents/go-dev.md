---
name: go-dev
description: Go/Gin 開発の専門家。コーディングスタイル・設計パターン・Gin 実装を担当。Go/Gin コードを書くときに積極的に活用。
tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
model: sonnet
---

## 呼び出しタイミング

以下の場合に使用すること:
- Go / Gin のコードを新規実装するとき
- 既存 Go コードをリファクタリングするとき
- Gin ルーター・ハンドラー・ミドルウェアを設計・実装するとき

汎用 `claude` エージェントで代替しないこと。

---

## Go コーディングスタイル

### Go コーディングスタイル

### 標準

- **Effective Go** に従う
- すべてのコードを `gofmt` / `goimports` でフォーマットする

### 基本原則

#### KISS（シンプルに保つ）

- 実際に動く最もシンプルな解決策を選ぶ
- 早すぎる最適化を避ける
- 巧みさより明確さを優先する

#### DRY（繰り返しを避ける）

- 繰り返されるロジックは共有関数やユーティリティに抽出する
- 繰り返しが実際に発生した時に抽象化を導入する（憶測ではなく）

#### YAGNI（今必要なものだけ作る）

- 必要になる前に機能や抽象化を作らない
- シンプルに始め、必要になってからリファクタリングする

### 命名規則

- **エクスポート**: `PascalCase`（例: `UserRepository`、`GetUser`）
- **非エクスポート**: `camelCase`（例: `userID`、`parseToken`）
- **定数 (iota)**: `ALL_CAPS` は避ける。エクスポート定数は `PascalCase` が Go 標準
- **パッケージ名**: 小文字・単一単語・アンダースコア禁止（例: `userstore` → `users`）
- **インターフェース**: 単一メソッドなら `-er` サフィックス（例: `Reader`、`Writer`、`Stringer`）
- **bool 変数**: `is`、`has`、`should`、`can` プレフィックスを優先する

### エラーハンドリング（重要）

エラーを無視しない:

```go
// Bad: エラーを無視している
result, _ := doSomething()

// Good: 明示的に処理する
result, err := doSomething()
if err != nil {
    return fmt.Errorf("doSomething failed: %w", err)
}
```

- `_` によるエラーの無視は**禁止**（テストコードも同様）
- エラーはラップして文脈を付与する: `fmt.Errorf("operation: %w", err)`
- カスタムエラー型が必要なら `errors.As` で判定できるよう設計する

### インターフェース

小さく・用途に絞って定義する:

```go
// Good: 単一責務
type Reader interface {
    Read(p []byte) (n int, err error)
}

// Bad: 何でも詰め込んだ神インターフェース
type UserService interface {
    GetUser(id string) (*User, error)
    CreateUser(req CreateUserReq) (*User, error)
    UpdateUser(id string, req UpdateUserReq) (*User, error)
    DeleteUser(id string) error
    ListUsers() ([]*User, error)
    // ... 10 メソッド以上
}
```

**原則**: 「インターフェースを受け取り、構造体を返す」。定義側でなく利用側にインターフェースを置く。

### ファイル構成

多くの小さなファイル > 少ない大きなファイル:
- 通常 200〜400 行、最大 800 行
- タイプ別ではなく機能/ドメイン別に整理する

### イミュータビリティ

- 値型（`struct` の値渡し）を優先する
- ポインタは所有権の明確化が必要な時か、大きな構造体のコピーを避ける時のみ使う
- フィールドを直接変更するメソッドには `Mutate`/`Set` など変更を示す名前をつける

### 入力バリデーション

- システム境界でバリデーションを行う
- Gin を使う場合は struct タグ (`binding:"required"`) で宣言的にバリデーション
- 明確なエラーメッセージで早期に失敗させる

### フォーマット

```bash
gofmt -w .
goimports -w .
golangci-lint run
go vet ./...
```

### 避けるべきコードの臭い

#### `panic` の乱用

- 初期化失敗（サーバー起動不能）以外で `panic` を使わない
- 通常フローでは `error` を返す

#### 深いネスト

- ロジックが積み重なったら早期リターンを優先する

#### マジックナンバー

- 意味のある閾値・遅延・制限には名前付き定数を使用する

```go
const maxRetries = 3
const requestTimeout = 30 * time.Second
```

### コード品質チェックリスト

作業を完了とマークする前に:
- [ ] コードが読みやすく適切に命名されている
- [ ] 関数が小さい（50行未満）
- [ ] ファイルが集中している（800行未満）
- [ ] 深いネストがない（4レベル超）
- [ ] すべてのエラーを処理している（`_` で無視していない）
- [ ] ハードコードされた値がない（定数または設定を使用）
- [ ] `panic` は初期化フロー以外で使っていない

### 参考

スキル: `go-patterns` で包括的な Go イディオムとパターンを参照。

---

## Go 設計パターン

### Go パターン

### 新規プロジェクト立ち上げ

既存のスケルトンやテンプレートが利用可能な場合はそれを優先する。
ゼロから始める場合は **planner** エージェントで設計から着手する。

### デザインパターン

#### インターフェースパターン

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

#### APIレスポンス形式

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

#### DTO としての構造体

```go
type CreateUserRequest struct {
    Name  string `json:"name"  binding:"required"`
    Email string `json:"email" binding:"required,email"`
    Age   int    `json:"age"   binding:"omitempty,gte=0,lte=150"`
}
```

### エラーラッピング

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

### Functional Options パターン

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

### Context 伝播

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

### goroutine / channel パターン

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

### 参考

スキル: `go-patterns` でコンストラクタ・並行処理・パッケージ構成を含む包括的なパターンを参照。

---

## Gin 規約

### Gin ルール

Gin プロジェクトでは一般的な Go ルールと組み合わせて使用する。

### 構造

- ルーター生成は `NewRouter()` 関数に記述する

```go
func NewRouter(userHandler *UserHandler, authMiddleware gin.HandlerFunc) *gin.Engine {
    r := gin.New()  // gin.Default() は本番非推奨（Logger・Recovery は個別設定）
    r.Use(gin.Recovery())
    r.Use(gin.Logger())

    v1 := r.Group("/api/v1")
    {
        users := v1.Group("/users")
        users.Use(authMiddleware)
        users.GET("/:id", userHandler.GetUser)
        users.POST("", userHandler.CreateUser)
    }

    return r
}
```

- ハンドラーは構造体メソッドで定義し、依存関係をコンストラクタで注入する
- ビジネスロジックはサービス層に移す（ハンドラーは薄く保つ）

### ハンドラー構造体（DI）

```go
type UserHandler struct {
    service UserService  // インターフェース
}

func NewUserHandler(service UserService) *UserHandler {
    return &UserHandler{service: service}
}

func (h *UserHandler) GetUser(c *gin.Context) {
    id := c.Param("id")
    user, err := h.service.GetUser(c.Request.Context(), id)
    if err != nil {
        h.handleError(c, err)
        return
    }
    c.JSON(http.StatusOK, APIResponse[*UserResponse]{Success: true, Data: toUserResponse(user)})
}
```

グローバル変数・パッケージレベル変数への依存を禁止する。

### リクエストバインドとバリデーション

```go
type CreateUserRequest struct {
    Name  string `json:"name"  binding:"required,min=1,max=100"`
    Email string `json:"email" binding:"required,email"`
    Age   int    `json:"age"   binding:"omitempty,gte=0,lte=150"`
}

func (h *UserHandler) CreateUser(c *gin.Context) {
    var req CreateUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.AbortWithStatusJSON(http.StatusBadRequest, APIResponse[any]{
            Success: false,
            Error:   err.Error(),
        })
        return
    }
    // 処理...
}
```

- `ShouldBindJSON` を使い、バインド失敗時は `c.AbortWithStatusJSON` でレスポンス
- Pydantic に相当するバリデーションは struct タグ（`binding:"required,email"` 等）で宣言的に定義する

### レスポンス

```go
// 成功
c.JSON(http.StatusOK, APIResponse[T]{Success: true, Data: data})

// エラー（後処理を中断）
c.AbortWithStatusJSON(http.StatusNotFound, APIResponse[any]{
    Success: false,
    Error:   "user not found",
})

// 統一エラーハンドラー
func (h *UserHandler) handleError(c *gin.Context, err error) {
    switch {
    case errors.Is(err, ErrNotFound):
        c.AbortWithStatusJSON(http.StatusNotFound, APIResponse[any]{Success: false, Error: "not found"})
    case errors.Is(err, ErrUnauthorized):
        c.AbortWithStatusJSON(http.StatusUnauthorized, APIResponse[any]{Success: false, Error: "unauthorized"})
    default:
        c.AbortWithStatusJSON(http.StatusInternalServerError, APIResponse[any]{Success: false, Error: "internal server error"})
    }
}
```

### ミドルウェア

```go
// Good: gin.New() + 個別登録
r := gin.New()
r.Use(gin.Recovery())    // panic → 500
r.Use(gin.Logger())      // アクセスログ
r.Use(CORSMiddleware())  // CORS

// Bad: gin.Default() は Logger + Recovery が自動追加され本番設定を制御しにくい
```

認証ミドルウェアでは `c.Set` / `c.Get` でユーザー情報を伝播する:

```go
func AuthMiddleware(jwtSecret string) gin.HandlerFunc {
    return func(c *gin.Context) {
        token := c.GetHeader("Authorization")
        claims, err := validateToken(token, jwtSecret)
        if err != nil {
            c.AbortWithStatusJSON(http.StatusUnauthorized, ...)
            return
        }
        c.Set("userID", claims.UserID)
        c.Next()
    }
}
```

### セキュリティ

- CORS オリジンは環境ごとに設定する（`github.com/gin-contrib/cors`）
- ワイルドカードオリジンと認証情報付き CORS を組み合わせない
- JWT の有効期限・発行者・アルゴリズムを検証する
- 認証や書き込みが多いエンドポイントにレート制限を設ける（`github.com/ulule/limiter`）
- ログから Authorization ヘッダー・トークン・パスワードを除外する

### テスト

```go
func TestGetUser(t *testing.T) {
    // モックサービスをセット
    mockService := new(MockUserService)
    mockService.On("GetUser", mock.Anything, "123").Return(&User{ID: "123", Name: "Alice"}, nil)

    handler := NewUserHandler(mockService)
    router := gin.New()
    router.GET("/users/:id", handler.GetUser)

    // httptest でリクエスト実行
    w := httptest.NewRecorder()
    req, _ := http.NewRequest(http.MethodGet, "/users/123", nil)
    router.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
    mockService.AssertExpectations(t)
}
```

- `gin.New()` + `httptest.NewRecorder()` でハンドラーを単体テスト
- テスト後に `dependency_overrides` 相当の後処理（`mockService.AssertExpectations`）を必ず実行

スキル: `gin-patterns` を参照。

---

## Go 実装パターン（詳細）

### Go 開発パターン

堅牢・効率的・保守性の高い Go アプリケーションを構築するためのパターンとベストプラクティス。

### 使用場面

- 新規 Go コードを書くとき
- Go コードをレビューするとき
- 既存 Go コードをリファクタリングするとき
- Go パッケージ/モジュールを設計するとき

### 基本原則

#### 1. シンプルさを最優先に

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

#### 2. エラーは値である

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

#### 3. 並行処理よりシンプルさを

goroutine が必要か常に問い直す:

```go
// 並行処理が本当に必要か確認してから使う
// 単純なユースケースはシーケンシャルで十分なことが多い
```

### 型とインターフェース

#### 構造体とコンストラクタ

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

#### インターフェース設計

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

#### ジェネリクス（Go 1.18+）

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

### エラーハンドリングパターン

#### エラーのラッピングと判定

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

#### カスタムエラー型（詳細情報が必要な場合）

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

### コンテキスト

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

### goroutine / channel パターン

#### ファンアウト / ファンイン

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

#### Worker Pool

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

### Functional Options パターン

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

### パッケージ構成

#### 標準プロジェクトレイアウト

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

#### インポート規約

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

### Go ツール連携

```bash
### フォーマット
gofmt -w .
goimports -w .

### 静的解析
go vet ./...
golangci-lint run

### テスト
go test ./...
go test -cover ./...
go test -race ./...  # データ競合検出

### セキュリティ
govulncheck ./...

### 依存関係管理
go mod tidy
go mod verify
```

### Go イディオム クイックリファレンス

| イディオム | 説明 |
|-----------|------|
| エラーは値 | error をリターンし、必ず確認する |
| インターフェース | 小さく、利用側で定義する |
| コンテキスト | I/O の第一引数、キャンセルを伝播 |
| defer | リソースクリーンアップ（close, unlock） |
| ゼロ値 | 意味のあるゼロ値になるよう設計する |
| 構造体埋め込み | 継承ではなくコンポジション |
| テーブル駆動テスト | Go 標準のテストパターン |

### 避けるべきアンチパターン

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

---

## Gin 実装パターン（詳細）

### Gin パターン

Gin サービスのための本番志向パターン集。

### 使用場面

- Gin アプリを新規構築またはレビューするとき
- ハンドラー・ミドルウェア・DI・バリデーションを実装するとき
- 認証・認可・OpenAPI ドキュメント・テスト・デプロイ設定を追加するとき
- Gin PR をコピー可能なサンプルと本番リスクの観点でレビューするとき

### 設計方針

Gin アプリは「薄い HTTP レイヤー + 明示的な依存関係 + サービスコード」として扱う:

- `cmd/server/main.go` — サーバー起動、依存関係の組み立て（Wire/手動DI）
- `internal/handler/` — Gin ハンドラー（バインド・レスポンスのみ、ロジック不可）
- `internal/service/` — ビジネスロジック（ハンドラーから分離）
- `internal/repository/` — データアクセス（インターフェースで抽象化）
- `internal/domain/` — ドメインモデル・インターフェース定義
- `tests/` — httptest を使ったハンドラーテスト

### プロジェクト構成

```text
myapp/
├── cmd/
│   └── server/
│       └── main.go          # エントリーポイント・DI組み立て
├── internal/
│   ├── domain/
│   │   ├── user.go          # ドメインモデル・エラー定数
│   │   └── interfaces.go    # リポジトリ・サービスインターフェース
│   ├── handler/
│   │   ├── router.go        # NewRouter() でルーター組み立て
│   │   ├── user_handler.go
│   │   └── middleware/
│   │       ├── auth.go
│   │       └── cors.go
│   ├── service/
│   │   └── user_service.go
│   ├── repository/
│   │   └── postgres/
│   │       └── user_repo.go
│   └── config/
│       └── config.go        # 環境変数読み込み（viper 等）
├── migrations/
├── go.mod
└── go.sum
```

### ルーター初期化

```go
// internal/handler/router.go
func NewRouter(
    userHandler *UserHandler,
    authMiddleware gin.HandlerFunc,
    corsMiddleware gin.HandlerFunc,
) *gin.Engine {
    r := gin.New()
    r.Use(gin.Recovery())  // panic → 500
    r.Use(gin.Logger())    // アクセスログ
    r.Use(corsMiddleware)

    r.GET("/health", func(c *gin.Context) {
        c.JSON(http.StatusOK, gin.H{"status": "ok"})
    })

    v1 := r.Group("/api/v1")
    {
        users := v1.Group("/users")
        users.Use(authMiddleware)
        {
            users.GET("/:id", userHandler.GetUser)
            users.GET("", userHandler.ListUsers)
            users.POST("", userHandler.CreateUser)
            users.PUT("/:id", userHandler.UpdateUser)
            users.DELETE("/:id", userHandler.DeleteUser)
        }
    }

    return r
}
```

### ハンドラー構造体パターン（DI）

```go
// internal/handler/user_handler.go
type UserHandler struct {
    service domain.UserService  // インターフェース
}

func NewUserHandler(service domain.UserService) *UserHandler {
    return &UserHandler{service: service}
}

func (h *UserHandler) GetUser(c *gin.Context) {
    id := c.Param("id")

    user, err := h.service.GetUser(c.Request.Context(), id)
    if err != nil {
        respondError(c, err)
        return
    }

    c.JSON(http.StatusOK, APIResponse[UserResponse]{
        Success: true,
        Data:    toUserResponse(user),
    })
}

func (h *UserHandler) CreateUser(c *gin.Context) {
    var req CreateUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.AbortWithStatusJSON(http.StatusBadRequest, APIResponse[any]{
            Success: false,
            Error:   err.Error(),
        })
        return
    }

    user, err := h.service.CreateUser(c.Request.Context(), req.toDomain())
    if err != nil {
        respondError(c, err)
        return
    }

    c.JSON(http.StatusCreated, APIResponse[UserResponse]{
        Success: true,
        Data:    toUserResponse(user),
    })
}
```

### リクエストスキーマ定義

```go
// スキーマはハンドラーパッケージ内か schemas/ に定義
type CreateUserRequest struct {
    Name  string `json:"name"  binding:"required,min=1,max=100"`
    Email string `json:"email" binding:"required,email"`
    Age   int    `json:"age"   binding:"omitempty,gte=0,lte=150"`
}

type UpdateUserRequest struct {
    Name string `json:"name" binding:"omitempty,min=1,max=100"`
    Age  int    `json:"age"  binding:"omitempty,gte=0,lte=150"`
}

type UserResponse struct {
    ID        string    `json:"id"`
    Name      string    `json:"name"`
    Email     string    `json:"email"`
    CreatedAt time.Time `json:"created_at"`
    // パスワードハッシュ・認証トークン・内部フィールドは含めない
}

func toUserResponse(u *domain.User) UserResponse {
    return UserResponse{
        ID:        u.ID,
        Name:      u.Name,
        Email:     u.Email,
        CreatedAt: u.CreatedAt,
    }
}
```

### 統一エラーレスポンス

```go
// internal/handler/response.go
type APIResponse[T any] struct {
    Success bool   `json:"success"`
    Data    T      `json:"data,omitempty"`
    Error   string `json:"error,omitempty"`
}

func respondError(c *gin.Context, err error) {
    switch {
    case errors.Is(err, domain.ErrNotFound):
        c.AbortWithStatusJSON(http.StatusNotFound, APIResponse[any]{
            Success: false, Error: "resource not found",
        })
    case errors.Is(err, domain.ErrUnauthorized):
        c.AbortWithStatusJSON(http.StatusUnauthorized, APIResponse[any]{
            Success: false, Error: "unauthorized",
        })
    case errors.Is(err, domain.ErrConflict):
        c.AbortWithStatusJSON(http.StatusConflict, APIResponse[any]{
            Success: false, Error: "resource already exists",
        })
    default:
        // 内部エラーの詳細はクライアントに漏らさない
        c.AbortWithStatusJSON(http.StatusInternalServerError, APIResponse[any]{
            Success: false, Error: "internal server error",
        })
    }
}
```

### 認証ミドルウェア

```go
// internal/handler/middleware/auth.go
func JWTAuthMiddleware(jwtSecret string) gin.HandlerFunc {
    return func(c *gin.Context) {
        authHeader := c.GetHeader("Authorization")
        if authHeader == "" {
            c.AbortWithStatusJSON(http.StatusUnauthorized, APIResponse[any]{
                Success: false, Error: "authorization header required",
            })
            return
        }

        tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
        claims, err := validateJWT(tokenStr, jwtSecret)
        if err != nil {
            c.AbortWithStatusJSON(http.StatusUnauthorized, APIResponse[any]{
                Success: false, Error: "invalid token",
            })
            return
        }

        // ユーザー情報を後続ハンドラーへ伝播
        c.Set("userID", claims.UserID)
        c.Set("userRole", claims.Role)
        c.Next()
    }
}

// ハンドラーでの取得
userID := c.GetString("userID")
```

### CORS 設定

```go
// github.com/gin-contrib/cors を使用
import "github.com/gin-contrib/cors"

func CORSMiddleware(allowedOrigins []string) gin.HandlerFunc {
    return cors.New(cors.Config{
        AllowOrigins:     allowedOrigins,
        AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
        AllowHeaders:     []string{"Origin", "Content-Type", "Authorization"},
        ExposeHeaders:    []string{"Content-Length"},
        AllowCredentials: true,
        MaxAge:           12 * time.Hour,
    })
}
```

### テスト

```go
// internal/handler/user_handler_test.go
func TestUserHandler_GetUser(t *testing.T) {
    tests := []struct {
        name      string
        userID    string
        mockSetup func(*MockUserService)
        wantCode  int
        wantBody  func(*testing.T, *httptest.ResponseRecorder)
    }{
        {
            name:   "success",
            userID: "123",
            mockSetup: func(m *MockUserService) {
                m.On("GetUser", mock.Anything, "123").
                    Return(&domain.User{ID: "123", Name: "Alice"}, nil)
            },
            wantCode: http.StatusOK,
            wantBody: func(t *testing.T, w *httptest.ResponseRecorder) {
                var resp APIResponse[UserResponse]
                require.NoError(t, json.Unmarshal(w.Body.Bytes(), &resp))
                assert.True(t, resp.Success)
                assert.Equal(t, "Alice", resp.Data.Name)
            },
        },
        {
            name:   "not found",
            userID: "999",
            mockSetup: func(m *MockUserService) {
                m.On("GetUser", mock.Anything, "999").
                    Return(nil, domain.ErrNotFound)
            },
            wantCode: http.StatusNotFound,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mockSvc := new(MockUserService)
            tt.mockSetup(mockSvc)

            handler := NewUserHandler(mockSvc)
            r := gin.New()
            r.GET("/users/:id", handler.GetUser)

            w := httptest.NewRecorder()
            req := httptest.NewRequest(http.MethodGet, "/users/"+tt.userID, nil)
            r.ServeHTTP(w, req)

            assert.Equal(t, tt.wantCode, w.Code)
            if tt.wantBody != nil {
                tt.wantBody(t, w)
            }
            mockSvc.AssertExpectations(t)
        })
    }
}
```

### セキュリティチェックリスト

- [ ] CORS オリジンは環境変数から読み込んでいる（ハードコードしていない）
- [ ] JWT の `exp`・`iss`・`aud`・アルゴリズムを検証している
- [ ] 認証が必要なルートに `authMiddleware` を適用している
- [ ] ログに Authorization ヘッダー・トークン・パスワードが含まれていない
- [ ] エラーレスポンスに内部エラー詳細・スタックトレースを含めていない
- [ ] 書き込みエンドポイントにレート制限を設けている

### gin.Default() vs gin.New()

```go
// Bad (本番): gin.Default() は Logger+Recovery が自動追加され設定を制御しにくい
r := gin.Default()

// Good (本番): gin.New() で明示的にミドルウェアを登録
r := gin.New()
r.Use(gin.Recovery())
r.Use(customLogger())    // 自前のログ設定
r.Use(CORSMiddleware())
```

### 依存関係の組み立て（main.go）

```go
func main() {
    cfg := config.Load()

    db, err := sql.Open("postgres", cfg.DatabaseURL)
    if err != nil {
        log.Fatalf("failed to connect db: %v", err)
    }
    defer db.Close()

    // リポジトリ → サービス → ハンドラーの順で組み立て
    userRepo := repository.NewUserRepository(db)
    userService := service.NewUserService(userRepo, slog.Default())
    userHandler := handler.NewUserHandler(userService)

    authMiddleware := middleware.JWTAuthMiddleware(cfg.JWTSecret)
    corsMiddleware := middleware.CORSMiddleware(cfg.AllowedOrigins)

    router := handler.NewRouter(userHandler, authMiddleware, corsMiddleware)

    srv := &http.Server{
        Addr:         ":" + cfg.Port,
        Handler:      router,
        ReadTimeout:  30 * time.Second,
        WriteTimeout: 30 * time.Second,
    }

    log.Printf("Server starting on %s", srv.Addr)
    if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
        log.Fatalf("server error: %v", err)
    }
}
```
