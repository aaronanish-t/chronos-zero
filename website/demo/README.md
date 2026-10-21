# Demo website

A first demo of the CHRONOS-ZERO product site: one standalone page that explains the product and
lets a visitor replay an agent getting caught, corrected and committed in each cartridge.

Open `index.html` in a browser. It needs no server and no internet beyond the two web fonts it
loads from Google Fonts; without them it falls back to system fonts.

## What's on the page

- **Hero:** the same `UPDATE accounts…` statement as a text filter sees it (allowed) and as
  Chronos-Zero sees it (UNSAT on `INV_FIN_01_ESCROW_CAP`).
- **How it works:** intercept, fork (SAVEPOINT), simulate, prove (Z3), commit or self-heal.
- **Live replay:** Healthcare, Fintech and Cloud DevOps, each with the hazardous tool call, the
  UNSAT verdict and its counterexamples, the rollback, the agent's corrected call, and the SAT
  commit. A "Without Chronos" switch shows the damage the same agent does unprotected.
- **Verify it:** every verdict has a "Verify receipt" button that recomputes
  `sha256(smt2_dump)` in the visitor's browser and compares it with the verifier's receipt.
- **Numbers:** only measured figures (proof time is the median of the recorded verdicts).

## Where the data comes from

The replay uses real verdicts, not hand-written ones. `record_verdicts.py` runs the actual
verifier (`services/z3-verifier/prover_core.py`) on the state shapes the kernel sends, and
writes `verdicts.json`. The kernel, database and agent steps are animated around those verdicts;
the page says so.

To reproduce a verdict in stock Z3, save its SMT-LIB2 and assume every rule:

```
(check-sat-assuming (INV_FIN_01_ESCROW_CAP INV_FIN_02_SLA_ATTESTATION))
```

`unsat` for a blocked action, `sat` for a committed one. A plain `(check-sat)` returns `sat`,
because each rule is a tracked assertion that is only enforced when its name is assumed.

## Update it

```bash
python website/demo/record_verdicts.py   # re-record verdicts.json from the verifier
python website/demo/build.py             # bake verdicts.json into index.html
```

Edit `template.html`, never `index.html` directly; `build.py` regenerates it.

## Next

This is the demo version. We will make it better with a few more Claude plugins, then turn it
into the full product website.
