---
name: dgx-spark-training-layout
description: "Structure a fine-tuning experiment (LoRA, QLoRA, SFT) so each one lives in its own directory, heavy artifacts land in shared locations rather than beside the code, and every run is reproducible from a config snapshot. Triggers: new training run, fine-tune a model, LoRA, QLoRA, SFT, training experiment layout, where do checkpoints go, adapter output directory, run id, sweep, reproducible training config."
compatibility: "Linux host with bash. Written for an NVIDIA DGX Spark (GB10, aarch64) but applies to any single-node CUDA machine running TRL, PEFT, unsloth or axolotl. Docker optional. Builds on the dgx-spark-layout skill, which should be read first."
license: MIT
---

# DGX Spark training experiment layout

## Overview

**Parent skill: [`dgx-spark-layout`](../dgx-spark-layout/SKILL.md) — read it first.** All of its
storage rules apply unchanged: caches at each tool's own standard default location,
every path an env-overridable variable, no dir-local `./.cache`, and the same Docker
mount / native export rules.

This skill adds only what training introduces on top of serving:

- **Runs.** One experiment is many training runs at different hyperparameters, so
  output paths need a run dimension that serving does not.
- **Artifacts with opposite economics.** Checkpoints carry optimizer state, run
  2–3× adapter size *per save*, and are disposable once a run succeeds. Adapters are
  tens of megabytes and are the entire product. They must not share a retention policy.

As in the parent skill, the workspace root is yours to name:

```bash
DGX_SPARK_ROOT="${DGX_SPARK_ROOT:-${HOME}/dgx-spark}"
```

Everything below is written against it, so nothing here is tied to one machine's
directory convention.

## Instructions

### The experiment directory holds code and config only

Every training experiment gets its own directory under
`${DGX_SPARK_ROOT}/experiments/trainings/<Name>/`. Nothing lives loose in
`trainings/` itself — if a file belongs to an experiment, it belongs inside that
experiment's directory.

Name as `<Model>-<Method>-<Task>`, e.g. `Qwen3-4B-QLoRA-alpaca`:

```
${DGX_SPARK_ROOT}/experiments/trainings/<Model>-<Method>-<Task>/
├── README.md        goal, base model, dataset, key results, gotchas
├── train.sh         thin launcher: stamps a run-id, resolves output dir, calls entry
├── train.py         or a config-driven entry for unsloth / TRL+PEFT / axolotl
├── configs/
│   ├── base.yaml    shared defaults (model id, dataset, seq len)
│   └── run-*.yaml   per-run overrides (rank, alpha, lr, quantization)
├── data/            dataset *preparation scripts* only — never data files
└── eval/            post-training eval prompts and scripts
```

The directory stays a few kilobytes: no weights, no datasets, no checkpoints, no
logs. The framework choice is per-experiment; the skeleton is identical either way.

### Heavy data goes where the parent skill says

| Data | Where | How |
|---|---|---|
| Base model weights | `~/.cache/huggingface/` | Reference by HF id; `from_pretrained` caches once for every experiment |
| HF datasets | `~/.cache/huggingface/` | Automatic via `datasets` |
| Self-built datasets | `${DGX_SPARK_ROOT}/datasets/<name>/` | The `data/` prep script writes there via an env-overridable path |
| Run outputs | `${DGX_SPARK_ROOT}/outputs/trainings/<experiment>/<run-id>/` | See below |

### Per-run output layout

```
${DGX_SPARK_ROOT}/outputs/trainings/<experiment>/<run-id>/
├── config.yaml      exact resolved config snapshot — the reproducibility record
├── checkpoints/     trainer checkpoints with optimizer state — big, prunable
├── adapter/         final LoRA/QLoRA adapter — small, keep indefinitely
├── merged/          optional merged-weights / GGUF export for serving
├── logs/            tensorboard / trainer logs
└── metrics.json     final train/eval numbers
```

`run-id` is `YYYYMMDD-HHMM-<tag>`, where the tag encodes what was varied — e.g.
`20260720-0930-r16-lr2e4`. An `ls` of the experiment's output directory then reads
as its own sweep history, without a separate log of what was tried.

### Rules

1. **One experiment, one directory** under `trainings/`.

2. **The output root is env-overridable and defaults to the shared location.** Never
   a dir-local `./outputs` — checkpoints accumulate faster than anyone expects. In
   `train.sh`:

```bash
DGX_SPARK_ROOT="${DGX_SPARK_ROOT:-${HOME}/dgx-spark}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${DGX_SPARK_ROOT}/outputs/trainings}"
EXPERIMENT="$(basename "$(cd "$(dirname "$0")" && pwd)")"
RUN_ID="$(date +%Y%m%d-%H%M)-${RUN_TAG:?set RUN_TAG, e.g. r16-lr2e4}"
RUN_DIR="${OUTPUT_ROOT}/${EXPERIMENT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"
```

3. **Snapshot the fully-resolved config to `${RUN_DIR}/config.yaml` before training
   starts.** Not the input config — the resolved one, after defaults and overrides
   have merged. A run whose exact hyperparameters cannot be recovered is a run that
   gets redone.

4. **Adapters are not checkpoints.** On a successful run, copy the final adapter out
   of `checkpoints/` into `adapter/`; `checkpoints/` is then safe to prune. Keep
   adapters indefinitely — they are the product.

5. **Base models and datasets are never downloaded per experiment.** Use HF ids so
   the shared cache dedupes. Non-HF artifacts go to `${DGX_SPARK_ROOT}/base-models/`
   and `${DGX_SPARK_ROOT}/datasets/` per the parent skill.

6. **Docker versus native follows the parent skill unchanged.** Training stacks (TRL,
   PEFT, unsloth, bitsandbytes) read `HF_HOME`; triton kernels cache under
   `~/.triton`. For Docker, bind-mount to the in-container defaults *and* add
   `-v "${OUTPUT_ROOT}:${OUTPUT_ROOT}"` — the same path inside and out, so a
   `RUN_DIR` printed in a log is a path that exists on the host. Native: export
   nothing and the defaults apply.

7. **A launcher wrapper stays optional**, same as the parent skill. Add one only for
   launch conveniences — token forwarding, Docker plumbing, run selection — never to
   set storage paths.

### When writing a new training experiment

1. Create `${DGX_SPARK_ROOT}/experiments/trainings/<Model>-<Method>-<Task>/` with the
   skeleton above.
2. Put the HF model id and dataset id in `configs/base.yaml`. Per-run variation goes
   in `configs/run-*.yaml`, never as an edit to `base.yaml`.
3. Write `train.sh` per rule 2, and the entry script per rules 3–4: snapshot the
   config, export the adapter.
4. Send any storage question — caches, mounts, tokens — to the parent
   [`dgx-spark-layout`](../dgx-spark-layout/SKILL.md) skill rather than answering it here.
