# Xiang Fig.2: source audit, failed dynamics and candidate identification

Primary paper: Jinlong Xiang, Axel Torchy, Xuhan Guo, Yikai Su, *All-Optical Spiking Neuron Based on Passive Microresonator*, JLT 38(15), 2020, DOI [10.1109/JLT.2020.2986233](https://doi.org/10.1109/JLT.2020.2986233). [Author-hosted PDF](https://otip.sjtu.edu.cn/publication/Journal/2020-JLT-JinlongXiang-All-Optical%20Spiking%20Neuron%20Based%20on.pdf).

## Separate the evidence layers

The task supplied a retrospective account: an earlier candidate showed decaying oscillations, then effective scales fcdScale/sigmaScale/heatScale/qScale and an exponential midpoint method were investigated. Exact old trial values, source scripts, solver logs and independently verified successful candidate data were not supplied. `history.json` records this absence. Do not invent an earlier successful run, 99% score or factor values.

The present repository independently transcribes and audits the accessible original paper. It includes executable **hypotheses** and actual PYTHON_REFERENCE runs, identified by receipts. These are new calculations, not recovered historical Lumerical runs. The scientific reproduction grade remains D until the required commercial/platform and validation evidence exists.

## Source-to-code map

| Source | Implementation |
|---|---|
| Eq.1 | Forward/backward complex fields as four real states; energy normalization |
| Eq.2 | Carrier generation proportional to U+²+4U+U-+U-²; carrier relaxation |
| Eq.3 | Thermal relaxation plus absorbed-power heating |
| Eqs.4-6 | Linear, radiation, coupling, TPA and FCA energy-loss rates |
| Eqs.7-10 | Kerr, plasma/FCD and thermal frequency shifts, with sign anomaly recorded |
| Eqs.11-14 | Absorbed linear/FCA/TPA power; radiation/coupling excluded from heat |
| Table I, Fig.2(a) | Microring parameter ledger, CW pump 5mW, delta-lambda -20pm |

The Drude closure for Eq.9 is an additional derived physical hypothesis, not a fully specified FCD law given by the paper. Mark it C; use the reference constitutive law before claiming strict reproduction. The one tabulated sigma is explicitly interpreted as a summed FCA cross-section; its species definition is unresolved.

The paper's Table I reports Q alongside Qin/Qv/linear absorption. Never add Qreported loss again to the constituent loss budget. The implemented Qreported is audit-only. The computed constituent loaded Q should be reported separately. Output power uses |sqrt(Pin)-sqrt(kappa)*a+|²; it is not a subtraction of a (sqrt J) and s (sqrt W).

## Source anomalies and immutable variants

- `literal.model.json` retains the printed Eq.10 thermal sign and suspicious raster-table exponents for epsilon0 and dn/dT. It is not recommended as a realistic physical model; execute only with a strict budget, retaining failure evidence.
- `candidate.model.json` explicitly substitutes SI vacuum permittivity, conventional silicon dn/dT and the physical thermal redshift sign. Its parameter histories and anomalies preserve the changes. These are C hypotheses, never paper-original A parameters.
- `eq10-literal-sign-with-si.model.json` isolates the thermal-sign issue with the same SI corrections. It is a diagnostic variant, not a strict baseline.
- `identification.model.json` declares uncertain effective FCA cross-section and carrier lifetime as D with explicit bounds/rationale. It does not contain guessed historical scale factors.

For SI permittivity magnitude see [NIST CODATA](https://physics.nist.gov/cuu/Constants/). The candidate's rounded constant is sufficient for this sensitivity study; numerical precision is not justification for changing a material model. Always re-inspect the source raster at high zoom before treating an exponent as a paper error.

## Actual development calculation

`reference-run/data.mat` (Radau) and `sign-diagnostic/data.mat` are real Python solutions over 3 microseconds. `diagnostics.json` measures late-time amplitude and period; the physical-sign candidate decays toward a fixed point rather than sustaining the paper's pulse train. This negative result is deliberately retained. The minimum/maximum output and amplitude-decay measurements are in the machine-readable diagnostics, not a fabricated success narrative.

`reference.csv` is an approximate digitization of Fig.2(a)'s red output trace. It preserves calibrated SI axes and per-column pixel uncertainty. `reference.calibration.json` gives the input asset hash/box, source, pixel uncertainty and exclusions. The copyrighted source image/QA overlay are not redistributed in the public code. The digital reference does not remove startup-state ambiguity: the paper says microring demonstrations begin after settling, so the initial state/phase must be investigated rather than fitted away invisibly.

`identification-run/identification.json`, when present, records real bounded evaluations against this approximate curve. A selected trial is only a candidate, including if the optimizer merely improves a fixed-point mismatch. Recheck sustained dynamics, all four plotted observables, warm-up, dt, independent integration and an excluded condition. No fitted candidate in this repository is claimed to meet the paper's self-pulsing waveform or a 99% criterion.

## Reproduction procedure

Run `python scripts/run_case.py xiang --out PROJECT --backend lumerical` on a licensed installation, or explicitly choose python-reference for numerical checks. The case command preserves immutable models and compiles both LSF candidates. To identify parameters use the separate bounded experiment command in README. Analyze late-time behavior before matching peaks. Keep original and corrected models separate, use one shared microring material table across figures, and reserve a different figure/pump condition for validation. Nanobeam Fig.2(b) has its own device parameters; do not reuse the ring table.
