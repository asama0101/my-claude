---
name: config-topology
description: >-
  NW機器のConfig（Cisco IOS/IOS-XE running-config、Juniper JunOS set形式）から
  ネットワーク構成図（トポロジー図）を生成する。複数機器のConfigを束ね、IP/サブネット一致で
  機器間リンクを自動推論し、中間表現（レイヤー別YAML）を経てインタラクティブHTML構成図を出力する。
  「構成図を作って」「トポロジー図を描いて」「このconfigから構成を可視化」「ネットワーク図にして」
  「configから結線を起こして」「機器の接続関係を図にして」等の発言、または inbox/ にconfig
  ファイル(.cfg/.conf/.txt)が置かれているときは必ずこのスキルを使う。Excel手順書のレビューや
  パラメータ入力ではなく、Config(テキスト)からのネットワーク図化が対象。
---

# config-topology — Config からネットワーク構成図を生成

ネットワーク機器の running-config（テキスト）を入力に、機器・インターフェース・IP・機器間リンク・
ルーティングを読み取り、中間表現（**レイヤー別 YAML**）を経て**インタラクティブなHTML構成図**を生成する。

- **入力**: Cisco IOS / IOS-XE running-config、Juniper JunOS（set 形式）。複数機器を一括。
- **出力**: `topology/`（**ベンダー中立のレイヤー別 YAML 正本**＝`_meta.yaml`/`devices.yaml`/`physical.yaml`/`routing.*.yaml`）＋ `topology.html`（自己完結・`file://` で開ける）。中間表現は YAML で、人手編集して再描画できる（round-trip）。
- **依存**: Python 3 ＋ **PyYAML**（`pip install -r requirements.txt`）。`python3` を使う（`python` エイリアスは無い前提）。
  ```bash
  python3 -m venv "$SKILL/.venv" && "$SKILL/.venv/bin/pip" install -r "$SKILL/requirements.txt"
  # 以降 python3 は "$SKILL/.venv/bin/python3" を使う（PyYAML が import 可能なら system python3 でも可）
  ```

スキルのルート（このファイルがある場所）を以降 `$SKILL` と書く。実行前にシェル変数を設定しておく:
```bash
SKILL="<このスキルの絶対パス>"   # 例: /path/to/config-topology
OUT="$SKILL/runs/$(date +%Y-%m-%d_%H%M)_<案件名>"   # 成果物の出力先（Phase 4 でアーカイブ）
mkdir -p "$OUT/inputs"
```

> **注意（機密情報）**: config の `interface description` 等に管理者が誤って community 文字列やパスワードを書いている場合、その値はそのまま 層別 YAML・`topology.html` に出力される（パーサは `password`/`secret`/`snmp community` 行自体はパースしないが description 等の自由記述は通す）。生成物を共有・保存する際は取り扱いに注意すること。

## アーキテクチャ（3層パイプライン）

```
inbox/*.{cfg,conf,txt}
   │  scripts/parse_configs.py     ベンダー自動判定 → 正規化モデル(Device)
   ▼
   │  scripts/build_topology.py    IP/サブネット一致でリンク・セグメント推論、BGP対向解決
   ▼
topology/  (層別YAML正本)            ← 中間表現（正確性が最優先・人手編集可）
   │  scripts/topology_io.py        dump/load（層別YAML ⇄ topology dict・参照整合検証）
   │  scripts/render_topology.py
   ▼
topology.html                       SVG+バニラJS（ズーム/パン/ホバー強調/レイヤー別ビュー）
```

各層は単一責務で、境界は層別 YAML（`scripts/topology_io.py` が dict と相互変換）。詳細仕様は必要に応じて参照:
- `references/schema.md` — レイヤー別 YAML レイアウト・topology スキーマと ID 採番規則
- `references/link-inference.md` — サブネット結線推論と BGP 対向解決のルール
- `references/vendor-parsing.md` — ベンダー別パース要点と**新ベンダー追加手順**

## 実行手順

### Phase 1: 入力の収集とベンダー確認
1. ユーザーが config ファイルを `inbox/` に置いているか、パスを指定しているか確認する。
   - `inbox/` 方式: `$SKILL/inbox/` に置かれた `*.cfg *.conf *.txt` を対象にする。
   - パス指定方式: ユーザーが渡したファイル/ディレクトリ/glob を対象にする。
2. ベンダー判定の妥当性を素早く確認する（任意・デバッグ用）:
   ```bash
   python3 "$SKILL/scripts/parse_configs.py" <paths...>   # 正規化 devices を JSON で確認
   ```
   未知ベンダーのファイルはスキップされ stderr に警告が出る。意図せずスキップされていないか見る。

