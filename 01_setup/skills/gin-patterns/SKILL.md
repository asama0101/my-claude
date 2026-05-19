---
name: gin-patterns
description: Gin フレームワークを使った Go HTTP API：ハンドラー設計・ミドルウェア・DI・バリデーション・テスト・本番運用パターン集。
---

# Gin パターン

Gin サービスのための本番志向パターン集。

## 使用場面

- Gin アプリを新規構築またはレビューするとき
- ハンドラー・ミドルウェア・DI・バリデーションを実装するとき
- 認証・認可・OpenAPI ドキュメント・テスト・デプロイ設定を追加するとき
- Gin PR をコピー可能なサンプルと本番リスクの観点でレビューするとき

## 設計方針

Gin アプリは「薄い HTTP レイヤー + 明示的な依存関係 + サービスコード」として扱う:

- `cmd/server/main.go` — サーバー起動、依存関係の組み立て（Wire/手動DI）
- `internal/handler/` — Gin ハンドラー（バインド・レスポンスのみ、ロジック不可）
- `internal/service/` — ビジネスロジック（ハンドラーから分離）
- `internal/repository/` — データアクセス（インターフェースで抽象化）
- `internal/domain/` — ドメインモデル・インターフェース定義
- `tests/` — httptest を使ったハンドラーテスト

## プロジェクト構成

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

## ルーター初期化

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

## ハンドラー構造体パターン（DI）

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

## リクエストスキーマ定義

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

## 統一エラーレスポンス

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

## 認証ミドルウェア

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

## CORS 設定

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

## テスト

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

## セキュリティチェックリスト

- [ ] CORS オリジンは環境変数から読み込んでいる（ハードコードしていない）
- [ ] JWT の `exp`・`iss`・`aud`・アルゴリズムを検証している
- [ ] 認証が必要なルートに `authMiddleware` を適用している
- [ ] ログに Authorization ヘッダー・トークン・パスワードが含まれていない
- [ ] エラーレスポンスに内部エラー詳細・スタックトレースを含めていない
- [ ] 書き込みエンドポイントにレート制限を設けている

## gin.Default() vs gin.New()

```go
// Bad (本番): gin.Default() は Logger+Recovery が自動追加され設定を制御しにくい
r := gin.Default()

// Good (本番): gin.New() で明示的にミドルウェアを登録
r := gin.New()
r.Use(gin.Recovery())
r.Use(customLogger())    // 自前のログ設定
r.Use(CORSMiddleware())
```

## 依存関係の組み立て（main.go）

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
