# Interview Sprint Plan

_Last updated: 2026-05-11_

## Purpose

Use Whittle as the spine project for three near-term interviews:

- Anima: Tuesday 14:00, agentic product engineering / healthcare workflows.
- PhysicsX: Wednesday morning, applied AI agents for engineering simulation.
- BeyondMath: later simulation-engineering emphasis, CFD/data fidelity.

The next 36 hours should optimise for agentic engineering evidence. CFD fidelity
work resumes after the Anima and PhysicsX interviews unless a specific interview
question requires it.

## Priority Order

1. Add a credible tracing story.
   - Prefer Pydantic Logfire because it maps cleanly to PydanticAI, FastAPI,
     OpenTelemetry, tool calls, and agent traces.
   - Minimum useful version: optional local configuration, no secrets committed,
     instrument FastAPI and PydanticAI, document how to run it.

2. Add a `ScenarioIntent` layer.
   - Purpose: let the agent reason flexibly about messy user requests before
     crossing into the deterministic `SimulationCaseSpec`.
   - This is the answer to "where does agentic reasoning belong?"
   - `SimulationCaseSpec` remains the hard deterministic boundary.
   - Motion-rate requests now pass through a typed heuristic
     `MotionRotorCommand` before becoming a differential-MRF proxy case.

3. Improve multi-turn state.
   - Preserve the previous scenario/intent/spec in the UI conversation.
   - Let the user refine speed, rotor model, attitude, and assumptions without
     starting from a blank prompt each time.
   - The agent should coach first, write later.

4. Improve the visible agent trajectory.
   - Show a compact timeline of actions: classify, inspect envelope, draft
     intent, validate, ask question, draft spec, human review.
   - Do not expose hidden chain-of-thought.

5. Prepare interview answer bank.
   - PhysicsX application questions.
   - Anima agentic-product examples.
   - BeyondMath CFD/data-pipeline story.

## Recommended Build Sequence

### Monday Evening

- Implement `ScenarioIntent` models and deterministic extraction. Done.
- Update PydanticAI planner tools to produce and validate intent before spec.
  First pass done.
- Add evals for multi-turn-ish requests and ambiguous manoeuvres. First pass
  done.
- Add or stub Logfire instrumentation if low risk. Done as optional env-gated
  FastAPI/PydanticAI instrumentation.

### Tuesday Before Anima

- Finish optional Logfire instrumentation or document the exact tracing story.
- Write an Anima demo script:
  vague request -> clarifying/coaching -> typed state -> validation -> human
  review -> writeable output.
- Improve the answer-bank framing around why LLMs propose intent, while
  deterministic tools own calibrated physics settings.

### Tuesday After Anima / Wednesday Morning

- Improve PhysicsX answer bank.
- If coding time remains, polish the UI action timeline and one failing-eval
  example in docs.

### After PhysicsX

- Return to CFD fidelity:
  - OpenFOAM log parser.
  - `SimulationRunReport`.
  - actuator disk or stronger rotor source model.
  - better CAD / propeller modelling assessment.
  - dataset manifest for CFD-to-ML workflows.

## CAD / CFD Fidelity Position

The current legacy quadcopter CAD is good enough for the agentic engineering
demo because it supports:

- multi-surface geometry;
- OpenFOAM meshing;
- MRF zone placement;
- rigid roll/pitch/yaw transforms;
- ParaView inspection.

It is not good enough to make strong aerodynamic claims. The visible weak
downwash and mesh-quality warnings should be treated as evidence of good
engineering judgment: we can explain the limitation rather than overclaiming.

For BeyondMath, the next fidelity step is not "prettier CAD" first. The better
sequence is:

1. parse solver and mesh logs into typed quality reports;
2. make run quality machine-checkable;
3. improve rotor forcing with actuator disk/source-term treatment;
4. then reassess CAD quality or find a better prop/drone assembly.

## Interview Talking Track

Core line:

> Whittle uses agentic reasoning only where it belongs: messy human intent,
> scenario discovery, clarification, and tool choice. It crosses into typed
> Pydantic contracts before deterministic engineering artefacts are generated.
> That gives us auditability, evals, human review, and reproducibility.

Updated proof point:

> A lay request like "slowly yawing in place" now becomes a typed
> `ScenarioIntent`, a bounded `MotionRotorCommand` from the transparent
> performance table, and then a caveated `SimulationCaseSpec` with per-rotor
> MRF speeds. The agent can explain the caveat: this is a steady CFD proxy, not
> solved flight dynamics.

For Anima:

> The same pattern maps to clinical workflows: messy patient/clinician input,
> structured state, safety checks, traceable tool calls, and human review.

For PhysicsX:

> The same pattern maps to engineering simulation: domain expert intent,
> simulation intent, tool orchestration, validation gates, trace/eval loops, and
> a clear platform/application boundary.

For BeyondMath:

> The same pattern maps to CFD-to-ML data infrastructure: structured provenance,
> mesh/solver quality gates, repeatability, and explicit limits on what the
> generated data can support.
