#!/usr/bin/env python3
import json, sys
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'python'))
from brief_hash import canonicalize, hash_brief

base={"title":"Title","description":"Description","criteria":"Criteria","reward":"1","token":"USDG","deadline":"2026-10-14T09:54:30.000Z"}
cases=[]
def add(name,**changes):
 v=base|changes; cases.append({"name":name,"input":v,"canonical_hex":canonicalize(v).hex(),"keccak256":hash_brief(v)})
add("baseline")
values=[
 ("empty-title",{"title":""}),("all-empty",dict.fromkeys(base,"")),
 ("lf",{"description":"a\nb"}),("crlf",{"description":"a\r\nb"}),("cr",{"description":"a\rb"}),
 ("composed",{"title":"café"}),("decomposed",{"title":"cafe\u0301"}),
 ("emoji",{"title":"🚀"}),("non-bmp",{"title":"𝄞"}),("cjk",{"title":"中文"}),
 ("arabic",{"title":"مرحبا"}),("rtl-mark",{"title":"a\u200fb"}),("nul",{"title":"a\u0000b"}),
 ("tab",{"title":"a\tb"}),("quote",{"title":"\""}),("backslash",{"title":"\\"}),
 ("slashes",{"title":"</script>"}),("spaces",{"title":"  x  "}),("nbsp",{"title":"a\u00a0b"}),
 ("line-separator",{"title":"a\u2028b"}),("paragraph-separator",{"title":"a\u2029b"}),
 ("combining-stack",{"title":"a\u0301\u0327"}),("hangul-composed",{"title":"한"}),
 ("hangul-decomposed",{"title":"한"}),("fullwidth",{"title":"Ａ"}),
 ("angstrom",{"title":"Å"}),("angstrom-sign",{"title":"Å"}),
 ("reward-zero-string",{"reward":"0"}),("reward-leading-zero",{"reward":"01"}),
 ("reward-decimal",{"reward":"1.0"}),("reward-exponent",{"reward":"1e0"}),
 ("reward-negative",{"reward":"-1"}),("reward-huge",{"reward":"9007199254740993"}),
 ("token-empty",{"token":""}),("token-lower",{"token":"usdg"}),("token-unicode",{"token":"ＵＳＤＧ"}),
 ("deadline-empty",{"deadline":""}),("deadline-offset",{"deadline":"2026-10-14T11:54:30+02:00"}),
 ("deadline-no-ms",{"deadline":"2026-10-14T09:54:30Z"}),("deadline-space",{"deadline":" 2026-10-14T09:54:30.000Z "}),
 ("empty-description",{"description":""}),("empty-criteria",{"criteria":""}),
 ("json-looking",{"criteria":"{\"admin\":true}"}),("array-looking",{"criteria":"[1,2]"}),
 ("prototype-key-text",{"criteria":"__proto__"}),("constructor-text",{"criteria":"constructor"}),
 ("html-hostile",{"description":"<img src=x onerror=alert(1)>"}),
 ("sql-hostile",{"description":"' OR 1=1 --"}),("shell-hostile",{"description":"$(rm -rf /)"}),
 ("bidi-override",{"description":"abc\u202egpj.exe"}),("unicode-newline",{"description":"a\u0085b"}),
 ("long",{"description":"x"*4096}),("leading-newline",{"description":"\nx"}),
 ("trailing-newline",{"description":"x\n"}),("multiple-lines",{"description":"a\n\nb\n"}),
 ("mixed-endings",{"description":"a\r\nb\nc\r"}),("variation-selector",{"title":"❤\ufe0f"}),
 ("zwj",{"title":"👩\u200d💻"}),("zero-width-space",{"title":"a\u200bb"}),
 ("replacement-char",{"title":"�"}),("del",{"title":"a\u007fb"}),
]
for n,c in values:add(n,**c)
rejected=[
 {"name":"missing-field","input":{k:v for k,v in base.items() if k!='token'}},
 {"name":"extra-field","input":base|{"extra":"x"}},
 {"name":"nested-criteria","input":base|{"criteria":{"admin":True}}},
 {"name":"array-criteria","input":base|{"criteria":[]}},
 {"name":"numeric-reward","input":base|{"reward":1}},
 {"name":"null-title","input":base|{"title":None}},
 {"name":"boolean-token","input":base|{"token":False}},
 {"name":"root-array","input":[]},
 {"name":"root-null","input":None},
]
out={"spec_version":"imdworks-brief-v1","accepted":cases,"rejected":rejected}
(ROOT/'vectors.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(f"generated {len(cases)} accepted and {len(rejected)} rejected vectors")
