"use strict";
const FIELDS = ["title","description","criteria","reward","token","deadline"];
const MASK = (1n<<64n)-1n;
const RC = [1n,0x8082n,0x800000000000808an,0x8000000080008000n,0x808bn,0x80000001n,0x8000000080008081n,0x8000000000008009n,0x8an,0x88n,0x80008009n,0x8000000an,0x8000808bn,0x800000000000008bn,0x8000000000008089n,0x8000000000008003n,0x8000000000008002n,0x8000000000000080n,0x800an,0x800000008000000an,0x8000000080008081n,0x8000000000008080n,0x80000001n,0x8000000080008008n];
const ROT=[[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]];
class BriefError extends Error {}
function canonicalize(v) {
  if (v===null || Array.isArray(v) || typeof v!=="object" || Object.keys(v).length!==6 || !FIELDS.every(k=>Object.prototype.hasOwnProperty.call(v,k))) throw new BriefError("brief must contain exactly six canonical fields");
  if (!FIELDS.every(k=>typeof v[k]==="string")) throw new BriefError("every brief field must be a string");
  if (FIELDS.some(k=>{for(let i=0;i<v[k].length;i++){const c=v[k].charCodeAt(i);if(c>=0xd800&&c<=0xdbff){if(i+1>=v[k].length||v[k].charCodeAt(++i)<0xdc00||v[k].charCodeAt(i)>0xdfff)return true;}else if(c>=0xdc00&&c<=0xdfff)return true;}return false;})) throw new BriefError("field strings must contain only Unicode scalar values");
  return Buffer.from("{"+FIELDS.map(k=>JSON.stringify(k)+":"+JSON.stringify(v[k])).join(",")+"}","utf8");
}
function rol(x,n){n=BigInt(n); return n===0n?x:((x<<n)|(x>>(64n-n)))&MASK;}
function permute(a){for(const rc of RC){let c=[],d=[];for(let x=0;x<5;x++)c[x]=a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20];for(let x=0;x<5;x++)d[x]=c[(x+4)%5]^rol(c[(x+1)%5],1);for(let x=0;x<5;x++)for(let y=0;y<5;y++)a[x+5*y]^=d[x];let b=Array(25).fill(0n);for(let x=0;x<5;x++)for(let y=0;y<5;y++)b[y+5*((2*x+3*y)%5)]=rol(a[x+5*y],ROT[x][y]);for(let x=0;x<5;x++)for(let y=0;y<5;y++)a[x+5*y]=b[x+5*y]^((~b[(x+1)%5+5*y]&MASK)&b[(x+2)%5+5*y]);a[0]^=rc;}}
function keccak256(data){const rate=136,p=[...data,1];while(p.length%rate!==rate-1)p.push(0);p.push(128);let a=Array(25).fill(0n);for(let o=0;o<p.length;o+=rate){for(let i=0;i<17;i++){let n=0n;for(let j=0;j<8;j++)n|=BigInt(p[o+i*8+j])<<(8n*BigInt(j));a[i]^=n;}permute(a);}let out=Buffer.alloc(32);for(let i=0;i<4;i++)for(let j=0;j<8;j++)out[i*8+j]=Number((a[i]>>(8n*BigInt(j)))&255n);return out;}
function hashBrief(v){return "0x"+keccak256(canonicalize(v)).toString("hex");}
module.exports={FIELDS,BriefError,canonicalize,keccak256,hashBrief};
