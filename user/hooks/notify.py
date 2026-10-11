"""処理の完了と、ユーザーの操作待ちを通知する Hook（トースト通知と音）。

使い方（settings.json の hooks から呼ぶ。入力は stdin の JSON）:
  notify.py start      UserPromptSubmit 用。応答の開始時刻をセッションごとに記録する
  notify.py done       Stop 用。開始から THRESHOLD_SEC 以上かかっていれば通知する
  notify.py attention  Notification 用。許可待ちなど、操作を求められたときに通知する

サブエージェントの完了（SubagentStop）には hook を付けないので、通知しない。
Hook の失敗で作業を止めないため、予期しない例外は握りつぶして正常終了する。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-notify")
STATE_TTL_SEC = 7 * 24 * 3600
THRESHOLD_SEC = 30  # この秒数以上かかった応答だけ通知する
ATTENTION_TYPES = {"permission_prompt", "elicitation_dialog"}  # 通知する Notification の種類
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.ps1")


def state_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return os.path.join(STATE_DIR, safe + ".txt")


def prune_old_states():
    try:
        now = time.time()
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if now - os.path.getmtime(p) > STATE_TTL_SEC:
                os.remove(p)
    except OSError:
        pass


def notify(message):
    """通知用の PowerShell を、hook を待たせないよう切り離して起動する。"""
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT,
         "-Message", message],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def start(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_path(data.get("session_id")), "w", encoding="utf-8") as f:
        f.write(str(time.time()))


def done(data):
    path = state_path(data.get("session_id"))
    try:
        with open(path, encoding="utf-8") as f:
            started = float(f.read())
        os.remove(path)  # 続けて Stop が走っても、二重に通知しない
    except (OSError, ValueError):
        return
    elapsed = time.time() - started
    if elapsed >= THRESHOLD_SEC:
        notify("処理が完了しました（%d 分 %d 秒）" % divmod(int(elapsed), 60))


def attention(data):
    if data.get("notification_type") in ATTENTION_TYPES:
        notify(data.get("message") or "操作を待っています")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if mode == "start":
        prune_old_states()
        start(data)
    elif mode == "done":
        done(data)
    elif mode == "attention":
        attention(data)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
