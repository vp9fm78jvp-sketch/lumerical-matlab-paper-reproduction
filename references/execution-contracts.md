# Execution, checkpoints, plotting and reports

## Task plan

Run commands from the skill root (or install its package first). A project has its own plan.json and state.sqlite; it must not be the installed skill directory.

```json
{"schema_version":1,"tasks":[
 {"id":"Fig2(a)","kind":"simulate","model":"models/ring.json","output":"data/fig2a.mat",
  "backend":"lumerical","timeout":300,"max_attempts":1,"priority":10,"dependencies":[]},
 {"id":"Fig2a-compare","kind":"compare","reference":"reference/a.csv","simulation":"data/fig2a.mat",
  "column":"out_output_power","output":"validation/metrics-a.json","dependencies":["Fig2(a)"]}
]}
```

Paths must stay inside the project. DAG references and cycles are validated. SQLite stores PENDING/RUNNING/COMPLETED/VERIFIED/FAILED/BLOCKED and an event ledger. This implementation automatically marks executions COMPLETED, never scientifically VERIFIED. Source file hashes, task definitions, dependency fingerprints and output hashes determine reuse; changed/missing artifacts invalidate cache and descendants. Existing completed artifacts are archived under .history before a changed model is re-run. Generated inputs must declare their producer as a dependency. Transactions claim tasks exclusively. Expired leases recover interrupted work; do not force-recover a live worker.

`--workers N` runs independent tasks concurrently with one commercial session per task. Default 1 avoids oversubscribing licenses. Dependent scans use `sweep`, not parallel tasks. Each scan point stores input-state hash and solver final state; resume re-verifies all preceding data/receipts before proceeding. A new scan definition requires a separate directory. Reverse sweeps integrate anew with their explicitly chosen initial state; reset_each deliberately removes inter-point memory.

`--budget` bounds new work and per-simulation process deadlines. A process group is terminated on timeout. This is a foreground scheduler, not a resident daemon; it cannot promise future background work. Retry permanent license/model blockers only after fixing the prerequisite (`--retry-blocked`). Default retry count is one; bounded retries without changes should be reserved for transient failures. On interruption, preserve `.runs`, logs, SQLite and completed points. Never clear them to “start fresh”.

## MATLAB config

`plot CONFIG --out CONFIG-COPY` validates data receipts before MATLAB. Example:

```json
{"output_dir":"/absolute/project/plots","figures":[
 {"id":"Fig2a","data":"/absolute/project/data/a.mat","panels":[
  {"columns":["out_input_power","out_output_power"],"labels":["Pin","Pout"],
   "x_factor":1000000,"y_factor":1000,"xlabel":"t (us)","ylabel":"P (mW)"}]}]}
```

Line panels optionally use x_column (default t), xscale/yscale, xlim/ylim. Display factors convert units explicitly. Heatmap panels use kind=heatmap, x_column/y_column/z_column, scalar array shaped [Nx,Ny], x_factor/y_factor and optional clim. Read `templates/plot_all.m` for layout. MATLAB outputs PNG/PDF/SVG/FIG and a plot receipt; Python verifies file existence/hash and PNG decodability. Visual legibility review remains the agent's responsibility. The current environment's plotting test mocks only the process/data contract; it does not validate MATLAB rendering.

## Evidence and grades

Store exact model snapshots next to run data (`data.model.json`), receipt (`data.provenance.json`) and log. `run-model`/scheduler create these. `convergence MODEL coarse.mat fine.mat independent.mat tolerances.json --out convergence.json` revalidates model family, unique run IDs, integration refinement and all observables.

A physical-check file contains model_sha256, passed and nonempty checks; every check needs passed, method, source, artifact and artifact_sha256. Do not set these based on visual resemblance. Derive energy balance, state-domain checks and mechanism tests from actual data. A held-out file needs passed, material parameter_sha256, different training_condition/validation_condition and hashed real artifacts. Use independent excluded source data and record full comparisons.

`grade SPEC --out RESULT` takes model/data/metrics/thresholds and optional convergence_path/physics_path/heldout_path. Metrics must be re-derived from the bound data and reference; preserve comparison source hashes. `report` reads validation/FigID.json specs and re-runs grading, rather than trusting an old grade string. Do not hand-edit grades or status VERIFIED to bypass evidence. N-dimensional PDE reproduction needs paper-specific convergence and grading; the generic ODE grader intentionally declines to certify it.

Report every figure's content class, execution state, grade, error and blocker. Bundle full sources/code/data/plots/metadata in the reproduction project, keeping commercial binaries/licenses excluded. Installed skill code and scientific project outputs are separate.

For high-grade curve comparisons, metrics contain a `_evidence` section identifying source/reference/data hashes. The grader recomputes metrics from those files rather than trusting a hand-written number. Convergence artifacts are independently recomputed. Held-out validation also needs bound comparison evidence, unchanged material parameters and real Lumerical receipts.
