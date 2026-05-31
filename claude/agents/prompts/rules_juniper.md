# Juniper JunOS レビュールール

ネットワーク作業手順書レビュー時に参照する Juniper 系のルール集。
syntax / consistency / procedure 系エージェントが必要に応じて Read して参照する。

## JunOS の基本モデル（commit ベース）

- 設定は **candidate config** に投入し、`commit` で初めて反映される。
- `commit confirmed <分>` を使うと、指定時間内に再 `commit` しないと自動ロールバック（**通信断時の保険**）。
- `rollback <n>` で過去設定に戻せる（`rollback 0` = 直近 commit 前）。

## 危険コマンド（CRITICAL）

| コマンド | リスク | 確認ポイント |
|---|---|---|
| `delete <hierarchy>`（上位階層の delete） | 配下設定の一括削除 | 対象階層が広すぎないか（例: `delete interfaces`） |
| `load override` | 設定全置換 | 既存設定の喪失 |
| `request system zeroize` | 工場出荷リセット | 原則手順書に出ない。あれば要厳重確認 |
| `commit`（`commit confirmed` でない） | 即時確定・誤設定が即反映 | 重要変更では `commit confirmed` 推奨 |

## 注意点（HIGH）

- `set` / `delete` の対象階層ミス（例: `delete interfaces ge-0/0/1` で IF 設定丸ごと削除）。
- `commit confirmed` 後の**確定 `commit` 漏れ**（時間経過で自動ロールバックし変更が消える）。
- `activate` / `deactivate` の付け忘れ。
- アドレス表記は CIDR（`192.168.1.1/24`）。Cisco のマスク表記と混在していないか。

## 推奨手順（procedure エージェント向け）

1. 作業前: `show configuration` / `show interfaces terse` で現状取得
2. 変更投入（candidate）
3. **`show | compare`** で差分確認（commit 前レビュー）
4. `commit confirmed <分>` で投入 → 疎通確認 → 問題なければ `commit`
5. ロールバック手順（`rollback 1` → `commit`）の明記

## 構文・表記の典型ミス

- `set` の階層パス誤り・タイプミス
- `commit check` による事前検証の記載漏れ
- ホスト名: `set system host-name <name>`
