# Reference data, metrics and physical acceptance

Public source data outrank digitized pixels. If digitization is needed, preserve source image hash, exact panel/plot box, axis limits/units, linear/log scaling, trace RGB and exclusion rectangles. The executable color-mask digitizer exports actually observed columns, pixel-spread uncertainty and a QA overlay. It reports gaps and makes no inferred points across them. It does not automatically infer axes, distinguish overlapping equal-colored curves or reconstruct error bars. The agent must calibrate/inspect these cases and obtain better data or block quantitative claims.

`digitize image.png calibration.json --out reference.csv` needs:

```json
{"plot_box":[60,20,600,350],"x_limits":[0,2],"y_limits":[0,5],
 "x_scale":"linear","y_scale":"linear","rgb":[0,0,255],
 "color_tolerance":45,"exclude_boxes":[[420,25,595,60]],"max_gap_pixels":3}
```

plot_box is inclusive PNG pixel coordinates; x_limits are left/right and y_limits bottom/top data values. Convert units to the simulation's SI units before comparison, preserving the original calibration. Nonempty `missing_pixel_intervals` must be reviewed. Digitized references are approximate, not original measurements. Do not demand errors below their resolution.

Curve comparisons validate finite monotonic x, prohibit extrapolation, evaluate simulated data on the reference grid only and report RMSE, range-normalized RMSE, MAE, correlation, peak/valley absolute errors and periodic feature differences. A flat reference uses its RMS scale instead of zero range. No free phase shift/amplitude scaling is applied. If a scientifically valid time-origin alignment is necessary, declare and retain both unaligned/aligned errors and use a held-out bound; never optimize away period drift.

Choose metrics by physics:

| Figure | Required emphasis |
|---|---|
| Self-pulsing | sustained late-time amplitude, period/cycle variation, peak/valley, inter-variable phase, convergence |
| Spectrum | resonance centers, width, splitting, extinction, asymmetry and input normalization |
| Heatmap/field | physical coordinate registration, scalar units/color limits, RMSE/boundaries, threshold-region overlap |
| Eigenvalues | complex eigenvalue matching, real-part stability, branch/exceptional-point topology |
| Bifurcation | stable/unstable branches, critical thresholds, scan history and Jacobian consistency |

`compare_maps` requires matching physical grids, not merely equal image dimensions; `compare_eigenvalues` matches complex sets by minimum assignment. `spectrum_features` reports local-prominence half widths; overlapping/Fano spectra need the actual spectral model. The generic tools are building blocks, not a universal validity certificate.

A 99% request has no unique scientific meaning. Define it before computation (for example NRMSE≤0.01 AND period error≤0.01 AND peak/valley tolerances AND sustained dynamics AND convergence). Do not turn correlation or a single SSIM/pixel score into proof of physical reproduction. Report all physical errors and digitization uncertainties. Multimodal observables can have different resolutions and justified weights.

The bundled ODE grader requires actual LUMERICAL_SCRIPT evidence for grades A-C. A/B additionally require source/model audit, named comparison thresholds, independently bound convergence and physical-check artifacts. Estimated/identified parameters or unresolved source corrections preclude strict A and require held-out evidence for B. Python-only results and unexecuted targets remain D in the reproduction report, even if the reference integrator is numerically accurate. This conservative policy prevents confusing infrastructure tests with paper reproduction.
