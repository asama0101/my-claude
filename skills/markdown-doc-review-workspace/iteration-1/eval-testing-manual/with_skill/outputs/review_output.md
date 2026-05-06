## ドキュメントレビュー: docs/testing_manual.md

### 総合スコア

| 観点 | スコア | 概要 |
|---|---|---|
| 内容の正確性 | ★★★☆☆ | `date` コマンドの時刻フォーマットバグ・`design.md §0.x` 参照切れ・worker.py 行番号ずれ・docker コマンド不一致あり |
| 構成・読みやすさ | ★★★★☆ | 章立ては明快。付録 A の `§5.2 自動側` が本書内の §5.2 と混同しやすい |
| 記述漏れ・抜け穴 | ★★★★☆ | 大部分は丁寧。§5.7-D の `downgrade 0009` コマンドに関する補足が薄い |
| リンク・参照 | ★★★☆☆ | `docs/design.md §0.1` / `§0.4` が存在しないセクションへの参照 |

**指摘件数**: 🔴 重要 3件 / 🟡 中程度 3件 / 🟢 軽微 2件

---

### 指摘事項

#### 🔴 重要（誤り・手順不能・参照不能）

**#1 [内容の正確性]** 場所: §1.2 コードブロック（L159-160, L167-168）

`${DAY}0000` / `${DAY}0030` の時刻フォーマットが誤り。`gen_sample_data.py` の `_parse_date` は `%Y%m%d%H%M%S`（14桁）または `%Y%m%d`（8桁）を受け付ける。`DAY=$(date +%Y%m%d)` の値は8桁なので、`${DAY}0000` は12桁になり `%Y%m%d` に一致せず `%Y%m%d%H%M%S` でパースされる。この場合 Python の `strptime` は `YYYYMMDD00MM` と解釈し、`${DAY}0030` は `00:03:00`（03分）として誤パースされる（期待 `00:30:00`）。結果として §1.2 の手順では意図した "30分幅・7タイムスタンプ" が生成されず、1タイムスタンプのみになる。

→ 修正案:
```bash
DAY=$(date +%Y%m%d)
.venv/bin/python scripts/gen_sample_data.py \
  --start ${DAY}000000 --end ${DAY}003000 --subports 5 --flows-per-subport 3
```
あわせて L177 の WHERE 句も `'<DAY> 00:35:00+09'` → `'<DAY> 00:35:00+09'` は問題なし（35分でカバー可）。ただし `--end ${DAY}0030` の誤パース修正後、時刻範囲フィルタ `< '<DAY> 00:35:00+09'` は正しくなる。

**#2 [リンク・参照]** 場所: §4（P）冒頭 L620-621

`docs/design.md §0.1` / `docs/design.md §0.4` への参照が壊れている。`docs/design.md` はセクション `## 1. 概要・目的` から始まり、§0（§0.1、§0.4）は存在しない。`CLAUDE.md` には `docs/design.md §0` への言及があるが、対応するセクションが design.md にはない。

→ 修正案: 参照先を実在するセクションに変更するか削除する。スループット要件値はこの手順書の「システム全体規模（参照値）」テーブル（L625-636）に記載済みのため、`docs/design.md §0.x` への言及を削除するだけでも十分。

修正例:
```
- **正式仕様** = **6,004,000 行/区間 / 必要スループット ≈ 20,013 rows/sec**（300 装置 × 4,000 subport × 6,000,000 flow / 5 分 ÷ 300 秒）。`scripts/measure_perf*.sh` 群はこの値を判定基準にする
- **ストレステスト諸元** = `scripts/test_production_like.sh` = **25,000,000 行/区間 / 83,333 rows/sec**（仕様の **約 4 倍負荷**）。本番 SLA を超えるマージン確認用
```

**#3 [内容の正確性]** 場所: §5.7-D コードブロック（L1538）

§5.7-D で `0010 downgrade` 後の動作確認コマンドとして以下が記述されている:
```bash
docker compose run --rm app python -m src.ingest.worker
```
しかし `docker/Dockerfile` の `CMD` は `["uv", "run", "python", "-m", "src.ingest.worker"]` であり、コンテナ内の Python は `uv run` 経由でのみ正しく動作する（venv 有効化なしで `python` のみを呼ぶと依存ライブラリが解決されない可能性がある）。§1.5（L293）では正しく `docker compose run --rm app uv run python -m src.ingest.worker` と記述している。

