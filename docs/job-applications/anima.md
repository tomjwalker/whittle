# Anima

## Raw Opportunity Summary

Anima is hiring a small cohort of AI-native product builders. The role is not
framed as traditional software engineering. It is closer to founder-level
product ownership inside a domain: talk to customers, understand clinical
workflow pain, make product decisions, and orchestrate agents into shipped
healthcare software.

Key supplied facts:

- Serves about 10% of the UK population across 800+ clinics.
- $20M+ ARR, fast growth, cash-flow positive, about 32 people.
- Backed by YC, Molten, and Hummingbird.
- Mission: improve human wellbeing through a healthcare data engine and care
  enablement platform.
- Current products include Core/Triage, Documents, Scribe, Andi AI telephone
  assistant, Anima OS, Call Intelligence, and Talent Sourcer AI.
- Internal engineering emphasis: context engineering, mechanical constraints,
  custom linters, architectural guardrails, feedback loops, Playwright-driven
  UX/self-correction, and agent-friendly codebases.
- They describe Anima ADK as a proprietary agent framework with primitives such
  as `Parallel` and `Loop`, composable multi-layer agents, and decoupled context
  versus session rendering.

Public site notes:

- Anima positions itself as an integrated care platform combining online
  consultation, productivity tooling, care-team collaboration, and EHR
  integration.
- Public homepage claims over 600 practices and more than 5 million patients,
  while the role page says 800+ clinics and 10% of the UK population. Treat the
  supplied role page as the more specific hiring material.
- Product themes on the public site: triage, appointments, documents,
  analytics, integrations with EMIS/SystmOne/GP Connect/PDS, messaging, AI
  receptionist, and collaboration.

Sources:

- https://www.animahealth.com/
- Supplied private opportunity text in this thread.

## What They Are Screening For

- AI-native product judgment: can you convert messy real-world workflows into
  software and agent systems?
- Agency: can you get to a working outcome when the obvious path is blocked?
- Systems thinking: can you improve the production system, not just complete
  one task?
- Taste: can you reduce UX friction and make interfaces clinicians actually use?
- Context engineering: can you build repos, docs, evals, and guardrails that
  make agents more effective?
- Agent orchestration: can you reason about parallel agents, loops, feedback,
  tool use, and self-correcting development workflows?

## Whittle Mapping

Strong signals already present:

- `AGENTS.md`, docs hierarchy, runbooks, and current plan show context
  engineering.
- Pydantic schemas create typed boundaries between natural language, planning,
  physics envelope, and generated case files.
- The planner/UI demonstrates a human-in-the-loop agentic workflow:
  ambiguous user request -> agent coaching -> structured spec -> human review.
- The trace panel and eval harness demonstrate explicit reasoning artefacts
  without exposing hidden chain-of-thought.
- Playwright checks and frontend smoke tests map directly to their emphasis on
  UX feedback loops.

Stronger if added:

- Logfire tracing for PydanticAI and FastAPI so agent runs, tool calls, and
  fallback paths are inspectable.
- A clearer multi-turn scenario-honing loop that remembers state rather than
  replanning from one prompt.
- A short demo script showing how a vague request becomes a typed contract with
  trace events and deterministic checks.
- One example of a failing eval being caught and fixed.

## Interview Narrative

Best positioning:

> Whittle is my small, domain-heavy agentic engineering sandbox. I use the LLM
> where language and judgment matter, then cross a typed Pydantic contract
> boundary before anything deterministic or expensive happens. The repo is
> deliberately agent-friendly: context docs, guardrails, evals, visible traces,
> Playwright UI checks, and deterministic fallbacks.

Emphasise:

- The agent is not just "chat over code"; it drives a workflow toward a
  machine-checkable state.
- The deterministic boundary is deliberate because engineering/clinical
  workflows need safety and auditability.
- The UI should help a lay/domain user refine intent without exposing internal
  implementation detail.

## Gaps To Close Before Anima

- Add or at least prepare a Logfire tracing story.
- Improve multi-turn memory and progressive clarification in the chat UI.
- Prepare one concise example of agentic product loop:
  ambiguous request -> tool calls -> validation -> human review -> output.
- Be ready to discuss how this transfers to healthcare:
  clinical request -> structured state -> safety checks -> clinician review.

