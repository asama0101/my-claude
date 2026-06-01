---
name: config-topology
description: >-
  NW機器のConfig（Cisco IOS/IOS-XE running-config、Juniper JunOS set形式）から
  ネットワーク構成図（トポロジー図）を生成する。複数機器のConfigを束ね、IP/サブネット一致で
  機器間リンクを自動推論し、中間JSON(topology.json)を経てインタラクティブHTML構成図を出力する。
  「構成図を作って」「トポロジー図を描いて」「このconfigから構成を可視化」「ネットワーク図にして」
  「configから結線を起こして」「機器の接続関係を図にして」等の発言、または inbox/ にconfig
  ファイル(.cfg/.conf/.txt)が置かれているときは必ずこのスキルを使う。Excel手順書のレビューや
  パラメータ入力ではなく、Config(テキスト)からのネットワーク図化が対象。
---

# config-topology — Config からネットワーク構成図を生成

ネットワーク機器の running-config（テキスト）を入力に、機器・インターフェース・IP・機器間リンク・
ルーティングを読み取り、中間表現 `topology.json` を経て**インタラクティブなHTML構成図**を生成する。

- **入力**: Cisco IOS / IOS-XE running-config、Juniper JunOS（set 形式）。複数機器を一括。
- **出力**: `topology.json`（ベンダー中立の中間表現）＋ `topology.html`（自己完結・`file://` で開ける）。
- **依存**: Python 3 標準ライブラリのみ（`python3` を使う。`python` エイリアスは無い前提）。外部パッケージ・venv 不要。

スキルのルート（このファイルがある場所）を以降 `$SKILL` と書く。実行前にシェル変数を設定しておく:
```bash
SKILL="<このスキルの絶対パス>"   # 例: /path/to/config-topology
OUT="$SKILL/runs/$(date +%Y-%m-%d_%H%M)_<案件名>"   # 成果物の出力先（Phase 4 でアーカイブ）
mkdir -p "$OUT/inputs"
```

> **注意（機密情報）**: config の `interface description` 等に管理者が誤って community 文字列やパスワードを書いている場合、その値はそのまま `topology.json`・`topology.html` に出力される（パーサは `password`/`secret`/`snmp community` 行自体はパースしないが description 等の自由記述は通す）。生成物を共有・保存する際は取り扱いに注意すること。

## アーキテクチャ（3層パイプライン）

```
inbox/*.{cfg,conf,txt}
   │  scripts/parse_configs.py     ベンダー自動判定 → 正規化モデル(Device)
   ▼
   │  scripts/build_topology.py    IP/サブネット一致でリンク・セグメント推論、BGP対向解決
   ▼
topology.json                       ← 中間表現（正確性が最優先）
   │  scripts/render_topology.py
   ▼
topology.html                       SVG+バニラJS（ズーム/パン/ホバー強調/レイヤートグル）
```

各層は単一責務で、境界は JSON。詳細仕様は必要に応じて参照:
- `references/schema.md` — `topology.json` スキーマと ID 採番規則
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

### Phase 2: topology.json の生成（最優先で正確に）
```bash
python3 "$SKILL/scripts/build_topology.py" <paths...> -o "$OUT/topology.json"
# paths 省略時は inbox/ を自動走査
```
- 生成された `topology.json` を**必ず目視確認**する。特に:
  - 機器・IF・IP が漏れなく拾えているか（特に description / shutdown / loopback）。
  - `links` と `segments` が意図通りか（2機器=link、3機器以上=segment、単独=スタブ）。
  - `routing.bgp` の `type`（ebgp/ibgp）と `local_ip` 解決が妥当か。
- 取りこぼしや誤りがあれば、まずパース/推論の問題か config の特殊記法かを切り分ける。

### Phase 3: HTML 構成図の描画
```bash
python3 "$SKILL/scripts/render_topology.py" "$OUT/topology.json" -o "$OUT/topology.html"
```
- ズーム（ホイール）/パン（ドラッグ）/ホバー強調/レイヤートグル（物理レイヤー ＋ `routing` の各プロトコル＝
  BGP・OSPF・static …。トグルは `routing` のキーから動的生成されるので将来プロトコルを足しても自動で増える）/
  F=全体表示・Esc=リセット が動く自己完結 HTML。

### Phase 4: runs/ へアーカイブ
再現性のため、実行ごとに成果物を退避する（`$OUT` は冒頭で設定済み）:
```bash
cp <入力configs> "$OUT/inputs/"     # 入力スナップショット
# Phase 2,3 の出力（topology.json / topology.html）は最初から $OUT に書いているので追加作業は不要
```

### Phase 5: HTML 成果物のクロスレビュー（提示前に必須）
HTML 構成図は提示前に**サブエージェントで敵対的にクロスレビュー**する（topology.json と HTML を突合し、
ノード/リンク/ルーティングの欠落・誤接続・ラベル不整合・描画崩れを洗い出す）。指摘があれば修正してから提示する。

## スコープ（v1）
- **対象**: 機器・IF・IP・サブネット結線（コア）＋ ルーティング（BGP / OSPF / static）。
- **スコープ外（将来拡張）**: VLAN/L2・SVI、HSRP/VRRP・LAG/Port-channel、CDP/LLDP 由来リンク、
  NX-OS/Arista 等の追加ベンダー、Mermaid/Graphviz 併出力、フロー選択等のリッチUX。

## 拡張の指針
- **ベンダー追加**: `scripts/parsers/<vendor>.py` に `detect`/`parse` を実装し registry に登録するだけ
  （`references/vendor-parsing.md` の手順）。スキーマ・build・render は変更不要。
- **プロトコル/レイヤー追加**: `topology.json` の `routing` にキーを足す、または `devices[].sections` に
  汎用テーブルを足す。レンダラーは `routing` のキーを走査してレイヤートグルを自動生成するので加算的に対応。
- **結線手段追加**: `links[].kind` に新しい由来（例 `neighbor-cdp`）を足す。

## 検証
```bash
cd "$SKILL" && python3 -m pytest tests/ -q          # ユニットテスト（パーサ/推論/描画）
# E2E: examples を使った通し確認
python3 scripts/build_topology.py examples/sample-ios-r1.cfg examples/sample-junos-r2.conf -o /tmp/t.json
python3 scripts/render_topology.py /tmp/t.json -o /tmp/t.html   # /tmp/t.html を file:// で開く
```
`examples/sample-topology.json` は 2 つのサンプル config から生成される期待出力（ゴールデン）。
