---
paths:
  - "**/handler/**/*.go"
  - "**/handlers/**/*.go"
  - "**/routes/**/*.go"
  - "**/api/**/*.go"
  - "**/server/**/*.go"
  - "**/middleware/**/*.go"
---
# Gin ルール

Gin プロジェクトでは一般的な Go ルールと組み合わせて使用する。

## 構造

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

## ハンドラー構造体（DI）

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

## リクエストバインドとバリデーション

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

## レスポンス

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

## ミドルウェア

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

## セキュリティ

- CORS オリジンは環境ごとに設定する（`github.com/gin-contrib/cors`）
- ワイルドカードオリジンと認証情報付き CORS を組み合わせない
- JWT の有効期限・発行者・アルゴリズムを検証する
- 認証や書き込みが多いエンドポイントにレート制限を設ける（`github.com/ulule/limiter`）
- ログから Authorization ヘッダー・トークン・パスワードを除外する

## テスト

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
