"""show_parser.py — ネットワーク機器の show running-config を解析して構造化データを返す。

対応ベンダー: Cisco IOS / Juniper (set形式)
"""
import argparse
import json
import re


def _detect_vendor(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("set "):
            return "juniper"
        if stripped.startswith(("hostname ", "interface ")):
            return "cisco"
    return "unknown"


def _parse_cisco(text: str) -> dict:
    hostname = None
    interfaces = []
    vlans = []

    lines = text.splitlines()
    i = 0
    current_iface = None
    current_vlan = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if re.match(r"^hostname\s+(\S+)", stripped):
            hostname = stripped.split(None, 1)[1]
            current_iface = None
            current_vlan = None

        elif m := re.match(r"^interface\s+(\S+)", stripped):
            current_iface = {
                "name": m.group(1),
                "ip": None,
                "mask": None,
                "description": None,
                "shutdown": False,
                "vlan": None,
            }
            interfaces.append(current_iface)
            current_vlan = None

        elif m := re.match(r"^vlan\s+(\d+)$", stripped):
            current_vlan = {"id": int(m.group(1)), "name": None}
            vlans.append(current_vlan)
            current_iface = None

        elif stripped == "!":
            current_iface = None
            current_vlan = None

        elif current_iface is not None:
            if m := re.match(r"^ip address\s+(\S+)\s+(\S+)", stripped):
                current_iface["ip"] = m.group(1)
                current_iface["mask"] = m.group(2)
            elif stripped.startswith("description "):
                current_iface["description"] = stripped[len("description "):]
            elif stripped == "shutdown":
                current_iface["shutdown"] = True
            elif m := re.match(r"^switchport access vlan\s+(\d+)", stripped):
                current_iface["vlan"] = int(m.group(1))

        elif current_vlan is not None:
            if stripped.startswith("name "):
                current_vlan["name"] = stripped[len("name "):]

        i += 1

    return {"hostname": hostname, "interfaces": interfaces, "vlans": vlans}


def _parse_juniper(text: str) -> dict:
    hostname = None
    interfaces: dict[str, dict] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("set "):
            continue
        tokens = stripped.split()

        # set system host-name <name>
        if len(tokens) >= 4 and tokens[1] == "system" and tokens[2] == "host-name":
            hostname = tokens[3]

        # set interfaces <ifname> unit 0 family inet address <ip/prefix>
        elif len(tokens) >= 8 and tokens[1] == "interfaces" and "address" in tokens:
            addr_idx = tokens.index("address") + 1
            if addr_idx >= len(tokens):
                continue
            ifname = tokens[2]
            addr_token = tokens[addr_idx]
            ip = addr_token.split("/")[0]  # CIDRのホスト部だけ取得
            if ifname not in interfaces:
                interfaces[ifname] = {
                    "name": ifname,
                    "ip": ip,
                    "mask": None,
                    "description": None,
                    "shutdown": False,
                    "vlan": None,
                }

    return {
        "hostname": hostname,
        "interfaces": list(interfaces.values()),
        "vlans": [],
    }


def parse_config(text: str, vendor: str = "auto") -> dict:
    """設定テキストを解析して構造化辞書を返す。

    Args:
        text: show running-config 等のテキスト全体
        vendor: "auto"|"cisco"|"juniper" (auto の場合は内容から判定)

    Returns:
        vendor/hostname/interfaces/vlans/raw_lines を含む dict
    """
    resolved_vendor = vendor if vendor != "auto" else _detect_vendor(text)
    raw_lines = len(text.splitlines())

    if resolved_vendor == "cisco":
        parsed = _parse_cisco(text)
    elif resolved_vendor == "juniper":
        parsed = _parse_juniper(text)
    else:
        parsed = {"hostname": None, "interfaces": [], "vlans": []}

    return {
        "vendor": resolved_vendor,
        "hostname": parsed["hostname"],
        "interfaces": parsed["interfaces"],
        "vlans": parsed["vlans"],
        "raw_lines": raw_lines,
    }


def main():
    parser = argparse.ArgumentParser(description="show running-config パーサー")
    parser.add_argument("--config", required=True, help="設定ファイルのパス")
    parser.add_argument("--vendor", default="auto", choices=["auto", "cisco", "juniper"])
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        text = f.read()

    result = parse_config(text, vendor=args.vendor)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
