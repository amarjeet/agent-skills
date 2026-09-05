---
name: dgx-spark-layout
description: "Keep model weights and compiler caches out of individual experiment directories on a DGX Spark (or any single-node CUDA host) by pinning them to each tool's own standard default location. Triggers: new experiment, model server, dgx spark layout, where should the model download go, HF_HOME, hugging face cache, vllm cache, llama.cpp cache, triton cache, duplicated model downloads, disk full from model weights, bind mount cache into container."
compatibility: "Linux host with bash. Written for an NVIDIA DGX Spark (GB10, aarch64) but the storage rules apply to any single-node CUDA machine running vLLM, SGLang, llama.cpp or Hugging Face tooling. Docker is optional; both containerized and native workflows are covered."
license: MIT
---

# DGX Spark experiment storage layout

## Overview

Experiments are small; their data is not. A single quantized checkpoint runs 60–80 GB, and a compiler cache rebuilt per experiment costs minutes of every cold start. The failure mode this skill prevents is a *dir-local* cache default — `./.cache` inside the experiment directory — which silently duplicates the same weights once per experiment until the disk fills.

The rule is one sentence: **heavyweight, reusable data lives exactly once, at each tool's own standard default location** — the path the tool uses with no configuration at all. An experiment directory holds code, config, and manifests. Nothing heavy.

That splits every path into two categories, and they are governed differently:

- **Tool caches.** Not a matter of preference. Each tool already has a documented default and an env var that overrides it; use both as-is. This is the universal part of this skill and the table below is the reference.
- **The workspace root.** Your own convention, for data no tool has an opinion about — non-HF weights, run outputs, docker build contexts. This skill writes it as `${DGX_SPARK_ROOT}`, defaulting to `~/dgx-spark`. Set it to whatever you like; nothing below depends on the name.

```bash
DGX_SPARK_ROOT="${DGX_SPARK_ROOT:-${HOME}/dgx-spark}"
```

Experiments live in `${DGX_SPARK_ROOT}/experiments/<name>/`.

| Data | Host path | Env var the tool actually reads (default) |
|---|---|---|
| HF hub cache, datasets, xet, modules | `~/.cache/huggingface/` | `HF_HOME` (`~/.cache/huggingface`) |
| vLLM torch.compile cache | `~/.cache/vllm/` | `VLLM_CACHE_ROOT` (`~/.cache/vllm`) |
| flashinfer JIT/autotune cache | `~/.cache/flashinfer/<version>/<arch>/` | `FLASHINFER_WORKSPACE_BASE` (default `~`; cache lands at `$BASE/.cache/flashinfer/`) |
| triton kernel cache | `~/.triton/cache/` | `TRITON_CACHE_DIR` (`~/.triton/cache`; `TRITON_HOME` moves the whole `.triton` tree) |
| tilelang kernel cache | `~/.tilelang/cache/` | `TILELANG_CACHE_DIR` (`~/.tilelang/cache`) |
| llama.cpp GGUF downloads | `~/.cache/llama.cpp/` | `LLAMA_CACHE` (`~/.cache/llama.cpp`) |
| non-HF model weights | `${DGX_SPARK_ROOT}/base-models/` | — |
| non-HF datasets | `${DGX_SPARK_ROOT}/datasets/` | — |
| run outputs / checkpoints | `${DGX_SPARK_ROOT}/outputs/` | — |
| docker build contexts / images | `${DGX_SPARK_ROOT}/docker/` | — |

Env var names and defaults are verified against the tools' own source, not against any wrapper's conventions. Verify again when a tool major-versions: `triton` moved its cache resolution from `runtime/cache.py` to `knobs.py`, and the name `FLASHINFER_CACHE_DIR` exists in flashinfer's source as a *derived constant*, not as an env var it reads.

## Instructions

### 1. Never introduce a dir-local cache default

No `./.cache`, and no hardcoded `${DGX_SPARK_ROOT}` cache path either. Every storage path in a script is an env-overridable variable whose default is the standard location from the table:

```bash
LLAMA_CACHE="${LLAMA_CACHE:-${HOME}/.cache/llama.cpp}"     # good
LLAMA_CACHE="${EXPERIMENT_DIR}/.cache"                      # never
```

The override is what makes the recipe portable; the default is what makes it correct out of the box.

### 2. Docker experiments: bind-mount to the in-container default

