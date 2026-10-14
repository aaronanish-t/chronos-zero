PY ?= python

.PHONY: test test-z3 test-cow

test:
	$(PY) -m pytest tests -q

test-z3:
	$(PY) -m pytest tests/test_z3_invariants.py -q

test-cow:
	$(PY) -m pytest tests/test_cow_engine.py -q
