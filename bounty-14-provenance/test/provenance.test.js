import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { verifyProvenance } from '../lib/provenance.js';

const root = path.resolve(import.meta.dirname, '..');
const runtime = fs.readFileSync(path.join(root, 'fixtures/deployed-runtime.hex'), 'utf8').trim();

function base(overrides = {}) {
  return { root, deployedRuntime: runtime, writeEvidence: false, ...overrides };
}

test('published sources rebuild to exact deployed runtime after immutable substitution', () => {
  const r = verifyProvenance(base());
  assert.equal(r.status, 'pass');
  assert.equal(r.comparison.exactMatch, true);
  assert.equal(r.immutable.address, '0x5fc5360d0400a0fd4f2af552add042d716f1d168');
  assert.equal(r.immutable.references.length, 9);
  assert.equal(r.comparison.differingBytes, 0);
});

test('changing one source statement fails verification', () => {
  const source = fs.readFileSync(path.join(root, 'src/IMDWorksEscrow.sol'), 'utf8');
  const mutated = source.replace('uint256 public constant MIN_DURATION = 1 hours;', 'uint256 public constant MIN_DURATION = 2 hours;');
  assert.notEqual(mutated, source);
  const r = verifyProvenance(base({ sourceOverrides: { 'src/IMDWorksEscrow.sol': mutated } }));
  assert.equal(r.status, 'fail');
  assert.equal(r.comparison.exactMatch, false);
  assert.ok(r.comparison.differingBytes > 0);
});

test('changing token address fails verification', () => {
  const r = verifyProvenance(base({ tokenAddress: '0x0000000000000000000000000000000000000001' }));
  assert.equal(r.status, 'fail');
  assert.equal(r.comparison.exactMatch, false);
  assert.equal(r.comparison.differingBytes, 171);
});

test('dependency hashes cover every compiler input and identify OZ 5.4.0', () => {
  const r = verifyProvenance(base());
  assert.equal(r.integrity.sources.length, 8);
  assert.match(r.integrity.openzeppelinPackageSha256, /^[0-9a-f]{64}$/);
  assert.ok(r.integrity.sources.every(x => /^[0-9a-f]{64}$/.test(x.sha256)));
  assert.equal(r.compiler.version, '0.8.29+commit.ab55807c.Emscripten.clang');
  assert.deepEqual(r.compiler.optimizer, { enabled: true, runs: 200 });
  assert.equal(r.compiler.evmVersion, 'paris');
});