Define host-side variables, then mount each to the *same path the tool defaults to inside the container*. When the mount target is already the tool's default, the tool needs no cache env vars at all — prefer that over setting them.

```bash
# Host-side mount sources. These names are this script's convention, not env
# vars the tools read — except HF_HOME and LLAMA_CACHE, which are real.
HF_HOME="${HF_HOME:-${HOME}/.cache/huggingface}"
VLLM_CACHE_DIR="${VLLM_CACHE_DIR:-${HOME}/.cache/vllm}"
FLASHINFER_CACHE_DIR="${FLASHINFER_CACHE_DIR:-${HOME}/.cache/flashinfer}"
TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-${HOME}/.triton}"
LLAMA_CACHE="${LLAMA_CACHE:-${HOME}/.cache/llama.cpp}"
mkdir -p "${HF_HOME}" "${VLLM_CACHE_DIR}" "${FLASHINFER_CACHE_DIR}" "${TRITON_CACHE_DIR}"
```

```bash
-e HF_TOKEN="${HF_TOKEN:-}" \
-v "${HF_HOME}:/root/.cache/huggingface" \
-v "${VLLM_CACHE_DIR}:/root/.cache/vllm" \
-v "${FLASHINFER_CACHE_DIR}:/root/.cache/flashinfer" \
-v "${TRITON_CACHE_DIR}:/root/.triton" \
```

Mount whole default *trees* (`~/.triton`, not `~/.triton/cache`) so the tool's own sub-layout applies inside. If you do set an in-container cache env var, point it at that tool's exact default path so containerized and native runs share one set of files.

Derive the container-side path from the host variable rather than writing it twice, and assert the relationship holds — a `MODEL_STORE` pointed outside the mounted tree produces a container path that does not exist, and you find out minutes into a cold load:

```bash
[[ "${MODEL_ROOT}" == "${LLAMA_CACHE}"/* ]] || {
  printf 'error: MODEL_ROOT is outside LLAMA_CACHE, so the bind mount cannot reach it\n' >&2
  exit 1
}
```

### 3. Native experiments: export the variable the tool actually reads

With no bind mount there is nothing to redirect, so the env var must be the real one — the third column of the table. `VLLM_CACHE_DIR` and `FLASHINFER_CACHE_DIR` are meaningless here: vLLM reads `VLLM_CACHE_ROOT`, flashinfer reads `FLASHINFER_WORKSPACE_BASE`.

Best case, export nothing. The defaults are already the shared locations.

### 4. spark-vllm-docker uses its own override names

[`eugr/spark-vllm-docker`](https://github.com/eugr/spark-vllm-docker) is a common way to run vLLM on DGX Spark. Its `launch-cluster.sh` reads host-side names of its own — `VLLM_CACHE_HOST_DIR`, `FLASHINFER_CACHE_HOST_DIR`, `TRITON_CACHE_HOST_DIR`, `TILELANG_CACHE_HOST_DIR` — whose defaults already match this table. Exporting `VLLM_CACHE_DIR` there does nothing. Normally export nothing and let its defaults work.

### 5. Wrappers are thin launchers, not path setters

A wrapper at `${DGX_SPARK_ROOT}/scripts/run-<name>.sh` is optional and exists for launch conveniences only: recipe selection, port publishing, token forwarding, running preflight before a long load. It must **not** set cache paths — the defaults already point at shared storage. A wrapper that sets a cache path is a wrapper that will disagree with the recipe it wraps.

### 6. Containers write cache files as root

To delete or restructure a cache directory as your normal user, either use `sudo` or do the file operations in a throwaway container:

```bash
docker run --rm -v "$HOME:/h" busybox sh -c 'rm -rf /h/.cache/vllm/torch_compile_cache'
```

### When writing a new experiment

1. Look up the new tool's *own* documented cache env var and default location, in its source or docs. Do not assume a `<TOOL>_CACHE_DIR` exists — several tools have no such variable, and at least one defines that exact name internally without reading it from the environment. The cache goes at the tool's default, never under the workspace root.
2. Docker → rule 2 (mount to in-container defaults). Native → rule 3 (export the real variable, or nothing at all).
3. Keep the experiment directory to code, config, and manifests. Weights, checkpoints, bench output and verification stamps all live outside it.
4. Add a `scripts/run-<name>.sh` wrapper only if the experiment needs launch conveniences.
