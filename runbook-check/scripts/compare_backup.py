#!/usr/bin/env python3
"""
作業の投入Config（関数解決後コマンド）を、作成時バックアップ（現行Config）と照合し、
妥当性を機械的にチェックする（構造の深い意味判断はレビュアーが上乗せ解釈する）。

役割分担:
  - 本スクリプト: 「現行Configと突き合わせれば機械的に分かる事実」を出す。
    削除対象の実在・識別子(IP/VLAN-ID)の重複/競合・投入対象IFの新規性・全体の整合度。
  - レビュアー(LLM): backup_compare.json と投入Config・backup を読み、設計意図との整合や
    アクセスVLAN変更による端末断など、意味的な妥当性を解釈する。

入力:
  --backup  現行Config（show configuration / running-config 等のテキスト or .conf）
  --config  投入Config。interpreted.json（config_preview を持つ）/ コマンド文字列のJSON配列 /
            1行1コマンドのテキスト、のいずれか。

出力JSON:
  {"summary": {...}, "details": [...], "findings": [ render用の指摘 ... ]}

使い方:
    python compare_backup.py --backup current.conf --config review-work/interpreted.json -o backup_compare.json
"""
import argparse
import json
import re
import sys

DIM = "14. 現行Config整合（バックアップ照合）"

IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
VLANID_RE = re.compile(r"vlan-id\s+(\d+)", re.I)
# Junos/IOS の代表的なIF表記
IFACE_RE = re.compile(
    r"\b((?:ge|xe|et|fe|ae|irb|lo|reth|em|me|fxp|gi|te|fa|eth)[-\d/.:]*\d)\b", re.I)
VLAN_MEMBERS_RE = re.compile(r"vlan\s+members\s+(\S+)", re.I)
# 削除系コマンド（Junos delete / IOS no）
REMOVE_RE = re.compile(r"^\s*(?:delete|no)\s+(.*)$", re.I)
ADD_RE = re.compile(r"^\s*set\s+(.*)$", re.I)
ERROR_TOKENS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NULL!", "#NUM!")
GENERIC = {"set", "delete", "no", "unit", "family", "interface", "interfaces", "address",
           "vlan", "vlans", "members", "system", "protocols", "0", "inet"}


def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def load_commands(config_arg):
    """投入コマンドの文字列リストを返す。"""
    raw = open(config_arg, encoding="utf-8").read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    cmds = []
    if isinstance(data, list):
        for x in data:
            if isinstance(x, str):
                cmds.append(x)
            elif isinstance(x, dict) and x.get("command"):
                cmds.append(x["command"])
    elif isinstance(data, dict):
        for blk in data.get("config_preview", []):
            for ln in blk.get("lines", []):
                if ln.get("command"):
                    cmds.append(ln["command"])
    return cmds


def tokens(s):
    return [t for t in re.split(r"[\s,;]+", norm(s)) if t]


def iface_membership(backup_lines):
    """backup から IF→所属VLAN(members) の対応を粗く拾う。"""
    mem = {}
    for ln in backup_lines:
        ifm = IFACE_RE.search(ln)
        vm = VLAN_MEMBERS_RE.search(ln)
        if ifm and vm:
            mem.setdefault(ifm.group(1).lower(), set()).add(vm.group(1).lower())
    return mem


