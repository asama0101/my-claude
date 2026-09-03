#!/bin/bash
# hooks/lib/json-field.sh — 共有ライブラリ(各フックから source)
# Claude Code自体がNode.js上で動くため、hooks実行環境には常にnodeが
# 存在するという前提でjqへの依存を廃止し、node単体でJSON抽出を行う。
# 対象はtool_name(トップレベル文字列)とtool_input配下1階層のネスト文字列
# (command/file_path/notebook_path)のみ。

has_json_backend() {
  command -v node >/dev/null 2>&1 && node -e "process.exit(0)" >/dev/null 2>&1
}

read -r -d '' _JSON_FIELD_JS <<'JSEOF' || true
var data = "";
process.stdin.on("data", function (c) { data += c; });
process.stdin.on("end", function () {
  var obj = {};
  try { obj = JSON.parse(data); } catch (e) { obj = {}; }
  var paths = process.argv.slice(1);
  for (var i = 0; i < paths.length; i++) {
    var cur = obj;
    var keys = paths[i].split(".");
    var ok = true;
    for (var j = 0; j < keys.length; j++) {
      if (cur !== null && typeof cur === "object" &&
          Object.prototype.hasOwnProperty.call(cur, keys[j])) {
        cur = cur[keys[j]];
      } else {
        ok = false;
        break;
      }
    }
    if (ok && typeof cur === "string") {
      process.stdout.write(cur);
      return;
    }
  }
  process.stdout.write("");
});
JSEOF

# json_field <json> <dotted_path> [<dotted_path2> ...]
json_field() {
  local json="$1"
  shift
  printf '%s' "$json" | node -e "$_JSON_FIELD_JS" "$@"
}

read -r -d '' _JSON_FIELDS_JS <<'JSEOF' || true
var data = "";
process.stdin.on("data", function (c) { data += c; });
process.stdin.on("end", function () {
  var obj = {};
  try { obj = JSON.parse(data); } catch (e) { obj = {}; }
  var specs = process.argv.slice(1);
  var lines = specs.map(function (spec) {
    var paths = spec.split(",");
    for (var i = 0; i < paths.length; i++) {
      var cur = obj;
      var keys = paths[i].split(".");
      var ok = true;
      for (var j = 0; j < keys.length; j++) {
        if (cur !== null && typeof cur === "object" &&
            Object.prototype.hasOwnProperty.call(cur, keys[j])) {
          cur = cur[keys[j]];
        } else {
          ok = false;
          break;
        }
      }
      if (ok && (typeof cur === "string" || typeof cur === "number")) {
        return String(cur);
      }
    }
    return "";
  });
  process.stdout.write(lines.join("\n"));
});
JSEOF

# json_fields <json> <spec1> [<spec2> ...]
# spec は "path1,path2,..." 形式のカンマ区切りフォールバック(先に見つかった値を採用)。
# 1回のnode起動で全specをまとめて解決し、結果を1行ずつ改行区切りで返す
# (jqの `(.a // .b // "")` を複数フィールド一括で行う代替。statusline等の多フィールド抽出向け)。
json_fields() {
  local json="$1"
  shift
  printf '%s' "$json" | node -e "$_JSON_FIELDS_JS" "$@"
}
