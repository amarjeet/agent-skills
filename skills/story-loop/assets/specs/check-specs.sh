#!/usr/bin/env bash
# The local spec gate for Quint models: typecheck, witness runs, random simulation of the
# invariants, the documented violations of rejected designs, and the tracker check.
# Bounded model checking (quint verify / Apalache) is slow and belongs in a nightly job.
#
#   scripts/check-specs.sh          # typecheck + test + run
#   scripts/check-specs.sh --itf    # also write ITF traces for a conformance harness
set -euo pipefail
cd "$(dirname "$0")/.."

ITF=0
[[ "${1:-}" == "--itf" ]] && ITF=1
SAMPLES=${QUINT_SAMPLES:-2000}
STEPS=${QUINT_STEPS:-25}
OUT=${ITF_DIR:-build/itf}

step() { printf '\n== %s\n' "$*"; }

# quint test exits 0 when --match selects nothing, so a renamed run would pass silently:
# assert on the number of runs that passed.
expect_passing() {
  local n=$1 out; shift
  if ! out=$(quint test "$@" 2>&1); then echo "$out" >&2; exit 1; fi
  if ! grep -qE "^ +$n passing" <<<"$out"; then
    echo "$out" >&2; echo "expected $n passing run(s): quint test $*" >&2; exit 1
  fi
  printf '%s\n' "$out"
}

# A rejected design must be found violating its property; passing is the failure.
expect_violation() {
  if quint run "$@" >/dev/null 2>&1; then
    echo "expected a violation but none was found: $*" >&2; exit 1
  fi
  echo "violation found as documented: $2 $4"
}

step typecheck
for f in specs/*.qnt; do quint typecheck "$f"; done

step "witness runs"
# One line per instance module; pin the count so a renamed run cannot pass silently.
# expect_passing 8 --main Example --match 'Test$' specs/example.qnt

step "invariants (must hold)"
# quint run --main Example --invariant safety --max-steps "$STEPS" --max-samples "$SAMPLES" specs/example.qnt

step "documented violations (must be found)"
# expect_violation --main ExampleRejected --invariant safety --max-steps "$STEPS" --max-samples "$SAMPLES" specs/example.qnt

if [[ -f stories/tracker.yaml ]]; then
  step "tracker references"
  python3 stories/coverage.py
fi

if [[ $ITF -eq 1 ]]; then
  step "ITF traces -> $OUT"
  mkdir -p "$OUT"
  # quint run --main Example --invariant safety --max-steps "$STEPS" --n-traces 20 --verbosity 1 --out-itf "$OUT/example-{seq}.itf.json" specs/example.qnt
fi

printf '\nall spec checks passed\n'
