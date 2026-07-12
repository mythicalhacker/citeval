# citeval — fast, deterministic eval loop.
# `make eval` is the health check we run after EVERY change: offline-scores the committed cal30
# durable results against graded_reference_v2, runs the versioned gate, prints PASS/FAIL + numbers +
# gaps, and exits nonzero on any breach. PURE OFFLINE — no pipeline, no NCBI, no ANTHROPIC_API_KEY.

PY ?= python3

.PHONY: eval eval-quiet baseline regen-results test

## eval: fast offline gate — the command to run after every change (<2s, exits nonzero on breach)
eval:
	cd src && $(PY) -m citeval.eval

## eval-quiet: just the gate table + PASS/FAIL (skip the full scorecard)
eval-quiet:
	cd src && $(PY) -m citeval.eval --quiet

## baseline: print the measured metrics as a baseline block (to reseed gate_thresholds.json)
baseline:
	cd src && $(PY) -m citeval.eval --print-baseline

## regen-results: rebuild the committed cal30 durable results file from the run artifacts
regen-results:
	cd src && $(PY) -m citeval.regen_results

## test: full unit-test suite (stdlib unittest)
test:
	$(PY) -m unittest discover -s tests
