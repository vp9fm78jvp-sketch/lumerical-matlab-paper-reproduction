# Numerical accuracy and dynamical diagnosis

Start with the published equations, material parameters, pump/trigger waveform, scan path and initial condition. Preserve their result regardless of whether it matches. Diagnose a failed result before any identification. A transient ring-down is not sustained self-pulsation. Near a bifurcation, settling can be much slower than any individual nominal relaxation time; use late-time windows and extend the integration horizon.

For fast cavity fields coupled to slower carriers/temperature:

1. Compute nonlinear loss and detuning from current state.
2. Advance the field exactly over a half-step for frozen coefficient L and drive b: a(h)=exp(Lh)a0+h*phi1(Lh)*b, phi1(z)=(exp(z)-1)/z. Use a series at small z to avoid cancellation.
3. Predict slow variables at the midpoint using their current derivatives.
4. Recompute all coefficients at the midpoint with the predicted field/slow state.
5. Advance the field over the full step with the midpoint coefficients; advance slow variables with the midpoint derivative.
6. Retain all state/output/diagnostic data. Reject nonfinite/diverging results, do not clamp them into a plausible waveform.

The generated exponential_midpoint LSF implements these steps for individually specified complex fields. It freezes cross-field terms only when explicitly represented as the drive; this may be inaccurate for strongly coupled fast fields. Use full-system RK4 at a stable optical-scale dt or an appropriate stiff/matrix-exponential implementation. Biasi's example deliberately uses tiny dt with full coupled RK4, rather than inheriting Xiang's splitting without justification.

The Python reference uses adaptive SciPy Radau by default, with state scaling and configurable relative/absolute tolerances. DOP853/BDF/RK45 are explicit choices available to reference checks. Output dt is not its internal step size. This reference is useful to audit the LSF method; its successful execution does not validate Lumerical syntax or licenses.

`convergence` requires three real run files with distinct run IDs, two at least 2x refined output/integration grids, the same physical/condition family, and an independent integrator. It binds exact model snapshots and data hashes, then checks every observable against declared NRMSE tolerances. For adaptive-reference-only comparisons, reducing output dt mainly tests sampling; also tighten rtol/atol/max_step to test integration error. For LSF dt actually refines the fixed integrator. Python comparisons do not establish commercial execution.

Late-time diagnostics in compare.py measure retained tail amplitude, period variation, number of cycles and decay. “sustained_oscillation_candidate” is deliberately weaker than a mathematical proof of an attracting limit cycle. Add longer trajectories, repeated initial conditions, phase-space recurrence, stability/Jacobian analysis or a return map as appropriate. Verify oscillation frequencies against FFT and event-based periods. Avoid detecting mesh/timestep oscillations as physics.

Useful separate diagnoses:

- Syntax/interface: reserved names, wrong product, feval, design/analysis mode, script scope and missing exports.
- Numerics: unstable timestep, stiffness, inconsistent tolerance scales, inadequate warm-up, invalid negative densities.
- Physics: duplicate losses, wrong Q definition, 2π, mode volume powers, thermal/FCD signs and incorrect energy normalization.
- Conditions: wrong detuning, pump power, pulse shape, scan direction, state reset or boundary conditions.
- Data/plotting: stale MAT, missing variable, array transpose, units, limits or wrong time origin.

Use a diagnostic change ledger: hypothesis, evidence, single intended change, baseline/candidate IDs, test outcome and unresolved concerns. Do not optimize all these causes simultaneously until the actual failure mode is understood.