### Phase 2: 層別 YAML（中間表現）の生成（最優先で正確に）
```bash
python3 "$SKILL/scripts/build_topology.py" <paths...> -o "$OUT/topology"
# paths 省略時は inbox/ を自動走査。-o は出力ディレクトリ（既定 topology/）
# → $OUT/topology/ に _meta.yaml / devices.yaml / physical.yaml / routing.*.yaml を生成
```
- 生成された層別 YAML を**必ず目視確認**する（YAML なので読みやすく、必要なら手で補正可）。特に:
  - `devices.yaml`: 機器・IF・IP が漏れなく拾えているか（特に description / shutdown / loopback）。
  - `physical.yaml`: `links` と `segments` が意図通りか（2機器=link、3機器以上=segment、単独=スタブ）。
  - `routing.bgp.yaml`: `type`（ebgp/ibgp）と `local_ip` 解決が妥当か。
- 手で編集した場合、読込時に **ID 参照整合が検証**される（dangling 参照はファイル・フィールド・値を示すエラー）。
- 取りこぼしや誤りがあれば、まずパース/推論の問題か config の特殊記法かを切り分ける。

### Phase 3: HTML 構成図の描画
```bash
python3 "$SKILL/scripts/render_topology.py" "$OUT/topology" -o "$OUT/topology.html"
# 入力は層別YAMLディレクトリ（topology_io.load_topology が参照整合を検証して dict 復元）
```
- **レイヤー別ビュー切替**（上部タブ）: `Physical`（L1物理＝機器+リンク+セグメント）/ `L3`（サブネットでグルーピング+routing隣接）/
  プロトコル別（`BGP`・`OSPF` … `routing` キーから動的生成）。ビューごとに配置が変わり、機器数が多くても見やすい。
- **検索ボックス**: hostname / IP で現在ビュー内のノードを絞り込み（淡色化）。
- レイアウトは**決定的 force-directed**（同一 topology → 同一HTML）＋**動的キャンバス**（台数に応じて拡大、〜150台目安）。
- ズーム（ホイール）/パン（ドラッグ）/ホバー強調/レイヤートグル（routingオーバーレイ表示制御）/
  F=全体表示・Esc=リセット が動く自己完結 HTML。

### Phase 4: runs/ へアーカイブ
再現性のため、実行ごとに成果物を退避する（`$OUT` は冒頭で設定済み）:
```bash
cp <入力configs> "$OUT/inputs/"     # 入力スナップショット
# Phase 2,3 の出力（topology/ 層別YAML ＋ topology.html）は最初から $OUT に書いているので追加作業は不要
```

### Phase 5: HTML 成果物のクロスレビュー（提示前に必須）
HTML 構成図は提示前に**サブエージェントで敵対的にクロスレビュー**する（層別 YAML(topology) と HTML を突合し、
ノード/リンク/ルーティングの欠落・誤接続・ラベル不整合・描画崩れを洗い出す）。指摘があれば修正してから提示する。

## スコープ（v1）
- **対象**: 機器・IF・IP・サブネット結線（コア）＋ ルーティング（BGP / OSPF / static）。
- **スコープ外（将来拡張）**: VLAN/L2・SVI、HSRP/VRRP・LAG/Port-channel、CDP/LLDP 由来リンク、
  NX-OS/Arista 等の追加ベンダー、Mermaid/Graphviz 併出力、フロー選択等のリッチUX。

## 拡張の指針
- **ベンダー追加**: `scripts/parsers/<vendor>.py` に `detect`/`parse` を実装し registry に登録するだけ
  （`references/vendor-parsing.md` の手順）。スキーマ・build・render は変更不要。
- **プロトコル/レイヤー追加**: topology の `routing` にキーを足す（新 `routing.<proto>.yaml` 層が増える）、または
  `devices[].sections` に汎用テーブルを足す。レンダラーは `routing` のキーを走査してレイヤー別ビュー/トグルを自動生成するので加算的に対応。
- **結線手段追加**: `links[].kind` に新しい由来（例 `neighbor-cdp`）を足す。

## 検証
```bash
cd "$SKILL" && python3 -m pytest tests/ -q          # ユニットテスト（パーサ/推論/描画）
# E2E: examples を使った通し確認
python3 scripts/build_topology.py examples/configs/sample-ios-r1.cfg examples/configs/sample-junos-r2.conf -o /tmp/topo
python3 scripts/render_topology.py /tmp/topo -o /tmp/t.html     # /tmp/t.html を file:// で開く
```
`examples/topology/`（層別 YAML）は 2 つのサンプル config から生成される期待出力（ゴールデン）。