→ 修正案:
```bash
docker compose run --rm app uv run python -m src.ingest.worker
```

---

#### 🟡 中程度（抜け穴・混乱の原因）

**#4 [内容の正確性]** 場所: §2.3 確認事項（L447）および §3.1（L436）

worker のログメッセージ記述が実装と不一致。ドキュメントは `skip (same hash)` 相当と記述しているが（§2.1 L397）、実装（`worker.py:119`）の実際のログは:
```
already ingested (hash match), skipping: {filename}
```
`skip (same hash)` という文字列はログには存在しない。運用担当者が `grep` で確認する際に一致しない。

→ 修正案: L397 を以下に変更:
```
- worker のログに `already ingested (hash match), skipping:` の INFO が出ていること
```

**#5 [構成・読みやすさ]** 場所: 付録 A（L1573）

「O-4 で 40 日前 chunk の `run_job` 実 drop を自動カバー（§5.2 自動側）」の `§5.2 自動側` が曖昧。本書の §5.2 は「CA 定義・refresh policy」であり retention 実動作とは無関係。実際には `testing_automated.md §5.2`（retention ポリシー実動作）を指す意図だが、文書名なしでは混乱を招く。

→ 修正案:
```
O-4 で 40 日前 chunk の `run_job` 実 drop を自動カバー（`testing_automated.md` §5.2）。設定値の存在確認は §5.5
```

**#6 [内容の正確性]** 場所: §2.3 stable check 参照（L451）と §3.2 復旧手順（L607）

`worker.py:189-209` / `worker.py:189-212` の行番号参照が実装と1行ずれている。実際のコードでは:
- stable check ループ: 行 190-208（189 は空行）
- processing_dir glob ループ: 行 210-215

また `worker.py:245-261` (`_cleanup_error_dir` の参照) も実際のコードでは行 248-264（3行ずれ）。

同様に本文内の参照一覧:
| ドキュメント記載 | 実際の行範囲 | 内容 |
|---|---|---|
| `worker.py:189-209` | 190-208（189は空行）| stable check ループ |
| `worker.py:189-212` | 190-215 | stable check + processing_dir glob |
| `worker.py:245-261` | 248-264 | `_cleanup_error_dir` |

これらは現時点では軽微な不一致だが、worker.py に変更が加わった際に参照先がさらにずれるリスクがある。

→ 修正案: 行番号参照を実際の行番号に修正するか、行番号を削除して関数名だけで参照する（`_cleanup_error_dir` など）方式に変更する。

---

#### 🟢 軽微（改善提案・スタイル）

**#7 [記述漏れ・抜け穴]** 場所: §1.5 Docker Compose 経由取り込み（L284-299）

`docker compose run --rm app` は `profiles: ["worker"]` 指定のサービスのため、通常の `docker compose up -d` では起動しない。`--profile worker` を明示しなくても `run` は動作するが、初めて実施する読者向けに「app サービスは profiles=worker のため `docker compose up` には含まれない」旨の注釈があると親切。

→ 修正案（任意）: 確認事項の冒頭に以下を追加:
```
> `app` サービスは `profiles: ["worker"]` のため `docker compose up -d` では起動しない。`docker compose run --rm app` は profiles に関わらず実行可能。
```

**#8 [記述漏れ・抜け穴]** 場所: §3.2 ディスク満杯再現方法（L557-587）

`sudo mkdir -p ./incoming/error` の後に `sudo mount -o loop ...` しているが、`./incoming/error` が既存ディレクトリの場合 `mount` はその中身を隠す。試験後の後始末（L582-587）で `sudo rmdir ./incoming/error` を実行しているが、`incoming/error` 内に既存ファイルがあると `rmdir` が失敗する（non-empty directory）。事前に `ls ./incoming/error/` で空であることを確認するか、`rm -rf` で代替するよう補足が必要。

→ 修正案: マウント前チェックを追加:
```bash
# error/ が空であることを確認（既存ファイルは後始末で取り出せなくなるため）
ls ./incoming/error/  # 空であること
sudo mount -o loop ./tmp_fullfs/disk.img ./incoming/error
```

---

**手動確認が必要な外部リンク**: なし（外部 URL の記載なし）

---

修正を適用しますか？
番号を指定（例: 1,3,5）、「全部」、または「スキップ」を入力してください。
