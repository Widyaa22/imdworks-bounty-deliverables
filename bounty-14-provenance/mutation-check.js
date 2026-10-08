#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { verifyProvenance } from './lib/provenance.js';

const root = import.meta.dirname;
const deployedRuntime = fs.readFileSync(path.join(root, 'fixtures/deployed-runtime.hex'), 'utf8').trim();
const original = fs.readFileSync(path.join(root, 'src/IMDWorksEscrow.sol'), 'utf8');
const mutated = original.replace(
  'uint256 public constant MIN_DURATION = 1 hours;',
  'uint256 public constant MIN_DURATION = 2 hours;'
);
if (mutated === original) throw new Error('source mutation anchor not found');
const source = verifyProvenance({
  root, deployedRuntime, writeEvidence: false,
  sourceOverrides: { 'src/IMDWorksEscrow.sol': mutated }
});
const token = verifyProvenance({
  root, deployedRuntime, writeEvidence: false,
  tokenAddress: '0x0000000000000000000000000000000000000001'
});
const evidence = {
  schemaVersion: 1,
  expectedOutcome: 'both mutations must fail exact byte verification',
  pass: source.status === 'fail' && token.status === 'fail',
  sourceMutation: {
    from: 'uint256 public constant MIN_DURATION = 1 hours;',
    to: 'uint256 public constant MIN_DURATION = 2 hours;',
    verifierStatus: source.status,
    comparison: source.comparison
  },
  tokenMutation: {
    from: source.immutable.derivedFromDeployedRuntime,
    to: token.immutable.address,
    verifierStatus: token.status,
    comparison: token.comparison
  }
};
fs.writeFileSync(path.join(root, 'evidence/mutations.json'), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify(evidence, null, 2));
process.exitCode = evidence.pass ? 0 : 1;
