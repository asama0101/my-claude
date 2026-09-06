#!/bin/bash
set -uo pipefail
HOOK="$HOME/.claude/hooks/venv-guard.sh"
SCRATCH=$(mktemp -d)
REPO="$SCRATCH/repo"; mkdir -p "$REPO/.venv/bin"
trap 'rm -rf "$SCRATCH"' EXIT

# key=value / key.sub=value 形式の引数からJSONを組み立てる(jqの代替)。
json_build() {
  node -e '
    var out = {};
    process.argv.slice(1).forEach(function (kv) {
      var i = kv.indexOf("=");
      var path = kv.slice(0, i), val = kv.slice(i + 1);
      var keys = path.split(".");
      var cur = out;
      for (var j = 0; j < keys.length - 1; j++) {
        cur[keys[j]] = cur[keys[j]] || {};
        cur = cur[keys[j]];
      }
      cur[keys[keys.length - 1]] = val;
    });
    process.stdout.write(JSON.stringify(out));
  ' "$@"
}

run_bash() {  # $1=command $2=VIRTUAL_ENV値(省略時は未設定)
  local input cmd="$1" venv="${2:-}"
  input=$(json_build tool_name=Bash tool_input.command="$cmd")
  if [ -n "$venv" ]; then
    printf '%s' "$input" | (cd "$REPO" && VIRTUAL_ENV="$venv" bash "$HOOK")
  else
    printf '%s' "$input" | (cd "$REPO" && env -u VIRTUAL_ENV bash "$HOOK")
  fi
}

FAIL=0
assert_exit() {
  if [ "$1" != "$2" ]; then
    echo "FAIL: $3 (expected exit $1, got $2)"
    FAIL=1
  else
    echo "PASS: $3"
  fi
}

# ── pip install ──
run_bash 'pip install requests'; assert_exit 2 "$?" "pip install: VIRTUAL_ENV未設定はブロック"
run_bash 'pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "pip install: VIRTUAL_ENVがプロジェクト配下なら許可"
run_bash 'pip install requests' "/tmp/other-venv"; assert_exit 2 "$?" "pip install: VIRTUAL_ENVがプロジェクト外はブロック"
run_bash 'pip3 install requests' "$REPO/.venv"; assert_exit 0 "$?" "pip3 install も同様に許可"
run_bash 'python3 -m pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "python -m pip install も同様に許可"
run_bash 'echo start && pip install requests' "$REPO/.venv"; assert_exit 0 "$?" "複合コマンド内(&&)のpip installも検知される"

# ── pip uninstall ──
run_bash 'pip uninstall requests'; assert_exit 2 "$?" "pip uninstall: VIRTUAL_ENV未設定はブロック"
run_bash 'pip uninstall requests' "$REPO/.venv"; assert_exit 0 "$?" "pip uninstall: VIRTUAL_ENVがプロジェクト配下なら許可"

# ── venvバイナリ直接指定の早期許可 ──
run_bash '.venv/bin/pip install requests'; assert_exit 0 "$?" "venvバイナリ直接指定(.venv/bin/pip)は許可"
run_bash "$REPO/.venv/bin/pip3 install requests"; assert_exit 0 "$?" "venvバイナリ直接指定(絶対パス)は許可"

# ── uv add / uv pip install ──
run_bash 'uv add requests'; assert_exit 0 "$?" "uv add: プロジェクト配下に.venvがあれば許可"
NOVENV="$SCRATCH/novenv"; mkdir -p "$NOVENV"
input=$(json_build tool_name=Bash tool_input.command='uv add requests')
printf '%s' "$input" | (cd "$NOVENV" && bash "$HOOK")
assert_exit 2 "$?" "uv add: プロジェクト配下に.venvが無ければブロック"

# ── 例外なし方針: VIRTUAL_ENVがプロジェクトのプレフィックスと無関係でもブロック ──
run_bash 'pip install requests' "/some/unrelated/path"; assert_exit 2 "$?" "誤検知しても機械的にブロック(回避経路は用意しない方針)"

echo "----"
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME TESTS FAILED"; exit 1; }
