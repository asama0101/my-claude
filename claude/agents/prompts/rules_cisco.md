# Cisco IOS / IOS-XE / NX-OS レビュールール

ネットワーク作業手順書レビュー時に参照する Cisco 系のルール集。
syntax / consistency / procedure 系エージェントが必要に応じて Read して参照する。

## 危険コマンド（CRITICAL: 実行で通信断・設定消失のおそれ）

| コマンド | リスク | 確認ポイント |
|---|---|---|
| `write erase` / `erase startup-config` | 起動設定の全消去 | 手順書に存在する場合は意図と復旧手順を必須確認 |
| `reload`（`reload in` でない即時 reload） | 即時再起動・通信断 | `reload in <分>` + `reload cancel` 退避があるか |
| `delete flash:...` / `format flash:` | ファイル/フラッシュ消去 | バックアップ取得後か |
| `no router ospf` / `no router bgp` 等 process 削除 | ルーティング全断 | 影響範囲・代替経路を確認 |
| `clear ip route *` / `clear arp` | 一時的通信断 | メンテ時間帯か |
| `default interface <if>` | IF 設定の初期化 | 既存設定の喪失 |

## 注意コマンド（HIGH: 順序・対象を誤ると影響大）

- `shutdown` / `no shutdown`: 対象 IF が稼働中アップリンクでないか。`shutdown` で意図せぬ通信断。
- `switchport trunk allowed vlan <list>`: `add` を付けないと**既存許可 VLAN を上書き**（`switchport trunk allowed vlan add 100` が安全）。
- `ip address` 変更: 既存セッション・管理経路を切る可能性。OOB/コンソール経路の確保。
- `spanning-tree` 関連変更: ループ・再収束による瞬断。
- NX-OS の `copy running-config startup-config`（= `write memory`）漏れ: 再起動で設定喪失。

## 推奨手順（procedure エージェント向け）

1. 作業前: `show running-config` / `show ip interface brief` / `show version` 等で**現状取得（エビデンス）**
2. 変更前に **`copy running-config flash:backup-<date>.cfg`** でバックアップ
3. 変更投入
4. 作業後: 投入結果の確認コマンド（`show ...`）で**事後確認**
5. **保存**: `copy running-config startup-config`（`write memory`）
6. **ロールバック手順**の明記（`configure replace flash:backup-....cfg` 等）

## 構文・表記の典型ミス

- `ip address` のサブネットマスク表記（255.255.255.0 形式）と prefix 表記の混在
- インタフェース名の機種差（`GigabitEthernet0/1` vs `Gi0/1` vs NX-OS の `Ethernet1/1`）
- `enable` / `configure terminal` モード遷移の記載漏れ
- VLAN 作成（`vlan 100`）前にアクセスポート割当（`switchport access vlan 100`）している順序ミス
