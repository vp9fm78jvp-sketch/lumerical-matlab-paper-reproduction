# Solver integration and checked interfaces

Official primary sources, checked while building this skill:

- [Python session management](https://optics.ansys.com/hc/en-us/articles/360041873053-Session-Management-Python-API): FDTD, MODE, DEVICE and INTERCONNECT constructors. HEAT/CHARGE are DEVICE physics configurations, not assumed Python constructor names.
- [feval](https://optics.ansys.com/hc/en-us/articles/360034405934-feval-Script-command): executes a named LSF script; API eval may issue this command.
- [matlabsave](https://optics.ansys.com/hc/en-us/articles/360034928113-matlabsave-Script-command): exports numerical workspace data to MAT.
- [MATLAB -batch](https://www.mathworks.com/help/matlab/ref/matlabwindows.html): noninteractive function invocation and process exit status.

Installation/interface detection is not proof of license validity. `doctor` discovers SDK candidates, MATLAB executable, platform, Python dependencies, OCR and output permissions. `doctor --probe-lumerical` actually opens one product and checks a simple script round-trip. This is only an API/license probe, not a physical simulation, and may block at a license server; run with an outer process deadline when automating.

Set LUMAPI_PATH to the vendor lumapi.py (or its directory) and MATLAB_EXECUTABLE to an actual executable. Use the vendor-supported Python/SDK combination for the installed version. Do not bundle commercial code/license files. Launch each attempt in its own session and output directory to prevent stale workspace variables/files from masquerading as fresh output.

The ODE adapter generates numerical LSF, uses `switchtolayout`, calls `feval` through the actual Python API, retrieves a completion sentinel/final state/time, validates every exported vector and binds data to a script/model/run hash. It does not rely on an empty circuit's “simulation completed” message. `run` starts circuit/project simulation; it is not a generic file executor.

LSF and MATLAB have distinct control flow, array construction, transposes and workspace rules. The linter flags built-in assignments, likely MATLAB `end/elseif`, unsafe run(file), and unmatched delimiters. Passing static lint is not a full LSF syntax/runtime check. Compiled scripts have not been commercially executed in this development environment; validate them on the installed product before trusting results.

## Spatial/product script contract

`paper-repro run-script simulation.lsf contract.json --product MODE --out field.mat` executes a reviewed, agent-authored script. Use `__OUTPUT_MAT__` without quotes as the replacement token for an absolute escaped path. Script must create actual geometry/material/source/boundary/mesh/solver/monitor operations, check solver convergence/results, export named MAT variables, then set `pr_completed=1`. A sentinel alone cannot prove correct physics; dataset and physical validation are also necessary.

Example contract:

```json
{"review":{"physics_reviewed":true,"evidence":"Paper p3 Fig2 geometry and boundary conditions; monitor extraction reviewed"},
 "variables":{"x":{"unit":"m","axis":true,"shape":[null]},
              "y":{"unit":"m","axis":true,"shape":[null]},
              "temperature":{"unit":"K","axes":["x","y"],"shape":[null,null],"real":true}}}
```

This validates units, finite values, coordinate monotonicity, exact array dimensions, and field-to-axis alignment. A receipt identifies LUMERICAL_PRODUCT and the actual constructor. No prewritten universal FDTD geometry or universal HEAT/CHARGE material law is provided. The agent must generate and verify the paper-specific project. N-dimensional product convergence/grading must use paper-specific physical checks; the bundled automatic A-D ODE grader does not certify PDE results.

Do not infer long-timescale thermal self-pulsation from an uncoupled optical FDTD simulation. Choose justified reduced equations or genuine multiphysics coupling. Do not assume a Scripted Element automatically provides arbitrary nonlinear ODE integration.
