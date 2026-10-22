# Per-panel classification and priorities

Use separate classifications for scientific content and execution status. A-E here describe figure content, whereas reproduction grades A-D describe achieved evidence. Do not confuse them.

| Content | Treatment |
|---|---|
| A numerical scientific data | Simulate physically, including time traces, spectra, eigenmodes, fields, maps and bifurcations |
| B measured data | Predict with justified theory and compare; preserve “experiment” versus “simulation” identity |
| C schematic | Extract topology, ports, geometry and feedback; no synthetic numeric target required |
| D photo/SEM/TEM | Retain as structural evidence and geometry source; do not generate counterfeit microscopy |
| E insufficient evidence | Keep in manifest with missing-model/data/parameter reasons and recovery actions |

The deterministic classifier is keyword-assisted and provisional. It uses each panel's own caption fragment, not the whole mixed figure caption. Conflicting schematic/photo/numerical cues become E awaiting agent review. “Schematics of self-pulsation” can mean a numerical plot; visually inspect it instead of trusting the word “schematic”. A caption's experiment/simulation comparison may contain separate modalities. Explicit reviewed panel classes override heuristics.

Record axes, units, log/linear scale, legends, marked conditions, error bars and source digitization uncertainty per panel. For nested (c1)-(c3), keep their actual labels. For unlabeled stacked plots, assign stable local panel names and record that names are agent-assigned; preserve the paper's parent label.

Priority starts with importance, model completeness, parameter availability, quantifiability and shared-model value, minus cost. Defaults are not scientific judgments. The agent should revise scores based on the central claim, shared calibration, computational prerequisites and held-out needs. A high-cost core result remains registered even if it must be blocked. Reserve excluded figures/conditions before fitting, rather than selecting a favorable “held-out” plot afterward.

Link every target to equations/parameters/device/model/conditions/dependencies, original reference, acceptance thresholds and actual run IDs. Build a DAG around physical dependencies (eigenmode → mode volume → dynamics → system cascade); do not impose artificial dependencies between independent experiments. Mark photos/schematics BLOCKED for numeric reproduction with reason “context-only”; this is deliberate inclusion, not a failed physics solve.
