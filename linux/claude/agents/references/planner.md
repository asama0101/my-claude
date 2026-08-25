# 計画の詳細例集

> planner エージェント用のオンデマンド参照ファイル。ADR が必要な規模の設計判断や、詳細レベルの完全な計画を求められたときに Read する。
> 2つの例を収録する: (1) 詳細レベルを示す完全な実装計画例、(2) ADR テンプレートと記入例。

---

## 例1: FastAPI JWT 認証の完全な実装計画

期待される詳細レベルを示す完全な計画:

```markdown
# 実装計画: FastAPI JWT 認証

## 概要
FastAPI アプリケーションに JWT ベースの認証を追加する。
ユーザーはメールアドレスとパスワードでログインし、アクセストークンとリフレッシュトークンを取得する。
保護されたエンドポイントは依存性注入で認証を強制する。

## 要件
- POST /auth/register — ユーザー登録（メール・パスワード）
- POST /auth/login — ログインしてトークンペアを返す
- POST /auth/refresh — リフレッシュトークンでアクセストークンを更新
- Depends(get_current_user) による保護エンドポイントのガード

## アーキテクチャ変更
- 新テーブル: `users`（id・email・hashed_password・created_at）
- 新ファイル: `src/auth/router.py` — 認証エンドポイント
- 新ファイル: `src/auth/service.py` — トークン生成・検証ロジック
- 新ファイル: `src/auth/dependencies.py` — `get_current_user` 依存性
- 新ファイル: `src/auth/schemas.py` — Pydantic リクエスト/レスポンスモデル
- 新マイグレーション: `alembic/versions/001_create_users.py`

## 実装ステップ

### フェーズ 1: データベースとスキーマ（2ファイル）
1. **users テーブルのマイグレーションを作成** (File: alembic/versions/001_create_users.py)
   - アクション: email に UNIQUE 制約付きで users テーブルを作成
   - 理由: 認証の基盤となるデータ層を先に確立する
   - 依存関係: なし
   - リスク: Low

2. **Pydantic スキーマを定義** (File: src/auth/schemas.py)
   - アクション: RegisterRequest・LoginRequest・TokenResponse を定義
   - 理由: 型安全なリクエスト/レスポンスの契約を確立する
   - 依存関係: なし
   - リスク: Low

### フェーズ 2: ビジネスロジック（2ファイル）
3. **認証サービスを実装** (File: src/auth/service.py)
   - アクション: bcrypt でパスワードをハッシュ化、python-jose で JWT を生成・検証
   - 理由: ルーターから認証ロジックを分離する
   - 依存関係: ステップ 1〜2
   - リスク: High — ハッシュ化とトークンの有効期限設定が重要

4. **get_current_user 依存性を作成** (File: src/auth/dependencies.py)
   - アクション: Authorization ヘッダーから Bearer トークンを検証し User を返す
   - 理由: 保護エンドポイントに再利用可能な認証ガードを提供する
   - 依存関係: ステップ 3
   - リスク: Medium — 期限切れ/無効トークンの 401 エラー処理

### フェーズ 3: エンドポイント（1ファイル）
5. **認証ルーターを実装** (File: src/auth/router.py)
   - アクション: /register・/login・/refresh エンドポイントを実装し app に include_router
   - 理由: 認証フローをユーザーに公開する
   - 依存関係: ステップ 2〜4
   - リスク: Low

## テスト戦略
- ユニットテスト: パスワードハッシュ化・JWT 生成・トークン検証（src/tests/test_auth_service.py）
- 統合テスト: 全エンドポイント（正常系・異常系）（src/tests/test_auth_router.py）
- フィクスチャ: pytest-asyncio + httpx.AsyncClient + テスト用 DB セッション

## リスクと軽減策
- **リスク**: リフレッシュトークンの再利用（リプレイ攻撃）
  - 軽減策: DB にリフレッシュトークンを保存し、使用後に無効化する
- **リスク**: SECRET_KEY のハードコード
  - 軽減策: Pydantic Settings で環境変数から読み込み、.env.example に記載

## 成功基準
- [ ] 登録・ログイン・リフレッシュが正常に動作する
- [ ] 無効/期限切れトークンで 401 が返る
- [ ] 保護エンドポイントがトークンなしで 401 を返す
- [ ] パスワードが DB に平文で保存されない
- [ ] pytest カバレッジ 80%以上
```

---

## 例2: ADR（アーキテクチャ決定記録）テンプレートと記入例

重要なアーキテクチャ上の決定には ADR を作成する。各決定について
メリット/デメリット/検討した代替案/決定と根拠を文書化する:

```markdown
# ADR-001: ベクトル類似度検索に Redis を採用

## コンテキスト
アプリ機能としてベクトル類似度検索が必要で、埋め込みベクトルを保存・近傍クエリする必要がある。低レイテンシ（10ms 未満）が要件。

## 決定
ベクトル検索機能を持つ Redis Stack を使用する。

## 結果

### プラス
- 高速なベクトル類似度検索（10ms 未満）
- 組み込み KNN アルゴリズム
- シンプルなデプロイ
- 100K ベクトルまで良好なパフォーマンス

### マイナス
- インメモリストレージ（大規模データセットでは高コスト）
- クラスタリングなしでは単一障害点
- コサイン類似度に限定

### 検討した代替案
- **PostgreSQL pgvector**: 低速だが永続ストレージ
- **Pinecone**: マネージドサービス、高コスト
- **Weaviate**: 機能が多い、セットアップが複雑

## ステータス
承認済み

## 日付
2025-01-15
```
