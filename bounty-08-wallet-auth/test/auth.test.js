import test from 'node:test';
import assert from 'node:assert/strict';
import { Wallet } from 'ethers';
import {
  WalletAuthService, ReplayableAuthService, ContextBlindAuthService,
  buildMessage, createHttpServer
} from '../src/auth.js';

const ORIGIN = 'https://app.imdworks.test';
const CHAIN = 8453;
const NOW = 2_000_000_000_000;
const wallet = Wallet.createRandom();
const attacker = Wallet.createRandom();

async function challenge(service, overrides = {}) {
  return service.issueChallenge({ address: wallet.address, origin: ORIGIN, chainId: CHAIN, ...overrides });
}
async function signed(service, overrides = {}) {
  const c = await challenge(service);
  const message = buildMessage(c);
  return { c, message, signature: await wallet.signMessage(message), ...overrides };
}

function fresh(options = {}) {
  return new WalletAuthService({ allowedOrigins: [ORIGIN], allowedChainIds: [CHAIN], clock: () => NOW, ttlMs: 300_000, ...options });
}

const cases = [
  ['valid signature issues bound session', async () => {
    const s=fresh(), p=await signed(s), out=await s.verify(p);
    assert.equal(out.address, wallet.address.toLowerCase()); assert.equal(out.origin, ORIGIN); assert.equal(out.chainId, CHAIN);
  }],
  ['nonce replay rejected', async () => { const s=fresh(),p=await signed(s); await s.verify(p); await assert.rejects(s.verify(p), /nonce/); }],
  ['wrong signer rejected', async () => { const s=fresh(),p=await signed(s); p.signature=await attacker.signMessage(p.message); await assert.rejects(s.verify(p), /signer/); }],
  ['claimed address substitution rejected', async () => { const s=fresh(),p=await signed(s); p.c={...p.c,address:attacker.address}; await assert.rejects(s.verify(p), /challenge|message/); }],
  ['origin substitution rejected', async () => { const s=fresh(),p=await signed(s); p.c={...p.c,origin:'https://evil.test'}; await assert.rejects(s.verify(p), /origin|challenge|message/); }],
  ['origin suffix confusion rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{origin:'https://app.imdworks.test.evil.test'}), /origin/); }],
  ['origin userinfo confusion rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{origin:'https://app.imdworks.test@evil.test'}), /origin/); }],
  ['origin path rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{origin:ORIGIN+'/x'}), /origin/); }],
  ['origin case normalization rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{origin:'https://APP.imdworks.test'}), /origin/); }],
  ['wrong chain challenge rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{chainId:1}), /chain/); }],
  ['chain substitution rejected', async () => { const s=fresh(),p=await signed(s); p.c={...p.c,chainId:1}; await assert.rejects(s.verify(p), /chain|challenge|message/); }],
  ['expiry one millisecond before accepted', async () => { let now=NOW; const s=fresh({clock:()=>now,ttlMs:100}); const p=await signed(s); now=p.c.expiresAt-1; assert.ok(await s.verify(p)); }],
  ['expiry exact boundary rejected', async () => { let now=NOW; const s=fresh({clock:()=>now,ttlMs:100}); const p=await signed(s); now=p.c.expiresAt; await assert.rejects(s.verify(p), /expired/); }],
  ['expiry after boundary rejected', async () => { let now=NOW; const s=fresh({clock:()=>now,ttlMs:100}); const p=await signed(s); now=p.c.expiresAt+1; await assert.rejects(s.verify(p), /expired/); }],
  ['future issued-at rejected', async () => { const s=fresh(),p=await signed(s); p.c={...p.c,issuedAt:NOW+1}; await assert.rejects(s.verify(p), /challenge|message|future/); }],
  ['malformed short signature rejected', async () => { const s=fresh(),p=await signed(s); p.signature='0x1234'; await assert.rejects(s.verify(p), /signature/); }],
  ['non-hex signature rejected', async () => { const s=fresh(),p=await signed(s); p.signature='not-a-signature'; await assert.rejects(s.verify(p), /signature/); }],
  ['high-s malleable signature rejected', async () => { const s=fresh(),p=await signed(s); const bytes=Buffer.from(p.signature.slice(2),'hex'); bytes.fill(0xff,32,64); p.signature='0x'+bytes.toString('hex'); await assert.rejects(s.verify(p), /signature/); }],
  ['message whitespace mutation rejected', async () => { const s=fresh(),p=await signed(s); p.message += ' '; p.signature=await wallet.signMessage(p.message); await assert.rejects(s.verify(p), /message/); }],
  ['message field reordering rejected', async () => { const s=fresh(),p=await signed(s); p.message=p.message.replace(`Chain ID: ${CHAIN}\nNonce:`, `Nonce: X\nChain ID: ${CHAIN}\nNonce:`); p.signature=await wallet.signMessage(p.message); await assert.rejects(s.verify(p), /message/); }],
  ['unknown nonce rejected', async () => { const s=fresh(),p=await signed(s); p.c={...p.c,nonce:'0'.repeat(64)}; p.message=buildMessage(p.c); p.signature=await wallet.signMessage(p.message); await assert.rejects(s.verify(p), /nonce/); }],
  ['nonce belonging to other address rejected', async () => { const s=fresh(),p=await signed(s); const other=await s.issueChallenge({address:attacker.address,origin:ORIGIN,chainId:CHAIN}); p.c={...other,address:wallet.address}; p.message=buildMessage(p.c); p.signature=await wallet.signMessage(p.message); await assert.rejects(s.verify(p), /challenge/); }],
  ['duplicate challenge fields rejected through canonical mismatch', async () => { const s=fresh(),p=await signed(s); p.message += `\nNonce: ${p.c.nonce}`; p.signature=await wallet.signMessage(p.message); await assert.rejects(s.verify(p), /message/); }],
  ['concurrent verification permits exactly one success', async () => { const s=fresh(),p=await signed(s); const r=await Promise.allSettled(Array.from({length:32},()=>s.verify(p))); assert.equal(r.filter(x=>x.status==='fulfilled').length,1); assert.equal(r.filter(x=>x.status==='rejected').length,31); }],
  ['nonce has 256 bits of lowercase hex entropy', async () => { const s=fresh(),c=await challenge(s); assert.match(c.nonce,/^[0-9a-f]{64}$/); }],
  ['issued challenges use distinct nonces', async () => { const s=fresh(); const cs=await Promise.all(Array.from({length:128},()=>challenge(s))); assert.equal(new Set(cs.map(x=>x.nonce)).size,128); }],
  ['unsupported address format rejected', async () => { const s=fresh(); await assert.rejects(s.issueChallenge({address:'0x1234',origin:ORIGIN,chainId:CHAIN}),/address/); }],
  ['numeric-string chain ID rejected', async () => { const s=fresh(); await assert.rejects(challenge(s,{chainId:'8453'}),/chain/); }],
  ['oversized signature rejected', async () => { const s=fresh(),p=await signed(s); p.signature='0x'+'00'.repeat(10000); await assert.rejects(s.verify(p),/signature/); }],
  ['session token is opaque, unique, and server-backed', async () => { const s=fresh(),a=await s.verify(await signed(s)),b=await s.verify(await signed(s)); assert.match(a.sessionToken,/^[0-9a-f]{64}$/); assert.notEqual(a.sessionToken,b.sessionToken); assert.deepEqual(s.getSession(a.sessionToken),a); }],
];
for (const [name, fn] of cases) test(name, fn);

test('local HTTP service runs complete nonce/sign/verify flow', async t => {
  const service=fresh(), server=createHttpServer(service); await new Promise(r=>server.listen(0,'127.0.0.1',r)); t.after(()=>server.close());
  const base=`http://127.0.0.1:${server.address().port}`;
  const c=await (await fetch(base+'/nonce',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({address:wallet.address,origin:ORIGIN,chainId:CHAIN})})).json();
  const message=buildMessage(c), signature=await wallet.signMessage(message);
  const res=await fetch(base+'/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({c,message,signature})});
  assert.equal(res.status,200); assert.equal((await res.json()).address,wallet.address.toLowerCase());
});

test('conformance suite rejects replayable vulnerable implementation', async () => {
  const s=new ReplayableAuthService({allowedOrigins:[ORIGIN],allowedChainIds:[CHAIN],clock:()=>NOW,ttlMs:300000}); const p=await signed(s); await s.verify(p); await assert.doesNotReject(s.verify(p));
});
test('conformance suite rejects context-blind vulnerable implementation', async () => {
  const s=new ContextBlindAuthService({allowedOrigins:[ORIGIN],allowedChainIds:[CHAIN],clock:()=>NOW,ttlMs:300000});
  const c=await s.issueChallenge({address:wallet.address,origin:ORIGIN,chainId:CHAIN}); const message=c.nonce, signature=await wallet.signMessage(message);
  await assert.doesNotReject(s.verify({c:{...c,origin:'https://evil.test',chainId:1},message,signature}));
});
