# PhysicsX

## Raw Role Summary

Role: Senior AI Engineer - Applied.

Location: London.

PhysicsX is a deep-tech company with roots in numerical physics and Formula
One. The role is focused on building advanced agentic workflows for engineering
and simulation customers.

Key supplied responsibilities:

- Build and deploy agentic functionality directly into the PhysicsX platform.
- Chain LLMs, tools, data, surrogates, and simulation capabilities to solve
  complex engineering reasoning tasks.
- Dogfood internal tools and improve developer experience.
- Work with domain experts to understand their mental models and codify them
  into agents.
- Help decide what belongs in the reusable platform versus customer/application
  layer.
- Implement rigorous evals and tracing, not vibe-based demos.

Tech stack supplied:

- Python primary; Go or TypeScript secondary.
- Kubernetes, Docker, Terraform.
- Agentic frameworks and vector databases.
- OpenTelemetry, agent tracing, and evaluation tooling.

Application questions worth preparing:

- How do you decide what belongs in a platform vs application layer?
- How have you orchestrated multiple LLM calls, tools, and data sources?
- What agentic frameworks have you used?
- How would you approach building an agent for a domain you are not expert in?
- What personal project are you most proud of?

Public site notes:

- PhysicsX describes itself as building an AI-driven simulation software stack
  across the full engineering lifecycle.
- Public platform messaging combines AI-driven multiphysics inference with
  numerical simulation, model training/fine-tuning/deployment, and customizable
  agentic applications.
- Public newsroom content explicitly discusses agentic engineering, including
  LLMs for intent understanding, physics models for prediction, geometry models
  for reasoning, tool orchestration, execution plans, checkpoints, and human
  review.

Sources:

- https://www.physicsx.ai/
- https://job-boards.greenhouse.io/physicsx/jobs/4804807101
- https://www.physicsx.ai/newsroom/agentic-engineering-revolution-the-physicsx-platform-and-microsoft-discovery-at-the-forefront-of-ai-innovation-part-1
- Supplied role text in this thread.

## What They Are Screening For

- Have you actually built agentic workflows, not just used chatbots?
- Can you compose LLMs, deterministic tools, domain data, evals, and traces?
- Can you work with domain experts and convert their tacit knowledge into
  deterministic tools and reusable workflows?
- Can you reason about platform versus application boundaries?
- Can you build a generalisable proof-point from a specific customer workflow?

## Whittle Mapping

Strong signals already present:

- Domain-heavy agent loop: lay request -> CFD planning -> typed Pydantic
  contract -> deterministic OpenFOAM writer.
- Clear platform/application boundary:
  - platform-ish: schemas, physics envelope, tools, case writer, eval harness
  - application-ish: drone-specific geometry, scenario prompts, UI flows
- PydanticAI planner with deterministic fallback.
- Visible trace events and human review state.
- Playwright UI smoke testing and eval fixtures.

Stronger if added:

- `ScenarioIntent` layer before `SimulationCaseSpec`, so the agent can reason
  flexibly before crossing the deterministic contract boundary.
- Logfire/OpenTelemetry tracing of model calls, tools, validation, and fallback.
- More explicit tool-call timeline in the UI.
- A small answer bank for the application questions using Whittle as evidence.

## Platform vs Application Layer Answer

Use Whittle as the example:

- Platform layer:
  - typed contracts
  - agent/tool orchestration primitives
  - trace and eval infrastructure
  - deterministic validators
  - case writer interfaces
  - reusable UI trace components
- Application layer:
  - drone geometry preset
  - legacy quadcopter rotor centres
  - scenario-specific prompt text
  - OpenFOAM v2012 quirks
  - current physics envelope limits

Rule of thumb:

> If the capability is reused across customers/domains and improves every
> workflow, it belongs in the platform. If it encodes one customer's geometry,
> assumptions, vocabulary, or acceptance criteria, keep it in the application
> layer until repeated demand proves it should be promoted.

## Interview Narrative

Best positioning:

> Whittle is a compact agentic engineering workflow for CFD. The LLM handles
> intent understanding and user coaching; deterministic tools handle physics
> envelope checks, transforms, file generation, and validation. I built it this
> way because engineering agents need to be auditable: traceable reasoning
> events, typed state, human checkpoints, eval fixtures, and deterministic
> fallbacks.

Emphasise:

- Agentic does not mean non-deterministic everywhere.
- The model should explore, interview, and propose; tools should verify and
  compile.
- Human review checkpoints are a feature, not a weakness, in engineering.

## Gaps To Close Before PhysicsX

- Add Logfire tracing or prepare a clear tracing story.
- Add `ScenarioIntent` as a flexible intermediate state.
- Improve UI trace chips into a cleaner agent action timeline.
- Prepare crisp answers to all supplied application questions.
