#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { verifyProvenance } from './lib/provenance.js';

const root = import.meta.dirname;
const args = process.argv.slice(2);
const rpcIndex = args.indexOf('--rpc');
let deployedRuntime;
let acquisition;

if (rpcIndex >= 0) {
  const rpc = args[rpcIndex + 1];
  if (!rpc) throw new Error('--rpc requires a URL');
  const response = await fetch(rpc, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getCode', params: ['0xd93aEd6f9F89699969B4967364D464fe7856EFaE', 'latest'] })
  });
  if (!response.ok) throw new Error(`RPC HTTP ${response.status}`);
  const body = await response.json();
  if (body.error || !body.result || body.result === '0x') throw new Error(`RPC eth_getCode failed: ${JSON.stringify(body.error ?? body)}`);
  deployedRuntime = body.result;
  acquisition = { mode: 'live', rpc, method: 'eth_getCode', blockTag: 'latest' };
  fs.writeFileSync(path.join(root, 'evidence/live-runtime.hex'), `${deployedRuntime}\n`);
} else {
  deployedRuntime = fs.readFileSync(path.join(root, 'fixtures/deployed-runtime.hex'), 'utf8').trim();
  acquisition = { mode: 'offline-fixture', fixture: 'fixtures/deployed-runtime.hex', originallyFetchedFrom: 'https://rpc.mainnet.chain.robinhood.com', method: 'eth_getCode', blockTag: 'latest' };
}

const tokenIndex = args.indexOf('--token');
const tokenAddress = tokenIndex >= 0 ? args[tokenIndex + 1] : undefined;
const result = verifyProvenance({ root, deployedRuntime, tokenAddress, writeEvidence: true });
result.acquisition = acquisition;
fs.writeFileSync(path.join(root, 'evidence/report.json'), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
process.exitCode = result.status === 'pass' ? 0 : 1;
