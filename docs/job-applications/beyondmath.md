# BeyondMath

## Raw Role Summary

Role: Simulation Engineer.

Location: London, hybrid, full time.

BeyondMath is building foundational AI models for physics. The Simulation
Engineer role is framed as the "guardian of the ground truth": architect and
execute CFD-to-ML pipelines that produce robust, repeatable, high-fidelity data
for model training and validation.

Key supplied responsibilities:

- Architect CFD-to-ML workflows from CAD cleanup and triangulation through
  volume meshing, solver execution, and downstream data extraction.
- Generate and validate high-fidelity transient CFD datasets: RANS, URANS, and
  HRLES are explicitly mentioned.
- Collaborate with AI researchers to translate fluid-dynamics principles into
  model constraints and validation criteria.
- Build automated, scalable meshing and solver infrastructure.
- Work with technical partners in F1 and aerospace to align simulation
  parameters with industrial design problems.
- Establish standards for mesh quality, solver settings, reproducibility, and
  simulation fidelity.

Essential requirements from supplied role:

- MSc/PhD in aerospace, aeronautical, mechanical engineering, or mathematics.
- Deep CFD mastery with tools such as OpenFOAM, Fluent, STAR-CCM+, ANSA, or
  ParaView.
- Strong fluid-dynamics theory: incompressible/compressible flow, turbulence
  modelling, heat transfer.
- Proven raw-CAD-to-validated-simulation workflow.
- Communication across classical engineering and modern ML teams.

Desirable:

- Scientific ML / surrogate modelling curiosity.
- Python or C++ automation.
- HPC or cloud simulation experience.

Public site notes:

- BeyondMath presents its product as a "generative physics" platform for fast
  engineering-grade simulation.
- Public messaging highlights physics AI for automotive, aerospace, energy,
  defence, semiconductors, construction, telecoms, and electronics.
- The site says the workflow aims to let users upload geometry, simulate with a
  physics foundation model, and analyse fields such as pressure, velocity, and
  temperature.
- Public claims include up to 1000x faster validation and a February 2026 seed
  round announcement.

Sources:

- https://beyondmath.com/
- https://builtin.com/job/simulation-engineer/9223603
- Supplied role text in this thread.

## What They Are Screening For

- Can you produce trustworthy CFD data, not just pretty pictures?
- Can you automate simulation workflows without losing physical rigor?
- Can you define mesh/solver/data quality standards?
- Can you bridge CFD and ML: what should be learned, what must be conserved,
  and how should model outputs be validated?
- Can you talk to F1/aerospace-style technical stakeholders in their language?

## Whittle Mapping

Strong signals already present:

- OpenFOAM case writing from typed Python schemas.
- STL metadata inspection, geometry presets, rigid transforms, and MRF zone
  generation.
- OpenFOAM smoke runs were manually executed and inspected in ParaView.
- `checkMesh` and `simpleFoam` logs have already shaped the roadmap.
- The project distinguishes smoke/demo validity from validated CFD fidelity.

Stronger if added after agent-interview prep:

- Parse `checkMesh` and `simpleFoam` logs into typed reports.
- Track mesh quality metrics as first-class acceptance criteria.
- Add post-processing outputs: force history, pressure extrema, residuals,
  continuity, mesh skewness, non-orthogonality.
- Improve rotor modelling: actuator disk or better MRF/source-term treatment.
- Add a case dataset manifest: geometry, settings, mesh metrics, solver status,
  post-processing fields.

## Interview Narrative

Best positioning:

> Whittle is not a claim that I solved drone CFD in a weekend. It is a
> production-shaped CFD automation spine: typed case specs, deterministic
> OpenFOAM generation, mesh/solver smoke testing, visible assumptions, and a
> roadmap toward reproducible CFD datasets. The important part for BeyondMath is
> that I treat simulation as data infrastructure: provenance, quality gates,
> repeatability, and downstream ML-readiness.

Emphasise:

- You noticed weak downwash and do not overclaim the MRF result.
- You know the next fidelity steps: actuator disk/source terms, better CAD,
  log parsing, mesh metrics, convergence criteria, dataset metadata.
- You can communicate where AI helps and where CFD ground truth must remain
  deterministic and validated.

## Gaps To Close Before BeyondMath

- Add typed log parsing and a small `SimulationRunReport`.
- Add a stronger explanation of why current MRF is only a smoke approximation.
- Prepare notes on RANS/URANS/LES/HRLES tradeoffs and why transient datasets
  matter for physics foundation models.
- Prepare one Whittle demo path: generate case -> inspect dictionaries ->
  mesh/solve smoke -> parse logs -> explain next fidelity step.
