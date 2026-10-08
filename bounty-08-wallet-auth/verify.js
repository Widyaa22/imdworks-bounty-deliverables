import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { Wallet } from 'ethers';
import { WalletAuthService, ReplayableAuthService, ContextBlindAuthService, buildMessage } from './src/auth.js';

const origin='https://app.imdworks.test', chainId=8453, now=2_000_000_000_000;
const opts={allowedOrigins:[origin],allowedChainIds:[chainId],clock:()=>now,ttlMs:300000};
const wallet=Wallet.createRandom();
async function payload(service){const c=await service.issueChallenge({address:wallet.address,origin,chainId}); const message=buildMessage(c); return {c,message,signature:await wallet.signMessage(message)};}
async function secureRejectsReplay(){const s=new WalletAuthService(opts),p=await payload(s); await s.verify(p); try{await s.verify(p);return false}catch{return true}}
async function secureRejectsContext(){const s=new WalletAuthService(opts),p=await payload(s); p.c={...p.c,origin:'https://evil.test'}; try{await s.verify(p);return false}catch{return true}}
async function replayExploitWorks(){const s=new ReplayableAuthService(opts),p=await payload(s); await s.verify(p); await s.verify(p); return true}
async function contextExploitWorks(){const s=new ContextBlindAuthService(opts),c=await s.issueChallenge({address:wallet.address,origin,chainId}); const message=c.nonce,signature=await wallet.signMessage(message); await s.verify({c:{...c,origin:'https://evil.test',chainId:1},message,signature}); return true}

const tests=spawnSync(process.execPath,['--test','--test-concurrency=1'],{encoding:'utf8'});
const checks={secure_rejects_replay:await secureRejectsReplay(),secure_rejects_context_substitution:await secureRejectsContext(),replayable_negative_control_exploited:await replayExploitWorks(),context_blind_negative_control_exploited:await contextExploitWorks()};
const matches=[...tests.stdout.matchAll(/^ok \d+ - /gm)];
const report={status:tests.status===0&&Object.values(checks).every(Boolean)?'pass':'fail',generated_test_wallets_only:true,network:'local-only',test_count:matches.length,test_exit_code:tests.status,negative_controls_rejected:checks,reproducibility:{node:process.version,dependency:'ethers@6.17.0',command:'npm ci && npm run verify'}};
writeFileSync('results.json',JSON.stringify(report,null,2)+'\n');
process.stdout.write(tests.stdout); process.stderr.write(tests.stderr); console.log(JSON.stringify(report,null,2));
if(report.status!=='pass') process.exit(1);
