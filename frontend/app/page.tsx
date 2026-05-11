"use client";

import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CircleHelp,
  CheckCircle2,
  FileCode2,
  ListChecks,
  Send,
  Terminal,
  Zap
} from "lucide-react";

type TraceEvent = {
  event_type: string;
  message: string;
  data?: Record<string, unknown>;
};

type ScenarioPlan = {
  user_request: string;
  scenario_type: string;
  spec: Record<string, unknown> | null;
  assumptions: string[];
  warnings: string[];
  missing_information: string[];
  clarifying_questions: string[];
  trace_events: TraceEvent[];
};

type AgentResponse = {
  status: string;
  phase: string;
  assistant_message: string;
  summary?: string | null;
  scenario_plan: ScenarioPlan | null;
  trace_events: TraceEvent[];
  model: string;
  source: string;
  next_actions: string[];
};

type ChatTurn = {
  id: string;
  user: string;
  assistant: string;
  nextActions?: string[];
  status?: string;
};

type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE = process.env.NEXT_PUBLIC_WHITTLE_API_URL ?? "http://localhost:8000";

const STARTERS = [
  "Set up cruise at 5 m/s with spinning propellers.",
  "Run pitch 10 degrees at 5 m/s with MRF rotors.",
  "I want to simulate hover takeoff from a floor.",
  "Make this drone more aerodynamic."
];

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [caseName, setCaseName] = useState("ui_planned_case");
  const [deterministic, setDeterministic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [response, setResponse] = useState<AgentResponse | null>(null);
  const [writeStatus, setWriteStatus] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const spec = response?.scenario_plan?.spec ?? null;
  const canWrite = Boolean(spec && response?.status === "ready_for_human_review");
  const statusClass = response?.status === "ready_for_human_review"
    ? "ok"
    : response?.status === "out_of_scope" || response?.status === "error"
      ? "warn"
      : "";

  const specSummary = useMemo(() => {
    if (!spec) return [];
    return [
      ["Case", String(spec.case_name ?? "unknown")],
      ["Velocity", `${String(spec.reference_velocity_mps ?? "?")} m/s`],
      ["Rotor model", String(spec.rotor_model ?? "none")],
      ["Roll", `${String(spec.roll_angle_deg ?? 0)} deg`],
      ["Pitch", `${String(spec.pitch_angle_deg ?? 0)} deg`],
      ["Yaw", `${String(spec.yaw_angle_deg ?? 0)} deg`],
      ["Solver", String(spec.solver_family ?? "simpleFoam")]
    ];
  }, [spec]);

  async function submit(message = prompt) {
    const trimmed = message.trim();
    if (!trimmed || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const turnId = crypto.randomUUID();
    setTurns((existing) => [...existing, { id: turnId, user: trimmed, assistant: "" }]);
    setPrompt("");
    setLoading(true);
    setWriteStatus(null);
    setTrace([]);
    setResponse(null);
    const conversationHistory = buildConversationHistory(turns);

    try {
      const res = await fetch(`${API_BASE}/api/plan/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          case_name: caseName || "ui_planned_case",
          deterministic,
          conversation_history: conversationHistory
        }),
        signal: controller.signal
      });

      if (!res.ok || !res.body) {
        throw new Error(`Planner returned HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          handleStreamLine(line, turnId);
        }
      }
      if (buffer.trim()) {
        handleStreamLine(buffer, turnId);
      }
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "Unknown planner error";
      setTurns((existing) =>
        existing.map((turn) =>
          turn.id === turnId ? { ...turn, assistant: `Planner error: ${messageText}` } : turn
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function buildConversationHistory(existingTurns: ChatTurn[]): ConversationMessage[] {
    return existingTurns.flatMap((turn) => {
      const messages: ConversationMessage[] = [];
      if (turn.user.trim()) {
        messages.push({ role: "user", content: turn.user });
      }
      if (turn.assistant.trim()) {
        messages.push({ role: "assistant", content: turn.assistant });
      }
      return messages;
    });
  }

  function handleStreamLine(line: string, turnId: string) {
    if (!line.trim()) return;
    const event = JSON.parse(line) as {
      type: string;
      delta?: string;
      event?: TraceEvent;
      response?: AgentResponse;
    };

    if (event.type === "trace" && event.event) {
      setTrace((existing) => [...existing, event.event as TraceEvent]);
    }
    if (event.type === "assistant_delta" && event.delta) {
      setTurns((existing) =>
        existing.map((turn) =>
          turn.id === turnId ? { ...turn, assistant: `${turn.assistant}${event.delta}` } : turn
        )
      );
    }
    if (event.type === "complete" && event.response) {
      setResponse(event.response);
      setTrace(event.response.trace_events ?? []);
      setTurns((existing) =>
        existing.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                assistant: event.response?.assistant_message ?? turn.assistant,
                nextActions: event.response?.next_actions ?? [],
                status: event.response?.status
              }
            : turn
        )
      );
    }
  }

  async function writeCase() {
    if (!spec) return;
    setWriteStatus("Writing OpenFOAM files...");
    const res = await fetch(`${API_BASE}/api/write-case`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec })
    });
    if (!res.ok) {
      setWriteStatus(`Write failed: HTTP ${res.status}`);
      return;
    }
    const payload = await res.json();
    setWriteStatus(`Written: ${payload.case_name} (${payload.files_written.length} files)`);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark"><Zap size={18} /></span>
            <span>Whittle</span>
          </div>
          <div className="meta-row">
            <Terminal size={15} />
            <span>{response?.model ?? "openai-responses:gpt-5.4-mini"}</span>
          </div>
        </header>

        <div className="conversation">
          {turns.length === 0 ? (
            <div className="empty-state">
              <h1>CFD planning, typed.</h1>
              <p>
                Convert a loose drone-aero request into a reviewed OpenFOAM case contract.
              </p>
              <div className="prompt-grid">
                {STARTERS.map((starter) => (
                  <button
                    className="prompt-chip"
                    key={starter}
                    type="button"
                    onClick={() => submit(starter)}
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            turns.map((turn, index) => (
              <div className="turn" key={turn.id}>
                <div className="message user">{turn.user}</div>
                <div className="message agent">
                  {turn.assistant || (loading ? "Working..." : "")}
                </div>
                {index === turns.length - 1 && turn.nextActions?.length ? (
                  <div className="quick-actions">
                    {turn.nextActions.map((action) => (
                      <button
                        className="quick-action"
                        key={action}
                        type="button"
                        disabled={loading}
                        onClick={() => submit(action)}
                      >
                        <ArrowRight size={14} />
                        <span>{action}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <div className="composer-box">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onInput={(event) => setPrompt(event.currentTarget.value)}
              placeholder="Describe the CFD case..."
            />
            <button className="command-button" type="submit" disabled={loading || !prompt.trim()}>
              <Send size={17} />
              Plan
            </button>
          </div>
          <div className="composer-options">
            <label>
              <input
                type="checkbox"
                checked={deterministic}
                onChange={(event) => setDeterministic(event.target.checked)}
              />{" "}
              Deterministic
            </label>
            <label>
              Case{" "}
              <input
                value={caseName}
                onChange={(event) => setCaseName(event.target.value)}
                aria-label="Case name"
              />
            </label>
          </div>
        </form>
      </section>

      <aside className="inspector">
        <div className="inspector-header">
          <h2>Planning State</h2>
          <p className={`status ${statusClass}`}>
            {statusClass === "ok" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            {response?.status ?? "idle"}
          </p>
          <p className="phase-label">{response?.phase ?? "waiting_for_request"}</p>
        </div>

        <div className="inspector-scroll">
          <section className="section compact">
            <h3>Agent Actions</h3>
            <TraceRail trace={trace} />
          </section>

          <section className="section">
            <h3>Current Step</h3>
            <p className="inspector-copy">
              {response?.summary ??
                "Ask for a drone CFD scenario and I will help turn it into a typed case."}
            </p>
            <div className="kv">
              <span>Source</span>
              <strong>{response?.source ?? "not_started"}</strong>
            </div>
            {response?.next_actions?.length ? (
              <div className="suggestion-stack">
                {response.next_actions.map((action) => (
                  <button
                    className="suggestion-button"
                    key={action}
                    type="button"
                    disabled={loading}
                    onClick={() => submit(action)}
                  >
                    <CircleHelp size={14} />
                    <span>{action}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <section className="section">
            <h3>Trace</h3>
            <div className="trace-list">
              {trace.length ? trace.map((item, index) => (
                <div className="trace-item" key={`${item.event_type}-${index}`}>
                  <span className="trace-dot" />
                  <span><strong>{item.event_type}</strong><br />{item.message}</span>
                </div>
              )) : <p className="small-note">No run yet.</p>}
            </div>
          </section>

          <section className="section">
            <h3>Spec</h3>
            {specSummary.length ? specSummary.map(([label, value]) => (
              <div className="kv" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            )) : (
              <div className="empty-spec">
                <ListChecks size={16} />
                <span>
                  No writeable typed spec yet. The agent is still scoping, coaching, or
                  asking for missing inputs.
                </span>
              </div>
            )}
          </section>

          {response?.scenario_plan?.clarifying_questions?.length ? (
            <section className="section">
              <h3>Clarifying Questions</h3>
              <ul className="list">
                {response.scenario_plan.clarifying_questions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {response?.scenario_plan?.missing_information?.length ? (
            <section className="section">
              <h3>Missing Information</h3>
              <ul className="list">
                {response.scenario_plan.missing_information.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="section">
            <h3>Assumptions</h3>
            {response?.scenario_plan?.assumptions?.length ? (
              <ul className="list">
                {response.scenario_plan.assumptions.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : <p className="small-note">None recorded.</p>}
          </section>

          <section className="section">
            <h3>Warnings</h3>
            {response?.scenario_plan?.warnings?.length ? (
              <ul className="list">
                {response.scenario_plan.warnings.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : <p className="small-note">None.</p>}
          </section>

          <section className="section">
            <details className="raw-contract">
              <summary>Raw Contract</summary>
              <pre>{JSON.stringify(response?.scenario_plan ?? {}, null, 2)}</pre>
            </details>
          </section>
        </div>

        <div className="write-strip">
          <button className="command-button secondary" type="button" disabled={!canWrite} onClick={writeCase}>
            <FileCode2 size={17} />
            Write case
          </button>
          <p className="small-note">
            {writeStatus ?? "Files are written under outputs/agent_cases after review."}
          </p>
        </div>
      </aside>
    </main>
  );
}

function TraceRail({ trace }: { trace: TraceEvent[] }) {
  if (!trace.length) {
    return <p className="small-note">No agent actions yet.</p>;
  }

  const important = trace.filter((item) =>
    [
      "RequestReceived",
      "AgentStarted",
      "DeterministicDraftCreated",
      "FieldsExtracted",
      "ValidationRun",
      "ClarificationNeeded",
      "HumanReviewNeeded",
      "RequestOutOfScope",
      "AgentOutputPlanned",
      "AgentError"
    ].includes(item.event_type)
  );

  return (
    <div className="trace-rail">
      {important.map((item, index) => (
        <span className="trace-chip" key={`${item.event_type}-${index}`}>
          {labelTrace(item.event_type)}
        </span>
      ))}
    </div>
  );
}

function labelTrace(eventType: string) {
  const labels: Record<string, string> = {
    RequestReceived: "Received",
    AgentStarted: "Started",
    DeterministicDraftCreated: "Drafted",
    FieldsExtracted: "Extracted",
    ValidationRun: "Validated",
    ClarificationNeeded: "Clarify",
    HumanReviewNeeded: "Review",
    RequestOutOfScope: "Blocked",
    AgentOutputPlanned: "Responded",
    AgentError: "Error"
  };
  return labels[eventType] ?? eventType;
}
