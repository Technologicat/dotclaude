# Strata setup: Qwen3.8 Flash Next on the work machine

[Strata](https://github.com/Niko1221/Strata) is a MoE inference engine with an OpenAI- and Anthropic-compatible
HTTP server. Here it runs Qwen3.8 Flash Next (IQ3_S, 200K context, `q4_0` KV) on the work machine, served on the
LAN so the personal machine can call it. Measured decode: over 50 tok/s. While running it takes nearly all of the
work machine's RAM, so little else can run beside it; LM Studio (see `NEW-MACHINE-SETUP.md`) remains the usual server.

This doc records the setup as of 2026-10-30, against Strata Terminal 0.1.47. Source pointers below name functions
in that version's `serve/server.py` and `strata_cli/launch/runner.py`, under
`~/.local/share/strata/terminal/<version>/`. Expect line numbers, and possibly file layouts, to drift.

## Wanted defaults

- Sampling: temperature 1, `min_p` 0.02, every other sampler off.
- Max output tokens per request: 16,384.
- Thinking budget: 12,288 tokens.

Each of these is only a *default*: a request that sends its own value wins.

## Where the settings live

Strata spreads its configuration across four files, and the obvious one is the wrong one.

| File | Owner | Holds |
| --- | --- | --- |
| `~/.local/share/strata/install/strata-<model>.json` | setup | The **base run config**. Edit this one for the `sampling` block and `reasoning_budget_tokens`. `strata models inspect <model>` prints its path. |
| `~/.local/state/strata/launch/<preset>.json` | `strata launch` | The run config the server actually starts with. **Regenerated on every launch, so do not edit it**: `derive_config` copies the base config and overlays host, port, API key, GPU cards and the preset's `extra`. Keys in the base survive into it. |
| `~/.local/state/strata/launch/<preset>.shared-settings.json` | the server | The web UI's shared Chat settings. The **only** place a default `max_tokens` can be set. The web UI's About → Settings writes the same file. |
| `~/.config/strata/launch-presets/<preset>.json` | `strata launch` | The launch preset: access mode, the API key, and `extra` (engine flags applied on top of the base config's `args`). |

The settings themselves:

```jsonc
// base run config, top level (beside "exe" and "args")
"sampling": {
 "temperature": 1.0,
 "min_p": 0.02,
 "top_p": 1.0,
 "top_k": 64,
 "presence_penalty": 0,
 "frequency_penalty": 0,
 "repetition_penalty": 1.0
},
"reasoning_budget_tokens": 12288
```

```jsonc
// <preset>.shared-settings.json
{"max_tokens": 16384}
```

```jsonc
// launch preset
"extra": {"--vram-reserve-mib": "832"}
```

Re-running setup (an engine or model update) rewrites the base config. Strata's docs say setup keeps keys it does not
manage; not verified in the code, so check the `sampling` block is still there afterwards.

### Every "off" must be spelled out

Sampling defaults are merged **per key** (`Service._run`, `{**model_card_sampling(...), **sampling_defaults, **shared}`),
in increasing precedence: the built-in model card, the config's `sampling` block, the shared Chat settings, and
finally the request. A key the config leaves out falls through to the card, and the card for this model
(`MODEL_CARD_SAMPLING["qwen4exp"]`) is not neutral:

| | temperature | top_p | top_k | presence_penalty |
| --- | --- | --- | --- | --- |
| thinking | 1.0 | 0.95 | 20 | — |
| non-thinking | 0.7 | 0.8 | 20 | 1.5 |

So the block above sets every one of those keys, plus the two penalties the card does not use, to its neutral value.

### Limits on what can be expressed

- **`top_k` cannot be switched off.** The engine's sampled path keeps at most 64 candidates whatever is asked, and
  the config validator accepts only 1..64. So 64 is "off" as far as this engine goes. With `min_p` 0.02 it rarely
  matters: the cap only bites on a distribution flat across more than 64 tokens.
- **The two layers accept different keys.** The config's `sampling` block takes `min_p` but no `max_tokens`
  (`sampling_defaults_from_config`). The shared settings take `max_tokens` but reject `min_p` as unknown
  (`clean_shared_defaults`). Since shared settings also outrank the config, keep samplers out of the shared file.
- **The thinking budget is a hard cap.** At N tokens the server injects a short wrap-up line and `</think>`, and the
  wrap-up counts as output tokens.

## API key

A preset with `"access": "lan"` makes launch generate a key unless `--no-api-key` was given, and that key is then
required on **every** request, from localhost included — `_authorized` has no loopback exemption. The launch TUI
never displays it, while the web UI just reports that a key is needed.

- The key is `api_key` in the launch preset.
- In the web UI: About → Settings → API key. Kept in that browser's localStorage, so once per browser.
- From a client: `Authorization: Bearer <key>`, or `x-api-key: <key>`.

## Checking the effective defaults

The engine log does **not** show the per-request sampling: the server sends it to the engine in the `GEN …` command
on its input, which is not logged. And comparing two sampled outputs proves nothing, since Strata's docs say a
sampled result is not reproducible run to run even with a fixed seed.

Instead, ask the live server. `/props` reports the merged defaults, by the same merge the request path uses, and
`n_predict` from the shared settings:

```bash
K=$(python3 -c "import json;print(json.load(open('$HOME/.config/strata/launch-presets/iq3_s-200k.json'))['api_key'])")
curl -s -H "Authorization: Bearer $K" http://localhost:8080/props | python3 -m json.tool
curl -s -H "Authorization: Bearer $K" http://localhost:8080/settings
```

Expected: `top_p` 1.0 and `top_k` 64, where the model card says 0.95 and 20 — which is what shows the config block,
not the card, is being read — plus `min_p` 0.02, neutral penalties and `n_predict` 16384. `/props` does not report
`reasoning_budget_tokens`.

## VRAM headroom

The work machine also runs Raven-server on the same GPU. At one start the engine warned that only 436 MiB of VRAM
was free, and that below 512 MiB the driver can page GPU memory to system RAM, dropping decode to a few tok/s.
`--vram-reserve-mib 832` is the value it suggested, set in the preset's `extra` as a precaution: decode was fast at
the time.
