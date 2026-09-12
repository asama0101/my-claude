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

const onlyInLinuxFiles = linux.files.filter((f) => !windowsFileSet.has(f));
const onlyInWindowsFiles = windows.files.filter((f) => !linuxFileSet.has(f));
const onlyInLinuxDirs = linux.emptyDirs.filter((d) => !windowsDirSet.has(d));
const onlyInWindowsDirs = windows.emptyDirs.filter((d) => !linuxDirSet.has(d));
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

// only_in_* も台帳と照合し、記録済み(known)と未記録(new)に分ける。
// ファイルは実ハッシュが台帳の該当side(linux_hash/windows_hash)と一致するかで判定、
// 空ディレクトリはハッシュ概念が無いためファイルパス一致のみで判定する。
function isKnownOnlyFile(dir, hashField, f) {
  const h = normHash(path.join(dir, f));
  return ledger.some((e) => e.file === f && e[hashField] === h);
}

function isKnownOnlyDir(f) {
  return ledger.some((e) => e.file === f);
}

const newOnlyLinux = [];
const knownOnlyLinux = [];
for (const f of onlyInLinuxFiles) {
  (isKnownOnlyFile(linuxDir, 'linux_hash', f) ? knownOnlyLinux : newOnlyLinux).push(f);
}
for (const d of onlyInLinuxDirs) {
  (isKnownOnlyDir(d) ? knownOnlyLinux : newOnlyLinux).push(d);
}

const newOnlyWindows = [];
const knownOnlyWindows = [];
for (const f of onlyInWindowsFiles) {
  (isKnownOnlyFile(windowsDir, 'windows_hash', f) ? knownOnlyWindows : newOnlyWindows).push(f);
}
for (const d of onlyInWindowsDirs) {
  (isKnownOnlyDir(d) ? knownOnlyWindows : newOnlyWindows).push(d);
}

newOnlyLinux.sort();
knownOnlyLinux.sort();
newOnlyWindows.sort();
knownOnlyWindows.sort();

console.log(
  JSON.stringify(
    {
      new_diffs: newDiffs,
      known_diffs: knownDiffs,
      only_in_linux: newOnlyLinux,
      only_in_windows: newOnlyWindows,
      known_only_in_linux: knownOnlyLinux,
      known_only_in_windows: knownOnlyWindows,
    },
    null,
    2
  )
);
