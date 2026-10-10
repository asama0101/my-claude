import json
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

RESET = "\033[0m"
CYAN = "\033[36m"
BLUE = "\033[94m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
GRAY = "\033[90m"

BAR_WIDTH = 5
SEP = "{} │ {}".format(GRAY, RESET)

ICON_MODEL = "◆"
ICON_DIR = "▸"
ICON_BRANCH = "⎇"
ICON_DIRTY = "●"
ICON_PR = "⇄"
ICON_SESSION = "✎"
ICON_CTX = "◔"
ICON_5H = "⏱"
ICON_7D = "▦"


def paint(color, text):
    return "{}{}{}".format(color, text, RESET)


def level_color(pct):
    if pct >= 80:
        return RED
    if pct >= 60:
        return YELLOW
    return GREEN


def bar(pct):
    filled = max(0, min(BAR_WIDTH, round(pct / 100 * BAR_WIDTH)))
    return "▓" * filled + "░" * (BAR_WIDTH - filled)


def meter(icon, pct, resets_at=None):
    # 取れない値は項目ごと省略する（ctx のみ呼び出し側で "--" を渡す）
    if not isinstance(pct, (int, float)):
        return None
    color = level_color(pct)
    out = paint(color, "{} {:.0f}% {}".format(icon, pct, bar(pct)))
    left = remaining(resets_at)
    if left:
        out += " " + paint(GRAY, left)
    return out


def remaining(resets_at):
    if not isinstance(resets_at, (int, float)):
        return ""
    sec = int(resets_at - time.time())
    if sec <= 0:
        return "0m"
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "{}d{}h".format(d, h)
    if h:
        return "{}h{}m".format(h, m)
    return "{}m".format(m)


def git_branch(cwd):
    if not cwd:
        return None
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v1", "--branch"],
            capture_output=True, text=True, encoding="utf-8", timeout=3,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    lines = r.stdout.splitlines()
    if not lines or not lines[0].startswith("## "):
        return None
    name = lines[0][3:].split("...")[0]
    if name.startswith("No commits yet on "):
        name = name[len("No commits yet on "):]
    dirty = len(lines) > 1
    return name, dirty


def sub(obj, key):
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, dict) else {}


try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}

model = sub(data, "model").get("display_name") or "?"
effort = sub(data, "effort").get("level")
cwd = sub(data, "workspace").get("current_dir") or data.get("cwd") or ""
cwd = str(cwd).replace("\\", "/")

# 1行目: モデル / effort、ブランチ、PR
head = paint(CYAN, "{} {}".format(ICON_MODEL, model))
if effort:
    head += paint(GRAY, " / ") + paint(CYAN, effort)
line1 = [head]

branch = git_branch(cwd)
if branch:
    name, dirty = branch
    git = paint(GREEN, "{} {}".format(ICON_BRANCH, name))
    if dirty:
        git += " " + paint(YELLOW, ICON_DIRTY)
    line1.append(git)

pr = sub(data, "pr")
if pr.get("number"):
    label = "MR" if pr.get("kind") == "mr" else "PR"
    state = pr.get("review_state")
    text = paint(BLUE, "{} {} #{}".format(ICON_PR, label, pr["number"]))
    if state:
        state_color = {"approved": GREEN, "changes_requested": RED}.get(state, YELLOW)
        text += " " + paint(state_color, state)
    line1.append(text)

# 2行目: ディレクトリ
line2 = [paint(BLUE, "{} {}".format(ICON_DIR, cwd))] if cwd else []

# 3行目: ctx、5h、7d、セッション名
limits = sub(data, "rate_limits")
five = sub(limits, "five_hour")
week = sub(limits, "seven_day")
ctx = sub(data, "context_window").get("used_percentage")

line3 = [meter(ICON_CTX, ctx) or paint(GRAY, "{} --".format(ICON_CTX))]
for icon, window in ((ICON_5H, five), (ICON_7D, week)):
    item = meter(icon, window.get("used_percentage"), window.get("resets_at"))
    if item:
        line3.append(item)

session_name = data.get("session_name")
if session_name:
    line3.append(paint(CYAN, "{} {}".format(ICON_SESSION, session_name)))

for line in (line1, line2, line3):
    if line:
        print(SEP.join(line))
