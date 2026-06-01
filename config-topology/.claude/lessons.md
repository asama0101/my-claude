# lessons.md — config-topology

## build_topology.py TDD 実装 (2026-06-01)

### 実装した内容
- `scripts/build_topology.py` — 結線推論層（`build()` 関数 + CLI）
- `tests/test_build_topology.py` — 67 件のテスト（ゴールデン/ユニット/統合）

### ゴールデンテスト一致
- `parse_paths(sample-ios-r1.cfg, sample-junos-r2.conf)` → `build()` の出力が `examples/sample-topology.json` と完全一致した（即時）。

### 設計判断

1. **defaultdict によるサブネットグルーピング**: `ipaddress.ip_interface(ip).network` を文字列キーにすることで IPv4 の正規化が自動的に行われる。`10.0.0.1/30` と `10.0.0.2/30` は同じキー `10.0.0.0/30` に集約される。

2. **自己ループ除外の実装**: メンバー 2 の場合のみ `a_device != b_device` チェックを行う。メンバー >= 3 は segment として扱うため自己ループの概念がない（仕様通り）。

3. **BGP local_ip 解決**: `ipaddress.ip_address(neighbor_ip) in iface_net.network` で同一サブネット判定。結果はホスト部のみ（`str(iface_net.ip)`）。

4. **ID 採番の重複管理**: `counter: dict[str, int]` で基底 ID の出現回数を追跡。最初の出現は suffix なし、2 回目以降に `-2`, `-3`... を付与。

5. **CLI の generated_from**: `os.path.basename(p)` でパスからファイル名のみ取り出す。ゴールデン JSON に合わせた動作。

### 非自明な注意点
- `sorted(subnet_to_members.items())` でサブネット文字列の辞書順ソートをして links の出力順を決定性保証している。
- segment id の生成: `network_str.replace(".", "_").replace("/", "_")` で `.` と `/` を両方 `_` に変換。例: `192.168.1.0/24` → `192_168_1_0_24`、prefix は `seg-`。
- `_assign_device_ids` は同じ基底 ID（例 `device`）が複数あると counter を使って `-2`, `-3` を付与する。最初の出現のみ suffix なしなので順序依存に注意。

## build_topology.py バグ修正 TDD (2026-06-02)

### 修正内容と再発防止

1. **ID 採番の衝突バグ** (`_assign_device_ids`): counter で base ごとにカウントするだけでは、別 hostname が正規化後に既存 ID と衝突する（例: `["R1","R1-2","R1"]` → `r1-2` が重複）。`issued: set[str]` を追加し、`while candidate in issued` で衝突解消まで count を繰り上げるパターンが正しい。

2. **BGP `local_as=None` 誤判定** (`_determine_bgp_type`): `None != 65001` が True になるため `local_as=None` で `ebgp` に誤判定された。`peer_as is None or local_as is None` の条件を先に置いて `unknown` を返すことで解決。

3. **デッドコード `dev_id_to_interfaces`**: build() 内に定義・設定されていたが未参照。BGP 解決は `_resolve_local_ip(dev, ...)` が Device を直接受け取るため不要。削除しても全テスト通過。

4. **`build()` の `generated_from` basename 化**: CLI は既に basename を渡していたが、公開 API `build()` 自体が `os.path.basename()` を各要素に適用するようにすることで、フルパスが渡されてもホームディレクトリ構造が漏洩しない堅牢な設計になる。ゴールデンテストは既に basename 済みの値を渡しているため影響なし。

### 追加テスト（カバレッジ補完）
- `TestSelfLoopAndDuplicateIp.test_same_device_same_subnet_no_link_and_no_segment`: 同一機器の 2 IF が同一 /30 サブネットのとき links も segments も空であること（従来は links のみ検証）。
- `TestSelfLoopAndDuplicateIp.test_duplicate_ip_two_devices_no_extra_links`: 重複 IP 設定で links が増殖しないこと。
- `TestSelfLoopAndDuplicateIp.test_duplicate_ip_does_not_crash`: 重複 IP で例外が発生しないこと。
