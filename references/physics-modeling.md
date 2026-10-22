# Physical model contract

The reusable engine accepts paper-specific real-state ODE IR. It is not a universal optical model. Copy `examples/minimal/model.json` to learn the exact JSON schema; construct the paper's physics from sources. Spatial Maxwell/transport tasks require an agent-authored solver script and dataset contract (`product.py`), rather than pretending this ODE engine solves arbitrary PDEs.

## Equation/source ledger

For each equation keep original source/page/number, a visually checked transcription, term meaning, variable units, approximation, implementation expression and associated targets. Raw equation candidates in paper.json are search anchors, not guaranteed complete mathematics. Record missing constitutive laws, dispersion models and supplementary definitions. Explain every included/omitted term. Keep anomaly variants separate and immutable.

For energy-normalized TCMT, |a|²=U (J), |s|²=P (W), coupling sqrt(kappa) is s^-1/2; a and s cannot be directly subtracted. An input-output relation contains sqrt(kappa)*a. With energy loss kappa, field decay is kappa/2 and Q=omega/kappa. Do not add a reported loaded Q's loss on top of its constituent losses. State the e^(+iwt) or e^(-iwt) and rotating-frame convention. Use angular frequency consistently; rad is dimensionless but 2π is not optional.

For dn/dT>0, a positive temperature shift normally lowers resonance angular frequency under omega proportional to 1/n. FCD and Kerr signs depend on the constitutive law and convention; derive them rather than matching the desired waveform. Separate absorbed losses that heat the cavity from radiated and coupling losses. Check integral energy balance, material passivity, state domains and boundary/initial conditions.

## Executable JSON fields

- `id`, `device_id`, `condition_id`, `variant_id`; `provenance.sources` with versioned citations.
- `parameters`: ordered records `name`, `value`, `unit`, `expected_unit`, `category` A/B/C/D, `source`, `optimize`, `history`. For derived values use `expression` referring only to earlier parameters. Keep documented `uncertainty`, `bounds`, `rationale` and `conditions` as needed.
- `states`: `name`, SI-base-scale `unit`, `initial` and positive `scale`. Store complex amplitudes as separate real/imaginary states. `scale` nondimensionalizes the Python reference integrator for reliable tolerances.
- `algebra`: ordered named expressions and units; `rhs`: derivative expression per real state.
- `observables`: named expression/unit. Exported MAT variables are `out_NAME` plus time vector `t` in seconds. Include all observables needed for physical tests, not merely attractive output power.
- `time`: `start`, `stop`, `dt`, `max_steps`, optional Python-reference `max_step`. dt determines the LSF integration step and the Python output grid; adaptive Python internal steps are controlled separately.
- `integration`: `rk4` or `exponential_midpoint`; `split_fields`: real/imag state names, local linear `coefficient` and `drive` expressions. The exponential splitting assumes each listed field can be advanced locally; strongly coupled fast fields may require a matrix exponential or full-system stiff solver instead.
- `review`: booleans `equations`, `normalization`, `loss_budget`, `detuning_sign`, `initial_boundary`, `parameter_sources`, plus substantive `evidence`. This is an agent scientific review assertion; dimension checks cannot prove physics.
- `condition_parameters`: permitted pump/detuning/phase differences across the same device. Material changes require a separately evidenced device/variant.

Expressions support numeric/complex constants, symbols, + - * / ** and one-argument sqrt, abs, abs2, exp, sin, cos, log, real, imag, conj. No eval/import/attribute/indexing/arbitrary Python code is allowed. Use algebraic real/imaginary equations for more complex systems, or author an explicitly reviewed solver program. The IR does not support arbitrary discontinuous waveforms: split integration into segments preserving state, or author an LSF waveform/solver appropriate to the paper. Do not approximate an unknown pulse by inventing a smooth function.

The Pint audit evaluates expressions with quantities to catch dimensional mismatches, including derived parameters, all state derivatives and observable units. It does not symbolically establish conservation or formula correctness. `audit` returns separate `units_passed`, `scientific_review_passed`, `can_execute`. Built-ins c/pi/cross and internal pr_ names are disallowed as model symbols. Name physical constants `lightSpeed`, `hbarSI`, etc.

Parameter C/D status must survive export/reporting. A reference-paper estimate is not an original parameter. A fitted lifetime remains an effective lifetime. Never silently overwrite the original model or use a separate fitted material table per figure.
