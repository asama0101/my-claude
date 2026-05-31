#!/usr/bin/env python3
"""
パラメータ値の妥当性を機械検証する（構造非依存ヘルパー）。
「どのセルがパラメータか」はサブエージェントが解釈し、その結果だけを渡す。
このスクリプトは渡された値の形式・範囲・宣言された許容範囲・IP×マスク整合のみを判定する。

入力JSON（ファイル or 標準入力）: パラメータの配列
  [{"name":"VLAN-ID","value":5000,"cell":"パラメータ!B5",
    "type":"vlan",          # 省略可。無ければ name から推定
    "constraint":"1-4094"}, # 省略可
   ...]

type: ip / cidr / mask / vlan / hostname / interface / int / text（省略時は name から推定）
constraint 記法: 数値レンジ 'N-M' / ネットワーク 'x.x.x.x/nn' / 列挙 'A|B|C' / 正規表現 're:...' / 完全一致

出力JSON:
  {"results":[{"cell","name","value","ok","issue","type"}...],
   "findings":[ render用の指摘(important) ...]}

使い方:
    python validate_values.py params.json
    cat params.json | python validate_values.py -
"""
import argparse
import ipaddress
import json
import re
import sys

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9./:_-]+$")


def infer_type(name):
    n = (name or "").lower()
    if any(k in name or k in n for k in ("cidr", "ネットワークアドレス", "プレフィクス", "prefix")):
        return "cidr"
    if any(k in name or k in n for k in ("マスク", "mask", "サブネット", "subnet")):
        return "mask"
    if any(k in name or k in n for k in ("ip", "アドレス", "address", "ゲートウェイ", "gateway", "next-hop", "ネクストホップ")):
        return "ip"
    if "vlan" in n:
        return "vlan"
    if any(k in name or k in n for k in ("ホスト名", "hostname", "host")):
        return "hostname"
    if any(k in name or k in n for k in ("インタフェース", "インターフェース", "interface", "ポート", "port", "if名")):
        return "interface"
    return None


def check_format(value, ptype):
    s = str(value).strip()
    try:
        if ptype == "ip":
            ipaddress.ip_address(s)
        elif ptype == "cidr":
            ipaddress.ip_network(s, strict=False)
        elif ptype == "mask":
            ipaddress.IPv4Network(f"0.0.0.0/{s}")
        elif ptype == "vlan":
            v = int(float(s))
            if not (1 <= v <= 4094):
                return f"VLAN-IDが範囲外（{v}）。1〜4094で指定する。"
        elif ptype == "hostname":
            if not HOSTNAME_RE.match(s) or len(s) > 253:
                return f"ホスト名として不正な文字種/形式（{s}）。"
        elif ptype == "interface":
            if not IFNAME_RE.match(s) or " " in s:
                return f"インタフェース名に不正な文字/空白（{s}）。"
        elif ptype == "int":
            int(float(s))
    except ValueError:
        labels = {"ip": "IPv4/IPv6アドレス", "cidr": "CIDR", "mask": "サブネットマスク(連続ビット)", "int": "整数"}
        return f"{labels.get(ptype, ptype)}として不正な値（{s}）。"
    return None


def check_constraint(value, constraint):
    s = str(value).strip()
    c = str(constraint).strip()
    if c.startswith("re:"):
        return None if re.match(c[3:], s) else f"許容パターン({c[3:]})に一致しない（{s}）。"
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[-~〜]\s*(-?\d+(?:\.\d+)?)\s*$", c)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        try:
            v = float(s)
        except ValueError:
            return f"数値であるべき値が非数値（{s}）。許容範囲 {c}。"
        return None if lo <= v <= hi else f"許容範囲 {c} の外（{s}）。"
    if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}$", c):
        try:
            net = ipaddress.ip_network(c, strict=False)
            ip = ipaddress.ip_address(s)
            if ip not in net:
                return f"許容ネットワーク {c} の外のIP（{s}）。"
            if net.num_addresses > 2 and ip in (net.network_address, net.broadcast_address):
                return f"ネットワーク/ブロードキャストアドレスを指定（{s} in {c}）。"
            return None
        except ValueError:
            return f"IPとして不正な値（{s}）。許容ネットワーク {c}。"
    if "|" in c or "," in c:
        opts = [o.strip() for o in re.split(r"[|,]", c) if o.strip()]
        return None if s in opts else f"許容値 [{', '.join(opts)}] に含まれない（{s}）。"
    return None if s == c else f"期待値 '{c}' と一致しない（{s}）。"


IFACE_PREFIX_RE = re.compile(r"^(ge|xe|et|fe|ae|irb|lo|reth|em|me|fxp|gi|te|fa|eth)[-.\d/:]", re.I)
# パラメータ型 → 受け入れる参照トークンの種別（型をまたいだ誤一致を防ぐ）
TYPE_KINDS = {
    "ip": {"ip"}, "cidr": {"ip"}, "mask": {"num", "ip", "mask"},
    "vlan": {"num", "vlan"}, "int": {"num", "asn"},
    "hostname": {"host"}, "interface": {"iface"},
}


