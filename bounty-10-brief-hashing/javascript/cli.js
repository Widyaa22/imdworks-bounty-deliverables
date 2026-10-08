#!/usr/bin/env node
"use strict";
const fs=require("fs"), {canonicalize,hashBrief}=require("./brief-hash");
const values=JSON.parse(fs.readFileSync(0,"utf8"));
process.stdout.write(JSON.stringify(values.map(v=>{
  try { return {canonical_hex:canonicalize(v).toString("hex"),keccak256:hashBrief(v)}; }
  catch (e) { return {error:e.name}; }
})));
