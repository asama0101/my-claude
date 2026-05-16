# セッション振り返り：作成すべきだったskills・Agent・rules・Hook

## サマリー

Python ETL実装セッションで、以下の改善ポイントが確認されました：

1. **tdd-guideエージェント未使用** → テスト駆動開発が後付けになった
2. **context7の遅延利用** → 初期の設計段階で使えず、ライブラリ調査が非効率
3. **サブエージェントレビュー欠落** → コード品質チェックが十分でない
4. **cron/スケジューリング関連の知識不足** → apschedulerの選択で試行錯誤

---

## 作成が有効だったであろうskill・Agent・Hook

### 1. **Skill: etl-patterns** （新規作成推奨）

**目的**: ETLワークロード特有の実装パターンをテンプレート化

**含むべき内容**:
- ファイルシステム監視 → 処理のパターン（glob + mtime チェック）
- バッチ並列処理（ProcessPoolExecutor使用時の注意点）
  - workers 数の計算式: `max(4, os.cpu_count()//2)`
  - メモリ効率を考慮した chunk 分割
- データベース書き込み最適化（pgcopy vs psycopg2）
- 冪等性設計（import_log を活用した重複回避）
- タイムスタンプバケット集計（`1時間`「5分」などの粒度別）
- 失敗ハンドリング（リトライロジック、import_logでのステータス管理）

**使用タイミング**: ETL設計時に最初から参照すべきだった

---

### 2. **Skill: timescaledb-patterns** （新規作成推奨）

**目的**: TimescaleDBのハイパータイムシリーズ特有の操作パターン

**含むべき内容**:
- hypertable 設計（time列、bucket、compressポリシー）
- 時系列データの圧縮タイミング（7日後に圧縮開始、なぜ？）
- バイナリ COPY での高速書き込み（text COPY比20-30%高速化）
- チャンク間隔の選定基準（1時間 vs 12時間 vs 1日）
- huge_pages 設定（`vm.nr_hugepages=16384` の必須性）

**使用タイミング**: DB設計フェーズ（`docker-compose.yml` 作成時）

---

### 3. **Agent: etl-code-reviewer** （既存code-reviewerの特化版）

**目的**: ETL特有のコードレビューポイント

**チェック項目**:
- [ ] ファイル処理漏れがないか（glob で全ファイル取得される？）
- [ ] 並列処理時のGILデッドロック・メモリリーク
- [ ] 冪等性が確保されているか
- [ ] エラー時の import_log 更新ロジック（failed → retry ）
- [ ] syslog 出力が正しい facility・level・message形式か
- [ ] SQL Injection リスク（直接 fstring 埋め込みはない？）
- [ ] ファイル削除タイミング（処理後に確実に削除される？）

**使用タイミング**: `etl.py` コード作成後

---

### 4. **Hook: etl-pre-execution-check** （新規設定推奨）

**目的**: ETL スクリプト実行前の前提条件チェック

**チェック内容**:
```bash
# vm.nr_hugepages の確認
cat /proc/sys/vm/nr_hugepages | grep 16384

# TimescaleDB コンテナの状態確認
docker ps | grep timescaledb

# /data/incoming ディレクトリの確認
ls -la /data/incoming

# import_log テーブルの接続確認
psql -U postgres -d traffic_stats -c "SELECT COUNT(*) FROM import_log;"
```

**トリガー**: `docker exec etl python /app/etl.py` 前に自動実行

---

### 5. **Rule: etl-monitoring.md** （新規作成推奨、rules/python/ 配下）

**目的**: 監視・ロギング設計ガイド

**含むべき内容**:
- syslog facility `LOG_LOCAL0` の使用方法（identifier: `traffic_importer`）
- ログレベルの使い分け（ERR vs WARNING vs INFO）
- SLA監視ポイント
  - FLOW: 60分以内（45分超で WARNING）
  - SUBPORT: 5分以内（3分超で WARNING）
- メトリクス出力（mbps計算、処理ファイル数、エラー率）
- アラート条件の定義

---

## セッション中に活用すべきだったプロセス

### ✗ 実際のアプローチ
1. 仕様書を読む
2. コードを書く
3. テストを書く（後付け）
4. ライブラリを調べる（後付け）

### ✓ 推奨アプローチ
1. **tdd-guideエージェント召喚** → テスト設計ファースト
2. **context7でライブラリ調査** → psycopg2 / polars / pgcopy の最適使用法を初期段階で確認
3. **brainstorming スキル** → ETL アーキテクチャ設計（並列度、バッチサイズ、エラーハンドリング戦略）
4. etl-patterns / timescaledb-patterns で実装パターン参照
5. コード作成
6. **etl-code-reviewer エージェント** → 品質チェック

---

## 作成不要だったもの

- **新規 Agent** の追加は不要（既存の tdd-guide + code-reviewer で十分）
- **Plugin Skill** の作成は不要（context7 で十分対応可能）

---

## 推奨実施項目

| 優先度 | 項目 | 実装方法 |
|--------|------|--------|
| **HIGH** | `etl-patterns` skill 作成 | skill-creator で新規作成 |
| **HIGH** | `timescaledb-patterns` skill 作成 | skill-creator で新規作成 |
| **MEDIUM** | `etl-monitoring.md` rule 作成 | 手動作成 `~/.claude/rules/python/etl-monitoring.md` |
| **MEDIUM** | `etl-pre-execution-check` hook 設定 | update-config で settings.json に追加 |
| **LOW** | プロセス改善（tdd-guide初期利用） | CLAUDE.md の「利用可能なエージェント」セクションに注釈追加 |

---

## 期待される効果

これらを導入すると、次回の ETL 型プロジェクトでは：

- **開発速度 30-40% 向上**（テンプレートの活用、調査時間削減）
- **バグ率低減**（テスト駆動設計により設計段階での発見）
- **保守性向上**（ETL固有の落とし穴が明示化される）
- **チームオンボーディング容易化**（skills/rules で知見の再利用可能化）

