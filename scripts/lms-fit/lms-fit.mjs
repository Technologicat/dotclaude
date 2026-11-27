#!/usr/bin/env node
// lms-fit: find how much of a model fits on the GPU in LM Studio, by loading it and generating.
//
//   lms-fit --list-gpus                                       # LM Studio's GPU device ids, for --disable-gpus
//   lms-fit qwen3.8-27b@q4_k_xl --knob layers --context 131072,196608 --kv-cache q4_0
//   lms-fit qwen3.6-35b-a3b --knob experts --context 262144 --kv-cache q4_0 --disable-gpus 1
//
// For each context it walks one knob toward more of the model on the GPU, from a safe start, a few layers at a
// time, until a point fails, and prints one row per point: the setting llama-server actually got, the VRAM in
// use on each GPU, and the speed of a 200-token generation.
//   --knob layers   the number of layers on the GPU, upward (a dense model)
//   --knob experts  every layer on the GPU, and the number of layers whose expert blocks stay in RAM, downward (a MoE)
//
// Columns: the context; the knob's value; what llama-server was started with (`ngl` layers on the GPU, or
// `n-cpu-moe` expert layers in RAM), which should equal the knob; VRAM in use/total per GPU, by nvidia-smi's
// index, which need not be LM Studio's device id; the generation's speed and time to first token; the result.
//
// Install, once per machine:
//   npm ci --prefix ~/.claude/scripts/lms-fit
//   ln -s ~/.claude/scripts/lms-fit/lms-fit.mjs ~/.local/bin/lms-fit
//
// A point fits only if the generation completes. A load can succeed and the first generation still die, near
// the edge (measured on a 16 GB card, 2026-11-27: ~450 MiB free or less), so a load alone proves nothing.
//
// Needs LM Studio running and nothing loaded in it (or --unload-others), and `npm ci` once in this folder, for
// LM Studio's SDK; the `lms` CLI cannot set the expert placement, the KV cache type or the GPUs per load.
// `gpuStrictVramCap` is off for every load, since with it on LM Studio quietly caps the offload to what it
// thinks fits, and the point tried is not the point asked for. Each model's saved settings in LM Studio
// otherwise apply, as they would in use: a vision projector, speculative decoding.
//
// LM Studio counts a model's layers as its blocks plus one, and rounds both offload ratios onto that count,
// so the script asks for N layers as the ratio N / (blocks + 1), with the blocks read from the GGUF header,
// and reports what llama-server's command line says it got.

import { execFileSync } from "node:child_process";
import { closeSync, openSync, readFileSync, readSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { LMStudioClient } from "@lmstudio/sdk";

const PROMPT = "In about 150 words: why did slide rules disappear so quickly in the 1970s?";
const IDENTIFIER = "lms-fit";

const { values: opts, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    knob: { type: "string", default: "layers" },
    context: { type: "string", default: "131072" },
    from: { type: "string" },
    step: { type: "string", default: "2" },
    "kv-cache": { type: "string" },
    "disable-gpus": { type: "string" },
    "max-tokens": { type: "string", default: "200" },
    "unload-others": { type: "boolean", default: false },
    "list-gpus": { type: "boolean", default: false },
    help: { type: "boolean", short: "h", default: false },
  },
});

function usage(code) {
  const lines = readFileSync(new URL(import.meta.url), "utf-8").split("\n").slice(1).filter((l) => l.startsWith("//"));
  console.log(lines.map((l) => l.slice(3)).join("\n"));
  process.exit(code);
}
if (opts.help) usage(0);

const sh = (cmd, args) => { try { return execFileSync(cmd, args, { encoding: "utf-8" }); } catch { return ""; } };

/** VRAM in use and in total on each GPU, as nvidia-smi sees them: "0: 14.0/16.0 GiB". */
function vram() {
  return sh("nvidia-smi", ["--query-gpu=index,memory.used,memory.total", "--format=csv,noheader,nounits"])
    .trim().split("\n").filter(Boolean).map((line) => {
      const [index, used, total] = line.split(",").map((x) => Number(x.trim()));
      return { index, usedMiB: used, totalMiB: total };
    });
}
const gib = (mib) => (mib / 1024).toFixed(1);

/** The offload llama-server was started with, from its command line. */
function served() {
  const pid = sh("pgrep", ["-x", "llama-server"]).trim().split("\n")[0];
  const cmd = pid ? sh("cat", [`/proc/${pid}/cmdline`]).split("\0") : [];
  const get = (flag) => (cmd.includes(flag) ? Number(cmd[cmd.indexOf(flag) + 1]) : null);
  return { gpuLayers: get("--n-gpu-layers"), cpuMoe: get("--n-cpu-moe") };
}