def token_kind(tok):
    """参照トークンの種別を推定（ip / num / iface / host / other）。"""
    s = str(tok).strip().lower()
    if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?$", s):
        return "ip"
    if re.match(r"^\d+(?:\.\d+)?$", s):
        return "num"
    if IFACE_PREFIX_RE.match(s):
        return "iface"
    if re.match(r"^[a-z0-9][a-z0-9.\-]*$", s):
        return "host"
    return "other"


def section_kind(label):
    """参照ファイルの見出し/ラベル（例: `# AS番号`, `マスク`）から、配下の裸の数値の種別を細分する。
    数値どうし（VLAN/マスク/AS）の取り違えを防ぐ。"""
    s = str(label)
    if re.search(r"\bAS\b|AS番号|ASN|自AS|対向AS|peer-as|local-as", s, re.I):
        return "asn"
    if re.search(r"マスク|サブネット|\bmask\b|prefix.?len|プレフィクス長", s, re.I):
        return "mask"
    if re.search(r"VLAN", s, re.I):
        return "vlan"
    return None


def build_reference(text):
    """インプット情報（IP一覧/設計値。CSV/JSON/テキスト）から、権威ある値→出典 の対応を作る。
    戻り値: {正規化トークン: (出典テキスト, 行番号, 種別)} 。None を渡されたら None（＝照合元なし）。"""
    if text is None:
        return None
    token2src = {}

    def add(tok, src, lineno, section=None):
        tok = str(tok).strip().lower()
        if not tok:
            return
        kind = token_kind(tok)
        if kind == "num" and section:  # 見出しが示す種別で裸の数値を細分（VLAN/マスク/AS の取り違え防止）
            kind = section
        token2src.setdefault(tok, (src, lineno, kind))
        # IP/CIDR はマスク無し形も登録（種別は ip 固定）
        m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?$", tok)
        if m:
            token2src.setdefault(m.group(1), (src, lineno, "ip"))

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = None
    if isinstance(data, dict):
        for i, (k, v) in enumerate(data.items(), 1):
            add(v, f"{k}={v}", i, section_kind(k))
            add(k, f"{k}={v}", i)
    elif isinstance(data, list):
        for i, item in enumerate(data, 1):
            if isinstance(item, dict):
                src = ", ".join(f"{k}:{v}" for k, v in item.items())
                for k, v in item.items():
                    add(v, src, i, section_kind(k))
            else:
                add(item, str(item), i)
    else:
        section = None
        for lineno, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):  # コメント行＝セクション見出し
                section = section_kind(s)
                continue
            for tok in re.split(r"[\s,;|\t]+", s):
                add(tok, s, lineno, section)
    return token2src


def match_reference(value, ptype, ref):
    """value が reference に**同じ種別で**存在すれば (出典テキスト, 行番号) を返す。無ければ None。
    型をまたいだ誤一致（裸の数字が無関係な行に一致 等）を防ぐため、ptype に応じて種別を絞る。"""
    s = str(value).strip().lower()
    cands = [s]
    m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?$", s)
    if m:
        cands.append(m.group(1))
    accepted = TYPE_KINDS.get((ptype or "").lower())  # None＝型不明なら種別で絞らない
    for c in cands:
        if c in ref:
            src, lineno, kind = ref[c]
            if accepted is None or kind in accepted:
                return (src, lineno)
    return None


