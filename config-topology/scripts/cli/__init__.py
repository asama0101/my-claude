"""
scripts.cli — CLI エントリーポイント（SKILL.md の各 Phase が python3 で起動する）。

- parse_configs.py   Phase1: ベンダー自動判定 → 正規化モデル(Device) を JSON 出力
- build_topology.py  Phase2: リンク/セグメント推論・BGP対向解決 → 層別 YAML 出力
- render_topology.py Phase3: 層別 YAML → 自己完結 HTML 構成図

ロジック本体は scripts.lib（parsers / rendering / topology_io）にある。
"""
