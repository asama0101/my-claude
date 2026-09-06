#!/usr/bin/env node
'use strict';

// show-ledger.js — show-ledger.sh から呼ばれるnode実装。
// ledger.json(許容差分の台帳)をMarkdown表に整形して標準出力へ出す。jqに依存しない。

const fs = require('fs');

const [, , ledgerPath] = process.argv;

let data = [];
if (fs.existsSync(ledgerPath)) {
  const raw = fs.readFileSync(ledgerPath, 'utf8').trim();
  data = raw ? JSON.parse(raw) : [];
}

if (!Array.isArray(data) || data.length === 0) {
  console.log('台帳(ledger.json)はまだ空です。許容済みの差分はありません。');
  process.exit(0);
}

const sorted = [...data].sort((a, b) => {
  if (a.file !== b.file) return a.file < b.file ? -1 : 1;
  const ra = a.recorded_at || '';
  const rb = b.recorded_at || '';
  return ra < rb ? -1 : ra > rb ? 1 : 0;
});

console.log('| ファイル | 記録日 | 理由 |');
console.log('|---|---|---|');
for (const e of sorted) {
  console.log(`| ${e.file} | ${e.recorded_at} | ${e.reason} |`);
}
