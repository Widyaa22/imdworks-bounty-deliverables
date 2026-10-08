"""Canonical IMD Works brief serialization and legacy Keccak-256."""
import json

FIELDS = ("title", "description", "criteria", "reward", "token", "deadline")
MASK = (1 << 64) - 1
RC = (0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008)
ROT = ((0,36,3,41,18),(1,44,10,45,2),(62,6,43,15,61),(28,55,25,21,56),(27,20,39,8,14))

class BriefError(ValueError): pass

def canonicalize(value):
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise BriefError("brief must be an object with exactly: " + ", ".join(FIELDS))
    if any(not isinstance(value[k], str) for k in FIELDS):
        raise BriefError("every brief field must be a string")
    if any(any(0xD800 <= ord(ch) <= 0xDFFF for ch in value[k]) for k in FIELDS):
        raise BriefError("field strings must contain only Unicode scalar values")
    text = "{" + ",".join(json.dumps(k)+":"+json.dumps(value[k], ensure_ascii=False, separators=(",", ":")) for k in FIELDS) + "}"
    return text.encode("utf-8")

def _rol(x, n):
    return x if n == 0 else ((x << n) | (x >> (64-n))) & MASK

def _permute(a):
    for rc in RC:
        c=[a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
        d=[c[(x-1)%5]^_rol(c[(x+1)%5],1) for x in range(5)]
        for x in range(5):
            for y in range(5): a[x+5*y]^=d[x]
        b=[0]*25
        for x in range(5):
            for y in range(5): b[y+5*((2*x+3*y)%5)] = _rol(a[x+5*y], ROT[x][y])
        for x in range(5):
            for y in range(5): a[x+5*y]=b[x+5*y]^((~b[(x+1)%5+5*y])&b[(x+2)%5+5*y])
        a[0]^=rc

def keccak256(data):
    rate=136
    padded=bytearray(data); padded.append(0x01)
    while len(padded)%rate != rate-1: padded.append(0)
    padded.append(0x80)
    a=[0]*25
    for off in range(0,len(padded),rate):
        block=padded[off:off+rate]
        for i in range(rate//8): a[i]^=int.from_bytes(block[i*8:i*8+8],"little")
        _permute(a)
    return b"".join(x.to_bytes(8,"little") for x in a)[:32]

def hash_brief(value): return "0x"+keccak256(canonicalize(value)).hex()
