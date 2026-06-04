# lessons.md — my-claude プロジェクト固有の技術的知見

## config-topology HTML レンダラー TDD 実装（2026-06-01）

### 概要
`render_topology.py` を標準ライブラリのみ（外部依存なし）で新規 TDD 実装。pytest 33テスト全パス、render_topology.py カバレッジ 87%。

### 重要な知見

- **`<script type="application/json">` 内の `</script>` は必ずエスケープ**: `topology_json.replace("</", "<\\/")` で埋め込み JSON 内の `</script>` がブラウザに閉じタグと解釈されるのを防ぐ。
- **決定論的レイアウト**: SVG ノード座標は機器 ID をソートして円形配置。Math.random() や time を使わないことが TDD でのスナップショット一致テストの前提。
- **HTML エスケープテストは 2段階**: `re.sub` で `application/json` 用と通常 JS `script` ブロックを除去した残り本文に生の `<script>` がないかチェック。除去しないと偽陰性になる。
- **モジュールスコープフィクスチャで重複 render を避ける**: `scope="module"` の `rendered_html` フィクスチャにより、依存テスト群が1回の render で済む。
- **pytest.ini の `markers` 登録は必須**: `--strict-markers` と組み合わせることで未登録マークを警告ではなくエラーにして品質を維持できる。
- **sys.path.insert で scripts/ を通す**: venv なしの標準ライブラリ専用プロジェクトでは `conftest.py` より tests ファイル冒頭の `sys.path.insert(0, scripts_dir)` が明快。

---

## config-topology パーサ層 TDD 実装（2026-06-01）

### 概要
`scripts/parsers/` + `scripts/parse_configs.py` を標準ライブラリのみで TDD 実装。pytest 91テスト全パス、パーサ層カバレッジ 96%。

### 重要な知見

- **JunOS detect は「`set ` 行が過半数か」で十分**。比率チェックを 0.5 超とすれば IOS（`!` 行などが混在）との誤検知を防げる。IOS detect 側は 0.4 を閾値に「set 支配的なら JunOS」と弾く二重ガードで安定。
- **IOS ブロックパースは「インデントあり行が続く限りループ」**: `inner[0].isspace()` で判定するとシンプル。`!` や空行が来たらブレーク。
- **OSPF wildcard → CIDR 変換は「255 - オクテット」**: `0.0.0.255` → `255.255.255.0` → `/24`。逆マスクの各オクテットを 255 から引いてサブネットマスクを得てから `ipaddress.IPv4Network` に渡す。
- **secondary アドレスの弾き方**: `re.match` のパターンに `(?:\s+secondary)?$` で末尾照合しつつ `"secondary" not in inner_stripped` でガードすると安全。
- **JunOS IF 名は dict で収集してから Interface リスト化**: 同一 IF に description/ip/disable が別行に分散するため `if_data: dict[str, dict]` で集約してから変換するとすっきり。
- **parse_configs.py の CLI テストは `importlib.reload` が必要**: `monkeypatch.chdir` で cwd を変更しても既にインポート済みの `collect_inputs` は古い cwd を参照しない場合がある。`reload()` でモジュールを再初期化してから呼ぶ。
- **`--cov=scripts/parsers` で render_topology.py を計測から除外できる**: `--cov=scripts` にするとプロジェクト内の既存スクリプトが 0% として合算される。パーサ層だけ計測したいときはサブパッケージ指定が有効。

---

## render_topology.py の tables 構造変更（2026-06-01）

### 変更内容
`build_render_data()` の tables を「全体BGP/static 横並び」から「機器ごとカード・カード内 sections 縦積み」に変更。

### 重要な教訓

- **flow インデックスは元配列全体インデックスを維持**すること。device でフィルタしても `for i, g in enumerate(bgp)` の `i` を捨てずに使う。テーブルの flow と flows リストの flow id が一致しないと図クリック連動が壊れる。

- **orphan 判定は `dev_ids = {d.get("id") for d in devices}` で集合チェック**が明快。`d.get("device") not in dev_ids` の1行で対応。

- **JS の `buildTables()` は SPA 動的生成** なので静的 HTML に `node-card` 等の class は存在しない。動作確認は埋め込み JSON の `tables` 構造チェックと Python でのシミュレーションが有効。

- **`markTableRows()` は `querySelectorAll` で DOM ツリーをフラットに走査**するため、カードで DOM が深くなっても変更不要。

- **stdlib unittest でのテストファースト**: openpyxl 等の依存なし・`sys.path.insert` で scripts/ を通す方式が有効。テスト dict はモジュールレベルの関数（`make_topo()` 等）として定義すると setUp が簡潔になる。
