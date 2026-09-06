#!/usr/bin/env node
'use strict';

// append-ledger.js — SKILL.md 手順5(Dを選んだ場合)から呼ばれるnode実装。
// ledger.jsonへ新しい許容差分エントリを追記する(既存エントリは残したまま追記=上書きしない)。jqに依存しない。
//
// 使い方: node append-ledger.js <ledger.json> <file> <linux_hash> <windows_hash> <reason>

const fs = require('fs');

const [, , ledgerPath, file, linuxHash, windowsHash, reason] = process.argv;

if (!ledgerPath || !file || !linuxHash || !windowsHash || !reason) {
  console.error(
    'usage: node append-ledger.js <ledger.json> <file> <linux_hash> <windows_hash> <reason>'
  );
  process.exit(1);
}

let ledger = [];
if (fs.existsSync(ledgerPath)) {
  const raw = fs.readFileSync(ledgerPath, 'utf8').trim();
  ledger = raw ? JSON.parse(raw) : [];
}

const recordedAt = new Date().toISOString().slice(0, 10);

ledger.push({
  file,
  linux_hash: linuxHash,
  windows_hash: windowsHash,
  reason,
  recorded_at: recordedAt,
});

fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + '\n');
console.log(`Recorded: ${file} (${recordedAt})`);