/** A GGUF file's `<architecture>.block_count`, read from its header. */
function blockCount(path) {
  const fd = openSync(path, "r");
  let offset = 0;
  const read = (n) => { const b = Buffer.alloc(n); readSync(fd, b, 0, n, offset); offset += n; return b; };
  const u32 = () => read(4).readUInt32LE(0), u64 = () => Number(read(8).readBigUInt64LE(0));
  const str = () => read(u64()).toString("utf-8");
  const SIZES = { 0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8 };
  const value = (type) => {
    if (type === 8) return str();
    if (type === 9) {
      const inner = u32(), n = u64();
      if (inner === 8) { for (let i = 0; i < n; i++) str(); } else offset += SIZES[inner] * n;
      return null;
    }
    const b = read(SIZES[type]);
    return { 4: () => b.readUInt32LE(0), 5: () => b.readInt32LE(0), 10: () => Number(b.readBigUInt64LE(0)) }[type]?.() ?? null;
  };
  try {
    if (read(4).toString("latin1") !== "GGUF") throw new Error(`${path}: not a GGUF file`);
    u32(); u64();
    const meta = {};
    for (let i = 0, n = u64(); i < n; i++) { const key = str(); meta[key] = value(u32()); }
    return meta[`${meta["general.architecture"]}.block_count`];
  } finally {
    closeSync(fd);
  }
}

function modelsDir() {
  try {
    return JSON.parse(readFileSync(join(homedir(), ".lmstudio", "settings.json"), "utf-8")).downloadsFolder;
  } catch {
    return join(homedir(), ".lmstudio", "models");
  }
}

const client = new LMStudioClient({ verboseErrorMessages: false });

if (opts["list-gpus"]) {
  for (const engine of (await client.runtime.surveyHardware()).engines) {
    for (const gpu of engine.hardwareSurvey.gpuSurveyResult.gpuInfo) {
      console.log(`${engine.engine}: device ${gpu.deviceId}  ${gpu.name}  ${gib(gpu.dedicatedMemoryCapacityBytes / 2 ** 20)} GiB  (${gpu.detectionPlatform})`);
    }
  }
  process.exit(0);
}

const [modelKey] = positionals;
if (!modelKey || !["layers", "experts"].includes(opts.knob)) usage(2);

const info = (await client.system.listDownloadedModels("llm")).find((m) => m.modelKey === modelKey);
if (!info) {
  console.error(`lms-fit: no downloaded model ${modelKey}; \`lms ls\` lists them`);
  process.exit(2);
}
const blocks = blockCount(join(modelsDir(), info.path));
const units = blocks + 1;

const loaded = await client.llm.listLoaded();
if (loaded.length > 0) {
  if (!opts["unload-others"]) {
    console.error(`lms-fit: loaded already: ${loaded.map((m) => m.identifier).join(", ")}. Unload them, or pass --unload-others.`);
    process.exit(2);
  }
  for (const m of loaded) await m.unload();
}

let current = null;
process.on("SIGINT", async () => {
  if (current) await current.unload().catch(() => {});
  process.exit(130);
});

const step = Number(opts.step);
const start = Number(opts.from ?? (opts.knob === "layers" ? Math.floor(units / 2) : Math.round(blocks * 0.6)));
const points = opts.knob === "layers"
  ? Array.from({ length: Math.floor((units - start) / step) + 1 }, (_, i) => start + i * step)
  : Array.from({ length: Math.floor(start / step) + 1 }, (_, i) => start - i * step);

console.log(`${modelKey}: ${blocks} blocks, ${units} layer units; knob ${opts.knob}, from ${start} by ${step}`
  + `${opts["kv-cache"] ? `; KV cache ${opts["kv-cache"]}` : ""}${opts["disable-gpus"] ? `; GPUs disabled: ${opts["disable-gpus"]}` : ""}`);
console.log(`before loading: ${vram().map((g) => `GPU ${g.index} ${gib(g.usedMiB)}/${gib(g.totalMiB)} GiB`).join(", ")}`);
console.log(["context", opts.knob === "layers" ? "on GPU" : "experts in RAM", "served", "VRAM in use", "tok/s", "TTFT s", "result"].join("\t"));

for (const context of opts.context.split(",").map(Number)) {
  for (const n of points) {
    const gpu = opts.knob === "layers"
      ? { ratio: n / units }
      : { ratio: "max", numCpuExpertLayersRatio: n / units };
    if (opts["disable-gpus"]) gpu.disabledGpus = opts["disable-gpus"].split(",").map(Number);
    const config = { contextLength: context, gpuStrictVramCap: false, gpu };
    if (opts["kv-cache"]) {
      Object.assign(config, { flashAttention: true, llamaKCacheQuantizationType: opts["kv-cache"], llamaVCacheQuantizationType: opts["kv-cache"] });
    }
    const row = [context, n];
    try {
      current = await client.llm.load(modelKey, { identifier: IDENTIFIER, config, verbose: false });
    } catch (error) {
      console.log([...row, "", "", "", "", `does not load: ${String(error.message).split("\n")[0].slice(0, 120)}`].join("\t"));
      break;
    }
    const got = served();
    row.push(opts.knob === "layers" ? `ngl ${got.gpuLayers}` : `n-cpu-moe ${got.cpuMoe}`);
    row.push(vram().map((g) => `${g.index}: ${gib(g.usedMiB)}/${gib(g.totalMiB)}`).join(", "));
    let failed = false;
    try {
      const result = await current.respond(PROMPT, { maxTokens: Number(opts["max-tokens"]) });
      row.push(result.stats.tokensPerSecond.toFixed(1), result.stats.timeToFirstTokenSec.toFixed(2), "fits");
    } catch (error) {
      row.push("", "", `loads, dies generating: ${String(error.message).split("\n")[0].slice(0, 100)}`);
      failed = true;
    }
    console.log(row.join("\t"));
    await current.unload().catch(() => {});
    current = null;
    if (failed) break;
  }
}
process.exit(0);
