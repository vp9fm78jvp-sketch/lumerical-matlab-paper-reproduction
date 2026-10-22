# Biasi DRUM: independent two-mode model and scan history

Primary journal article: Stefano Biasi et al., *Phase-controlled non-Markovian hysteresis in a nonlinear, non-Hermitian silicon microresonator*, Phys. Rev. Applied 25, 024041 (12 February 2026), DOI [10.1103/fcsp-jw79](https://doi.org/10.1103/fcsp-jw79). Its publisher abstract/full-text metadata and equations were checked. This corrects an earlier conversation's unverified publication date.

The executable coefficient table here comes from [Research Square v1 supplementary information](https://assets-eu.researchsquare.com/files/rs-7355635/v1/45bdd9826e745f37ec546b53.pdf), dated 12 August 2025, associated with [10.21203/rs.3.rs-7355635/v1](https://doi.org/10.21203/rs.3.rs-7355635/v1). Keep this preprint supplement distinct from the final article. Published-version numerical tables are not reconciled, so do not claim a journal-figure reproduction.

## Different physics from Xiang

The two counterpropagating fields have explicit complex asymmetric coupling: derivative of mode1 includes -beta21*mode2, derivative of mode2 includes -beta12*mode1 and i*sqrt(gammaCoupling)*Ein. beta12/21 have separate amplitudes and phases. Carrier generation depends on the **square of the total energy**, not Xiang's direction-resolved cross-term polynomial. The intrinsic/coupling loss budget includes **five** coupling points. Heating includes absorbed linear, TPA and FCA losses, excluding radiation/coupling. These distinctions are built into Biasi's own IR.

The source uses gammaLoss/2 for field amplitude decay. Read beta in the generator's rate convention; do not insert another 2π just because a table labels a rate THz. gammaCoupling=0.026THz and beta magnitudes 55/65GHz are transcribed as rates s^-1; omegaR explicitly includes 2π. Mode2 transmission amplitude is 1+i*sqrt(gammaCoupling)*a2/Ein in this convention. Test the no-coupling and low-power analytic limits independently.

An explicit source inconsistency remains: the supplement's printed numerical thermal displacement factor differs by roughly four orders of magnitude from its defining -omegaR/ng*dn/dT formula. `literal.model.json` retains the printed number, while `candidate.model.json` uses the defining expression. Neither is silently presented as the unique correct published model. The candidate's default detuning/power are a declared demonstration condition, not a complete reconstruction of every figure's wavelength marker.

## Forward and reverse are different calculations

`forward.json` defines 0→2π in five demonstration points. `reverse.json` defines 2π→0. Production resolution and dwell time must follow the target figure. Every point integrates the full field/carrier/thermal system, records its final state, and carries that state to the next point. A closed-loop reverse run starts from the final forward state when the experimental protocol says so; an independently prepared reverse sweep may require a different initial state. Do not assume these protocols are equivalent.

`reset_each=true` deliberately restores initial state at each point; this models the source's laser-off/on control only when the dwell/reset procedure justifies it. Do not obtain reverse data by reversing forward arrays. For phase changes along constant phase sum, keep phase12+phase21 fixed while integrating the actual sequence. A constant product can preserve a linear equilibrium without implying identical transient or nonlinear memory behavior under every protocol.

This example uses full RK4 at an optical-scale timestep in LSF because rapidly coupled modes make naive independent frozen-drive exponentials questionable. `short-reference.model.json`, if present, explicitly changes the Python **output sampling/horizon** for a short Radau diagnostic; its time step is not safe for the LSF RK4 solver. Always regenerate the production LSF from candidate.model.json. The short trace is not enough to infer steady memory or a publication match.

Use `python scripts/run_case.py biasi --out PROJECT --backend lumerical` for actual production scans. Tests validate state carry and separate forward/reverse solves using a clearly synthetic analytic memory system; those tests do not establish experimental Biasi hysteresis. The real short Biasi Python diagnostic validates numerical/model interoperability only. No Lumerical/MATLAB execution or journal-figure agreement is claimed.

## Actual path-execution development evidence

`phase-forward-run` and `phase-reverse-run` contain real three-point PYTHON_REFERENCE scans at 0, pi and 2pi, with a 2us dwell per point and adaptive Radau integration. Reverse initialization is the actual forward terminal state. Each point retains its model, final state, input-state hash and unique run receipt. `phase-scan-diagnostic.json` records the protocol. This tests stateful numerical execution on Biasi's distinct nonlinear model; three points and unresolved source-table/version issues do not establish the journal's hysteresis maps.
