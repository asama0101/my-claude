---
paths:
  - "**/*.go"
---
# Go コーディングスタイル

## 標準

- **Effective Go** に従う
- すべてのコードを `gofmt` / `goimports` でフォーマットする

## 基本原則

### KISS（シンプルに保つ）

- 実際に動く最もシンプルな解決策を選ぶ
- 早すぎる最適化を避ける
- 巧みさより明確さを優先する

### DRY（繰り返しを避ける）

- 繰り返されるロジックは共有関数やユーティリティに抽出する
- 繰り返しが実際に発生した時に抽象化を導入する（憶測ではなく）

### YAGNI（今必要なものだけ作る）

- 必要になる前に機能や抽象化を作らない
- シンプルに始め、必要になってからリファクタリングする

## 命名規則

- **エクスポート**: `PascalCase`（例: `UserRepository`、`GetUser`）
- **非エクスポート**: `camelCase`（例: `userID`、`parseToken`）
- **定数 (iota)**: `ALL_CAPS` は避ける。エクスポート定数は `PascalCase` が Go 標準
- **パッケージ名**: 小文字・単一単語・アンダースコア禁止（例: `userstore` → `users`）
- **インターフェース**: 単一メソッドなら `-er` サフィックス（例: `Reader`、`Writer`、`Stringer`）
- **bool 変数**: `is`、`has`、`should`、`can` プレフィックスを優先する

## エラーハンドリング（重要）

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

## インターフェース

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

## ファイル構成

多くの小さなファイル > 少ない大きなファイル:
- 通常 200〜400 行、最大 800 行
- タイプ別ではなく機能/ドメイン別に整理する

## イミュータビリティ

- 値型（`struct` の値渡し）を優先する
- ポインタは所有権の明確化が必要な時か、大きな構造体のコピーを避ける時のみ使う
- フィールドを直接変更するメソッドには `Mutate`/`Set` など変更を示す名前をつける

## 入力バリデーション

- システム境界でバリデーションを行う
- Gin を使う場合は struct タグ (`binding:"required"`) で宣言的にバリデーション
- 明確なエラーメッセージで早期に失敗させる

## フォーマット

```bash
gofmt -w .
goimports -w .
golangci-lint run
go vet ./...
```

## 避けるべきコードの臭い

### `panic` の乱用

- 初期化失敗（サーバー起動不能）以外で `panic` を使わない
- 通常フローでは `error` を返す

### 深いネスト

- ロジックが積み重なったら早期リターンを優先する

### マジックナンバー

- 意味のある閾値・遅延・制限には名前付き定数を使用する

```go
const maxRetries = 3
const requestTimeout = 30 * time.Second
```

## コード品質チェックリスト

作業を完了とマークする前に:
- [ ] コードが読みやすく適切に命名されている
- [ ] 関数が小さい（50行未満）
- [ ] ファイルが集中している（800行未満）
- [ ] 深いネストがない（4レベル超）
- [ ] すべてのエラーを処理している（`_` で無視していない）
- [ ] ハードコードされた値がない（定数または設定を使用）
- [ ] `panic` は初期化フロー以外で使っていない

## 参考

スキル: `go-patterns` で包括的な Go イディオムとパターンを参照。