def compare(backup_text, cmds):
    backup_lines = [ln for ln in backup_text.splitlines() if ln.strip()]
    blob = norm(backup_text)
    backup_tokens = set(tokens(backup_text))
    backup_ips = set(IP_RE.findall(backup_text))
    backup_vlanids = set(VLANID_RE.findall(backup_text))
    backup_ifaces = {m.lower() for m in IFACE_RE.findall(backup_text)}
    mem = iface_membership(backup_lines)

    details, findings = [], []
    seen_new_iface = set()
    inj_tokens = set()

    for cmd in cmds:
        if not cmd or any(tok in cmd for tok in ERROR_TOKENS):
            continue  # 関数エラー等は facts 側で確定済み
        inj_tokens |= set(tokens(cmd))
        d = {"command": cmd, "op": "other", "notes": []}

        rem = REMOVE_RE.match(cmd)
        add = ADD_RE.match(cmd)

        if rem:
            d["op"] = "del"
            target = rem.group(1)
            sig = [t for t in tokens(target) if t not in GENERIC and len(t) > 1]
            # 対象パスの主要トークンが現行に一つも無ければ「削除対象なし」
            present = any(t in blob for t in sig) if sig else (norm(target) in blob)
            d["in_backup"] = present
            if sig and not present:
                d["notes"].append("削除対象が現行Configに見当たらない")
                findings.append({
                    "severity": "important", "kind": "delete_missing", "dimension": DIM,
                    "location": "投入Config", "problem": f"削除コマンド「{cmd}」の対象が現行Config(バックアップ)に存在しない。",
                    "suggestion": "対象パスの綴り・存在を現行Configで確認する。無効な削除は no-op か対象誤りで、意図した撤去がされない。",
                    "reviewers": ["backup_check"],
                })
        elif add:
            d["op"] = "add"
            ips = IP_RE.findall(cmd)
            vids = VLANID_RE.findall(cmd)
            ifs = [m.lower() for m in IFACE_RE.findall(cmd)]
            d["identifiers"] = {"ip": ips, "vlan_id": vids, "iface": ifs}

            for ip in ips:
                if ip in backup_ips:
                    d["notes"].append(f"IP {ip} は現行に既出")
                    findings.append({
                        "severity": "important", "kind": "ip_dup", "dimension": DIM,
                        "location": "投入Config", "problem": f"投入する IP {ip} が現行Configに既に存在する（重複/競合の疑い）。",
                        "suggestion": "二重採番・既存割当との衝突がないか確認する。重複割当は機器で拒否または通信障害になりうる。",
                        "reviewers": ["backup_check"],
                    })
            for vid in vids:
                if vid in backup_vlanids:
                    d["notes"].append(f"vlan-id {vid} は現行に既出")
                    findings.append({
                        "severity": "important", "kind": "vlanid_dup", "dimension": DIM,
                        "location": "投入Config", "problem": f"投入する vlan-id {vid} が現行Configに既に存在する（重複/別VLAN名との競合の疑い）。",
                        "suggestion": "同一 vlan-id の二重定義になっていないか、既存VLANと統合すべきでないか確認する。",
                        "reviewers": ["backup_check"],
                    })
            for ifc in ifs:
                if ifc in backup_ifaces:
                    # 既存IF。アクセスVLANの所属変更などは端末断につながる
                    new_mem = VLAN_MEMBERS_RE.search(cmd)
                    cur = mem.get(ifc)
                    if new_mem and cur and new_mem.group(1).lower() not in cur:
                        d["notes"].append(f"{ifc} の所属VLAN変更の可能性（現行: {sorted(cur)} → {new_mem.group(1)}）")
                        findings.append({
                            "severity": "important", "kind": "iface_vlan_change", "dimension": DIM,
                            "location": "投入Config", "problem": (
                                f"{ifc} は現行Configで VLAN {sorted(cur)} に収容済みだが、本作業で {new_mem.group(1)} を投入する。"
                                "アクセスポートの所属VLAN変更なら配下端末の通信断を伴う。"),
                            "suggestion": "対象ポートが未使用か稼働中かを確認し、稼働中なら影響範囲・断時間・切り戻しを手順に明記する。",
                            "reviewers": ["backup_check"],
                        })
                    else:
                        d["notes"].append(f"{ifc} は現行に存在（既存IFへの追加設定）")
                elif ifc not in seen_new_iface:
                    seen_new_iface.add(ifc)
                    d["notes"].append(f"{ifc} は現行に無し（新規対象）")
                    findings.append({
                        "severity": "recommended", "kind": "iface_new", "dimension": DIM,
                        "location": "投入Config", "problem": f"投入対象IF {ifc} が現行Config(バックアップ)に見当たらない（新規 or 綴り違い）。",
                        "suggestion": "新規IFなら問題ないが、既存IFの綴り違いでないか確認する。",
                        "reviewers": ["backup_check"],
                    })
        if d["notes"]:
            details.append(d)

    inter = inj_tokens & backup_tokens
    similarity = round(len(inter) / len(inj_tokens), 3) if inj_tokens else None
    if similarity is not None and similarity < 0.3 and len(inj_tokens) >= 6:
        findings.append({
            "severity": "recommended", "kind": "low_similarity", "dimension": DIM,
            "location": "投入Config", "problem": f"投入Configと現行Configの用語・採番の一致度が低い（整合度 {similarity}）。",
            "suggestion": "命名規則・採番体系が現行と揃っているか、別機器のConfigを参照していないか確認する。",
            "reviewers": ["backup_check"],
        })

    summary = {
        "backup_lines": len(backup_lines),
        "injected_commands": len(cmds),
        "removals": sum(1 for c in cmds if REMOVE_RE.match(c)),
        "additions": sum(1 for c in cmds if ADD_RE.match(c)),
        "similarity": similarity,
        "findings": len(findings),
    }
    return {"summary": summary, "details": details, "findings": findings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True, help="現行Config（テキスト/.conf）")
    ap.add_argument("--config", required=True, help="投入Config（interpreted.json / コマンドJSON配列 / テキスト）")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()

    try:
        backup_text = open(args.backup, encoding="utf-8").read()
    except OSError as e:
        print(f"バックアップを読めません: {e}", file=sys.stderr)
        sys.exit(1)
    cmds = load_commands(args.config)
    out = compare(backup_text, cmds)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text)
        s = out["summary"]
        print(f"現行Config照合完了: {args.output}")
        print(f"  投入 {s['injected_commands']} / 削除 {s['removals']} / 整合度 {s['similarity']} / 指摘 {s['findings']}")
    else:
        print(text)


if __name__ == "__main__":
    main()
