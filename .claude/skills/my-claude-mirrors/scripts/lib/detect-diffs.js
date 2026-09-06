#!/usr/bin/env node
'use strict';

// detect-diffs.js — detect-diffs.sh から呼ばれるnode実装。
// linux/claude/ と windows/claude/ を再帰比較し、台帳(ledger.json)と照合した結果をJSONで標準出力に返す。
// jqに依存しない(Claude Code自体の実行基盤であるnodeのみに依存する)。

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const [, , linuxDir, windowsDir, ledgerPath] = process.argv;

function walk(rootDir) {
  const files = [];
  const emptyDirs = [];

  function rec(current) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    if (entries.length === 0) {
      const rel = path.relative(rootDir, current).split(path.sep).join('/');
      emptyDirs.push(rel);
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        rec(full);
      } else if (entry.isFile()) {
        files.push(path.relative(rootDir, full).split(path.sep).join('/'));
      }
    }
  }

  rec(rootDir);
  files.sort();
  emptyDirs.sort();
  return { files, emptyDirs };
}

// CRLF/LFの違いを無視するため、比較前に全てのCRバイト(0x0D)を取り除いてからハッシュ化する。
// `tr -d '\r' | sha256sum` とバイト単位で等価。
function normHash(filePath) {
  const buf = fs.readFileSync(filePath);
  const filtered = buf.filter((b) => b !== 0x0d);
  return crypto.createHash('sha256').update(filtered).digest('hex');
}

const linux = walk(linuxDir);
const windows = walk(windowsDir);

const linuxFileSet = new Set(linux.files);
const windowsFileSet = new Set(windows.files);
const linuxDirSet = new Set(linux.emptyDirs);
const windowsDirSet = new Set(windows.emptyDirs);

const onlyInLinux = [
  ...linux.files.filter((f) => !windowsFileSet.has(f)),
  ...linux.emptyDirs.filter((d) => !windowsDirSet.has(d)),
].sort();
const onlyInWindows = [
  ...windows.files.filter((f) => !linuxFileSet.has(f)),
  ...windows.emptyDirs.filter((d) => !linuxDirSet.has(d)),
].sort();
const commonFiles = linux.files.filter((f) => windowsFileSet.has(f)).sort();

let ledger = [];
if (fs.existsSync(ledgerPath)) {
  const raw = fs.readFileSync(ledgerPath, 'utf8').trim();
  ledger = raw ? JSON.parse(raw) : [];
}

const newDiffs = [];
const knownDiffs = [];

for (const f of commonFiles) {
  const lh = normHash(path.join(linuxDir, f));
  const wh = normHash(path.join(windowsDir, f));
  if (lh === wh) continue;

  const matches = ledger.filter(
    (e) => e.file === f && e.linux_hash === lh && e.windows_hash === wh
  );
  if (matches.length > 0) {
    knownDiffs.push(matches[matches.length - 1]);
  } else {
    newDiffs.push({ file: f, linux_hash: lh, windows_hash: wh });
  }
}

console.log(
  JSON.stringify(
    {
      new_diffs: newDiffs,
      known_diffs: knownDiffs,
      only_in_linux: onlyInLinux,
      only_in_windows: onlyInWindows,
    },
    null,
    2
  )
);
