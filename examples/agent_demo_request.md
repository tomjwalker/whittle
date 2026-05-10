# Agent Demo Request

Use this prompt to smoke-test the planning agent and UI:

```text
Set up cruise at 5 m/s with spinning propellers.
```

CLI:

```bash
uv run whittle agent-plan "Set up cruise at 5 m/s with spinning propellers." --case-name agent_demo
```

With no `OPENAI_API_KEY`, the command uses deterministic fallback. With
`OPENAI_API_KEY` set, it uses `WHITTLE_AGENT_MODEL`, defaulting to
`openai-responses:gpt-5.4-mini`.