def validate(params, reference=None, reference_name=None):
    ref = build_reference(reference)
    refname = reference_name or "インプット情報"
    results = []
    findings = []
    no_ref_count = 0
    for p in params:
        name = p.get("name", "")
        value = p.get("value")
        cell = p.get("cell", "")
        if value is None or (isinstance(value, str) and value.strip() == ""):
            results.append({"cell": cell, "name": name, "value": value, "ok": None, "issue": "未入力",
                            "type": p.get("type") or infer_type(name), "basis": "—（未入力）"})
            continue
        ptype = (p.get("type") or infer_type(name) or "").lower() or None
        # (1) 形式・許容範囲（壊れた値の検出）
        issues = []
        if ptype:
            r = check_format(value, ptype)
            if r:
                issues.append(r)
        if p.get("constraint") and not issues:
            r = check_constraint(value, p["constraint"])
            if r:
                issues.append(r)
        # (2) インプット情報（IP一覧/設計値）との照合。照合元が無い/不一致は NG。
        #     形式不正な値は照合しない（誤った「一致」表記が出るのを防ぐ）。
        ref_issue = None
        ref_note = None
        if issues:
            ref_note = "形式不正のため照合せず"
        elif ref is None:
            ref_issue = "設計値未照合（インプット情報・IP一覧が未提供）"
            ref_note = "照合元なし（インプット情報未提供）"
            no_ref_count += 1
        else:
            src = match_reference(value, ptype, ref)
            if src:
                src_text, lineno = src
                ref_note = f"インプット照合: {refname}:{lineno}行「{src_text}」と一致"
            else:
                ref_issue = f"インプット情報（{refname}）に一致する{ptype or '値'}が無い（設計値要確認）"
                ref_note = f"照合元に該当なし/不一致（参照: {refname}）"
        ok = (not issues) and (ref_issue is None)
        all_issues = issues + ([ref_issue] if ref_issue else [])
        basis_parts = []
        if ptype:
            basis_parts.append(f"形式({ptype})")
        if p.get("constraint"):
            basis_parts.append(f"許容範囲({p['constraint']}・シート宣言)")
        if ref_note:
            basis_parts.append(ref_note)
        basis = " / ".join(basis_parts) or "形式チェックのみ（型未指定）"
        results.append({"cell": cell, "name": name, "value": value, "ok": ok,
                        "issue": " / ".join(all_issues), "type": ptype, "basis": basis})
        # 形式・許容範囲の実不正は常に finding。reference 不一致は提供時のみ個別 finding。
        if issues:
            findings.append({
                "severity": "important", "kind": "param_invalid",
                "dimension": "11. 関数・パラメータ整合",
                "location": cell or name,
                "problem": f"パラメータ「{name}」の値が不正: " + " / ".join(issues),
                "suggestion": "正しい値に修正する。誤値のまま関数解決すると機器で拒否/誤適用される。",
                "reviewers": ["value_check"],
            })
        if ref_issue and ref is not None:
            findings.append({
                "severity": "important", "kind": "param_unverified",
                "dimension": "11. 関数・パラメータ整合",
                "location": cell or name,
                "problem": f"パラメータ「{name}」({value}) がインプット情報（IP一覧/設計値）と一致しない。設計上の正解値か確認できずNG。",
                "suggestion": "IP一覧/設計書と突き合わせ、正しい設計値に修正するか、インプット情報を更新する。",
                "reviewers": ["value_check"],
            })

    # IP × マスク クロスチェック（各1つのときのみ）
    def t(p):
        return (p.get("type") or infer_type(p.get("name", "")) or "").lower()
    ips = [p for p in params if t(p) == "ip" and p.get("value")]
    masks = [p for p in params if t(p) == "mask" and p.get("value")]
    if len(ips) == 1 and len(masks) == 1:
        # クロスチェック対象の result の basis に明記する
        for r in results:
            if r.get("cell") in (ips[0].get("cell"), masks[0].get("cell")) and r.get("basis"):
                r["basis"] = r["basis"] + " / クロスチェック(IP×マスク)"
        try:
            net = ipaddress.IPv4Network(f"{ips[0]['value']}/{masks[0]['value']}", strict=False)
            ip = ipaddress.ip_address(str(ips[0]['value']).strip())
            if net.num_addresses > 2 and ip in (net.network_address, net.broadcast_address):
                findings.append({
                    "severity": "important", "kind": "param_crosscheck",
                    "dimension": "11. 関数・パラメータ整合",
                    "location": f"{ips[0].get('name')}×{masks[0].get('name')}",
                    "problem": f"IP {ips[0]['value']} がネットワーク {net} の{'ネットワーク' if ip==net.network_address else 'ブロードキャスト'}アドレスでホストに使えない。",
                    "suggestion": "ホストアドレスを指定する（マスクとの組み合わせを再確認）。",
                    "reviewers": ["value_check"],
                })
        except ValueError:
            pass

    # インプット情報（IP一覧/設計値）が未提供 → 設計値照合できず、対象パラメータを一律 NG。
    # per-param で findings を出すと氾濫するため、サマリ 1 件に集約する。
    if ref is None and no_ref_count:
        findings.append({
            "severity": "important", "kind": "no_reference",
            "dimension": "11. 関数・パラメータ整合",
            "location": "全体・横断",
            "problem": f"インプット情報（IP一覧/設計値）が未提供のため、記入済みパラメータ {no_ref_count} 件を設計値と照合できずNG（形式は別途検証）。",
            "suggestion": "IP一覧/設計書（IPAM 等）を検証根拠として渡す。照合できないと『設計上正しい値か』を保証できない。",
            "reviewers": ["value_check"],
        })
    return {"results": results, "findings": findings, "reference_provided": ref is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="パラメータ配列のJSONファイル。'-' で標準入力")
    ap.add_argument("-o", "--output", default=None, help="出力先（省略時は標準出力）")
    ap.add_argument("--reference", default=None,
                    help="検証根拠のインプット情報（IP一覧/設計値。CSV/JSON/テキスト）。未指定だと設計値未照合=NG")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    params = json.loads(raw)
    if isinstance(params, dict):
        params = params.get("parameters", [])
    import os as _os
    reference = open(args.reference, encoding="utf-8").read() if args.reference else None
    refname = _os.path.basename(args.reference) if args.reference else None
    out = validate(params, reference, refname)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text)
        print(f"検証完了: {args.output}（不正 {sum(1 for r in out['results'] if r['ok'] is False)}件）")
    else:
        print(text)


if __name__ == "__main__":
    main()
