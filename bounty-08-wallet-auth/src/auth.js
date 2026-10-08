import crypto from 'node:crypto';
import http from 'node:http';
import { getAddress, verifyMessage } from 'ethers';

const TITLE = 'IMD Works Wallet Sign-In';
const MAX_BODY = 16_384;

function fail(message) { throw new Error(message); }
function canonicalAddress(value) {
  if (typeof value !== 'string' || !/^0x[0-9a-fA-F]{40}$/.test(value)) fail('invalid address');
  try { return getAddress(value).toLowerCase(); } catch { fail('invalid address'); }
}
function validOrigin(value) {
  if (typeof value !== 'string') return false;
  try { const u=new URL(value); return (u.protocol==='https:'||u.protocol==='http:') && u.origin===value && !u.username && !u.password; } catch { return false; }
}
function validChain(value) { return Number.isSafeInteger(value) && value > 0; }
function timingEqual(a,b) {
  const x=Buffer.from(a), y=Buffer.from(b); return x.length===y.length && crypto.timingSafeEqual(x,y);
}

export function buildMessage(c) {
  return `${TITLE}\nAddress: ${c.address.toLowerCase()}\nOrigin: ${c.origin}\nChain ID: ${c.chainId}\nNonce: ${c.nonce}\nIssued At: ${c.issuedAt}\nExpiration Time: ${c.expiresAt}`;
}

export class WalletAuthService {
  constructor({allowedOrigins,allowedChainIds,clock=Date.now,ttlMs=300_000}) {
    this.origins=new Set(allowedOrigins); this.chains=new Set(allowedChainIds); this.clock=clock; this.ttlMs=ttlMs;
    this.challenges=new Map(); this.sessions=new Map();
    if (![...this.origins].every(validOrigin)) fail('invalid configured origin');
    if (![...this.chains].every(validChain)) fail('invalid configured chain');
  }
  async issueChallenge({address,origin,chainId}) {
    address=canonicalAddress(address);
    if (!validOrigin(origin) || !this.origins.has(origin)) fail('origin not allowed');
    if (!validChain(chainId) || !this.chains.has(chainId)) fail('chain not allowed');
    const issuedAt=this.clock(), expiresAt=issuedAt+this.ttlMs, nonce=crypto.randomBytes(32).toString('hex');
    const c=Object.freeze({address,origin,chainId,nonce,issuedAt,expiresAt});
    this.challenges.set(nonce,{...c,state:'fresh'}); return c;
  }
  async verify({c,message,signature}) {
    if (!c || typeof c!=='object') fail('invalid challenge');
    if (typeof c.nonce!=='string' || !/^[0-9a-f]{64}$/.test(c.nonce)) fail('invalid nonce');
    const stored=this.challenges.get(c.nonce);
    if (!stored) fail('unknown nonce');
    // Atomic in JS: state is consumed synchronously before the first possible yield.
    if (stored.state!=='fresh') fail('nonce already consumed');
    stored.state='consumed';
    if (this.clock() >= stored.expiresAt) fail('challenge expired');
    if (stored.issuedAt > this.clock()) fail('challenge issued in future');
    for (const key of ['address','origin','chainId','nonce','issuedAt','expiresAt']) if (c[key] !== stored[key]) fail('challenge mismatch');
    if (!this.origins.has(stored.origin)) fail('origin not allowed');
    if (!this.chains.has(stored.chainId)) fail('chain not allowed');
    const expected=buildMessage(stored);
    if (typeof message!=='string' || !timingEqual(message,expected)) fail('message mismatch');
    if (typeof signature!=='string' || !/^0x[0-9a-fA-F]{130}$/.test(signature)) fail('malformed signature');
    let recovered; try { recovered=verifyMessage(expected,signature).toLowerCase(); } catch { fail('malformed signature'); }
    if (recovered!==stored.address) fail('wrong signer');
    const sessionToken=crypto.randomBytes(32).toString('hex');
    const session=Object.freeze({sessionToken,address:stored.address,origin:stored.origin,chainId:stored.chainId,authenticatedAt:this.clock()});
    this.sessions.set(sessionToken,session); return session;
  }
  getSession(token) { return this.sessions.get(token); }
}

// Deliberately vulnerable negative-control: never consumes a nonce.
export class ReplayableAuthService extends WalletAuthService {
  async verify(input) { const stored=this.challenges.get(input.c.nonce); const state=stored?.state; const out=await super.verify(input); if(stored) stored.state=state; return out; }
}

// Deliberately vulnerable negative-control: signs only a nonce and ignores context.
export class ContextBlindAuthService extends WalletAuthService {
  async verify({c,message,signature}) {
    const stored=this.challenges.get(c.nonce); if(!stored||stored.state!=='fresh') fail('nonce'); stored.state='consumed';
    let recovered; try { recovered=verifyMessage(message,signature).toLowerCase(); } catch { fail('signature'); }
    if(message!==stored.nonce||recovered!==stored.address) fail('signer');
    return {sessionToken:crypto.randomBytes(32).toString('hex'),address:stored.address,origin:c.origin,chainId:c.chainId,authenticatedAt:this.clock()};
  }
}

async function readJson(req) {
  let size=0, chunks=[]; for await (const chunk of req) { size+=chunk.length; if(size>MAX_BODY) fail('body too large'); chunks.push(chunk); }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
function send(res,status,value){ const body=JSON.stringify(value); res.writeHead(status,{'content-type':'application/json','content-length':Buffer.byteLength(body),'cache-control':'no-store'}); res.end(body); }
export function createHttpServer(service) {
  return http.createServer(async(req,res)=>{ try {
    if(req.method!=='POST') return send(res,405,{error:'method not allowed'});
    const body=await readJson(req);
    if(req.url==='/nonce') return send(res,200,await service.issueChallenge(body));
    if(req.url==='/verify') return send(res,200,await service.verify(body));
    return send(res,404,{error:'not found'});
  } catch(e) { return send(res,400,{error:e.message}); } });
}
