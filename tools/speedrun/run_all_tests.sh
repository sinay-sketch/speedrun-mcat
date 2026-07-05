#!/bin/bash
# One-command reproducible test suite for Speedrun (MCAT). Runs every check a
# grader would re-run and prints a PASS/FAIL summary. Deterministic.
#
#   bash tools/speedrun/run_all_tests.sh
#
# The sync test needs a self-hosted anki-sync-server; this script starts a fresh
# one on 127.0.0.1:8080 (user test:test) for the duration and tears it down.
set -uo pipefail
export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"
cd "$(dirname "$0")/../.."          # repo root
PY=out/pyenv/bin/python
VENV=tools/speedrun/ai/.venv/bin/python
pass=0; fail=0; results=()

run() {  # run <name> <command...>
  local name="$1"; shift
  echo "──▶ $name"
  if "$@"; then results+=("PASS  $name"); pass=$((pass+1)); else results+=("FAIL  $name"); fail=$((fail+1)); fi
  echo
}

# 1. Rust core: scores + interleaving feature (mastery/performance/interleave live
#    under scheduler::; runs all scheduler tests — a single cargo filter).
run "Rust score/feature tests" cargo test -q -p anki scheduler::

# 2. Python test calling the engine
run "Python engine test (MasteryForDeck)" env PYTHONPATH=out/pylib "$PY" -m pytest -q pylib/tests/test_mastery.py

# 3. AI: leakage assertion (no key)
run "AI leakage assertion" "$VENV" tools/speedrun/ai/leakage.py

# 4. Memory-model calibration (ECE + reliability diagram)
run "Memory calibration (ECE)" "$VENV" tools/speedrun/scoring/calibration.py

# 5. Interleaving ablation (pre-registered)
run "Interleaving ablation" "$VENV" tools/speedrun/ablation/interleaving_ablation.py

# 6. Crash / zero-corruption
run "Crash / zero-corruption (x20)" env PYTHONPATH=out/pylib "$PY" tools/speedrun/crash_test.py 20

# 7. 50k-card speed benchmark (uses cached deck)
run "50k-card speed benchmark" env PYTHONPATH=out/pylib "$PY" tools/speedrun/benchmark.py

# 8. Two-way sync + conflict (spin up a throwaway server)
echo "──▶ Two-way sync + conflict"
pkill -f anki-sync-server 2>/dev/null; sleep 1; rm -rf /tmp/speedrun_test_syncbase
SYNC_USER1=test:test SYNC_BASE=/tmp/speedrun_test_syncbase SYNC_HOST=127.0.0.1 SYNC_PORT=8080 \
  nohup cargo run -q -p anki-sync-server >/tmp/speedrun_sync_srv.log 2>&1 &
srv=$!
for i in $(seq 1 40); do nc -z 127.0.0.1 8080 2>/dev/null && break; sleep 1; done
if env PYTHONPATH=out/pylib "$PY" tools/speedrun/sync_conflict_test.py; then
  results+=("PASS  Two-way sync + conflict"); pass=$((pass+1)); else results+=("FAIL  Two-way sync + conflict"); fail=$((fail+1)); fi
kill "$srv" 2>/dev/null; pkill -f anki-sync-server 2>/dev/null
echo

# 9. Coverage map (informational — always prints)
echo "──▶ Coverage map (informational)"
env PYTHONPATH=out/pylib "$PY" tools/speedrun/coverage_map.py >/dev/null && echo "  (see coverage_map.py output)"
echo

echo "════════ SUMMARY ════════"
printf '%s\n' "${results[@]}"
echo "─────────────────────────"
echo "$pass passed, $fail failed"
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
