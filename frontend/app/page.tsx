"use client";

import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  CheckCircle2,
  FileCode2,
  Maximize2,
  Minimize2,
  PanelRightClose,
  PanelRightOpen,
  Send,
  Terminal,
  Trash2,
  Zap
} from "lucide-react";

type TraceEvent = {
  event_type: string;
  message: string;
  data?: Record<string, unknown>;
};

type ScenarioIntent = {
  objective: string;
  state: string;
  rotor_strategy: string;
  environment: string;
  confidence: number;
  requested_velocity_mps?: number | null;
  requested_yaw_rate_deg_s?: number | null;
  requested_roll_deg?: number | null;
  requested_pitch_deg?: number | null;
  requested_yaw_deg?: number | null;
  requested_mrf_omega_rad_s?: number | null;
  inferred_fields: Record<string, string | number | boolean>;
  missing_information: string[];
  assumptions: string[];
  warnings: string[];
  recommended_next_step?: string | null;
};

type ScenarioPlan = {
  user_request: string;
  scenario_type: string;
  intent: ScenarioIntent | null;
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

type SchemaRow = {
  field: string;
  value: string;
  state: "set" | "draft" | "missing";
  source: string;
};

const API_BASE = process.env.NEXT_PUBLIC_WHITTLE_API_URL ?? "http://127.0.0.1:8000";

const STARTERS = [
  "Set up cruise at 5 m/s with spinning propellers.",
  "Run pitch 10 degrees at 5 m/s with MRF rotors.",
  "Set up static hover at 0 m/s with MRF rotors at 1000 rad/s.",
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
  const [caseWritten, setCaseWritten] = useState(false);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [runLines, setRunLines] = useState<string[]>([]);
  const [openfoamRunning, setOpenfoamRunning] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalExpanded, setTerminalExpanded] = useState(false);
  const [terminalFocus, setTerminalFocus] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const spec = response?.scenario_plan?.spec ?? null;
  const intent = response?.scenario_plan?.intent ?? null;
  const canWrite = Boolean(spec && response?.status === "ready_for_human_review");
  const canRunOpenFOAM = caseWritten && !loading && !openfoamRunning;
  const statusClass = response?.status === "ready_for_human_review"
    ? "ok"
    : response?.status === "out_of_scope" || response?.status === "error"
      ? "warn"
      : "";

  const schemaRows = useMemo<SchemaRow[]>(() => {
    const specRecord = spec as Record<string, unknown> | null;
    const geometry = specRecord?.geometry as Record<string, unknown> | undefined;
    const mrfZones = specRecord?.mrf_zones as unknown[] | undefined;
    const rotorDiskSources = specRecord?.rotor_disk_sources as unknown[] | undefined;
    const missing = response?.scenario_plan?.missing_information ?? [];
    const attitude = specRecord
      ? `${formatSchemaNumber(specRecord.roll_angle_deg)} / ${formatSchemaNumber(
          specRecord.pitch_angle_deg
        )} / ${formatSchemaNumber(specRecord.yaw_angle_deg)} deg`
      : intent
        ? `${formatSchemaNumber(intent.requested_roll_deg)} / ${formatSchemaNumber(
            intent.requested_pitch_deg
          )} / ${formatSchemaNumber(intent.requested_yaw_deg)} deg`
        : "unset";

    const rotorSourceCount = (mrfZones?.length ?? 0) + (rotorDiskSources?.length ?? 0);
    return [
      schemaRow("case_name", specRecord?.case_name ?? caseName, Boolean(specRecord), "draft"),
      schemaRow("geometry", geometry?.name, Boolean(geometry), "missing"),
      schemaRow(
        "reference_velocity_mps",
        specRecord?.reference_velocity_mps ?? intent?.requested_velocity_mps,
        specRecord?.reference_velocity_mps !== undefined,
        intent?.requested_velocity_mps !== undefined ? "draft" : "missing",
        "m/s"
      ),
      schemaRow(
        "rotor_model",
        specRecord?.rotor_model ?? intent?.rotor_strategy,
        specRecord?.rotor_model !== undefined,
        intent?.rotor_strategy ? "draft" : "missing"
      ),
      schemaRow("solver_family", specRecord?.solver_family ?? "simpleFoam", Boolean(specRecord), "draft"),
      {
        field: "attitude_rpy",
        value: attitude,
        state: specRecord ? "set" : intent ? "draft" : "missing",
        source: specRecord ? "SimulationCaseSpec" : intent ? "ScenarioIntent" : "waiting",
      },
      {
        field: "rotor_sources",
        value: rotorSourceCount ? `${rotorSourceCount} configured` : intent?.rotor_strategy ?? "unset",
        state: rotorSourceCount ? "set" : intent?.rotor_strategy ? "draft" : "missing",
        source: rotorSourceCount ? "SimulationCaseSpec" : intent?.rotor_strategy ? "ScenarioIntent" : "waiting",
      },
      {
        field: "missing_information",
        value: missing.length ? `${missing.length} open` : "none",
        state: missing.length ? "missing" : specRecord || intent ? "set" : "draft",
        source: missing.length ? "planner" : "validator",
      },
    ];
  }, [caseName, intent, response?.scenario_plan?.missing_information, spec]);

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
    setCaseWritten(false);
    setRunStatus(null);
    setRunLines([]);
    setOpenfoamRunning(false);
    setTrace([]);
    const conversationHistory = buildConversationHistory(turns);
    const previousPlan = response?.scenario_plan ?? null;

    try {
      const res = await fetch(`${API_BASE}/api/plan/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          case_name: caseName || "ui_planned_case",
          deterministic,
          conversation_history: conversationHistory,
          previous_plan: previousPlan
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
    setCaseWritten(true);
  }

  async function runOpenFOAM() {
    const activeCaseName = String(spec?.case_name ?? (caseName || "ui_planned_case"));
    setRunStatus("Running OpenFOAM in WSL...");
    setRunLines([]);
    setTerminalOpen(true);
    setTerminalExpanded(true);
    setTerminalFocus(true);
    setOpenfoamRunning(true);
    try {
      const res = await fetch(`${API_BASE}/api/openfoam/run/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_name: activeCaseName })
      });
      if (!res.ok || !res.body) {
        setRunStatus(`Run failed to start: HTTP ${res.status}`);
        return;
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
          handleRunLine(line);
        }
      }
      if (buffer.trim()) {
        handleRunLine(buffer);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setRunStatus(`Run stream failed: ${message}`);
      setRunLines((prev) => [
        ...prev,
        `run_failed: The OpenFOAM run stream ended unexpectedly: ${message}`
      ]);
    } finally {
      setOpenfoamRunning(false);
    }
  }

  function handleRunLine(line: string) {
    if (!line.trim()) return;
    let event: { type: string; message: string };
    try {
      event = JSON.parse(line) as { type: string; message: string };
    } catch {
      event = { type: "line", message: line };
    }
    if (["run_start", "step_start", "step_done", "target", "done"].includes(event.type)) {
      setRunStatus(event.message);
    }
    if (event.type === "run_complete" || event.type === "run_failed") {
      setRunStatus(event.message);
    }
    setRunLines((existing) => [...existing.slice(-240), `${event.type}: ${event.message}`]);
  }

  return (
    <main className={`app-shell ${inspectorOpen ? "" : "inspector-collapsed"}`}>
      <section className="workspace">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark"><Zap size={18} /></span>
            <span>Whittle</span>
          </div>
          <div className="meta-row">
            <Terminal size={15} />
            <span>{response?.model ?? "openai-responses:gpt-5.4-mini"}</span>
            {!inspectorOpen ? (
              <button
                className="icon-button rail-toggle"
                type="button"
                onClick={() => setInspectorOpen(true)}
                aria-label="Show planning state"
                title="Show planning state"
              >
                <PanelRightOpen size={16} />
              </button>
            ) : null}
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
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
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

      {inspectorOpen ? <aside className="inspector">
        <div className="inspector-header">
          <div className="inspector-title-row">
            <h2>Planning State</h2>
            <button
              className="icon-button rail-toggle"
              type="button"
              onClick={() => setInspectorOpen(false)}
              aria-label="Collapse planning state"
              title="Collapse planning state"
            >
              <PanelRightClose size={16} />
            </button>
          </div>
          <div className="state-summary">
            <p className={`status ${statusClass}`}>
              {statusClass === "ok" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {response?.status ?? "idle"}
            </p>
            <span>{response?.phase ?? "waiting_for_request"}</span>
          </div>
          <TraceRail trace={trace} />
        </div>

        <div className="inspector-scroll">
          <section className="section step-section">
            <h3>Current Step</h3>
            <p className="inspector-copy">
              {response?.summary ??
                "Ask for a drone CFD scenario and I will help turn it into a typed case."}
            </p>
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

          <section className="section schema-section">
            <div className="section-title-row">
              <h3>SimulationCaseSpec</h3>
              <span className="schema-source">{response?.source ?? "not_started"}</span>
            </div>
            <div className="schema-list">
              {schemaRows.map((row) => (
                <div className={`schema-row ${row.state}`} key={row.field}>
                  <code>{row.field}</code>
                  <strong>{row.value}</strong>
                  <span>{row.state}</span>
                </div>
              ))}
            </div>
          </section>

          <details className="fold-section">
            <summary>Intent draft</summary>
            <section className="section nested">
              {intent ? (
                <>
                  <div className="intent-header">
                    <span className={`intent-state ${intentStateClass(intent.state)}`}>
                      {labelIntentState(intent.state)}
                    </span>
                    <span className="confidence">
                      {Math.round((intent.confidence ?? 0) * 100)}% confidence
                    </span>
                  </div>
                  <div className="intent-grid">
                    <IntentValue label="Objective" value={intent.objective} />
                    <IntentValue label="Rotor strategy" value={intent.rotor_strategy} />
                    <IntentValue label="Environment" value={intent.environment} />
                    <IntentValue
                      label="Velocity"
                      value={formatOptionalNumber(intent.requested_velocity_mps, "m/s")}
                    />
                    <IntentValue
                      label="Yaw rate"
                      value={formatOptionalNumber(intent.requested_yaw_rate_deg_s, "deg/s")}
                    />
                    <IntentValue
                      label="Omega"
                      value={formatOptionalNumber(intent.requested_mrf_omega_rad_s, "rad/s")}
                    />
                  </div>
                  {intent.recommended_next_step ? (
                    <p className="inspector-copy">{intent.recommended_next_step}</p>
                  ) : null}
                </>
              ) : (
                <p className="small-note">No intent draft yet.</p>
              )}
            </section>
          </details>

          <details className="fold-section">
            <summary>Trace and checks</summary>
            <section className="section nested">
              <div className="trace-list">
                {trace.length ? trace.map((item, index) => (
                  <div className="trace-item" key={`${item.event_type}-${index}`}>
                    <span className="trace-dot" />
                    <span><strong>{item.event_type}</strong><br />{item.message}</span>
                  </div>
                )) : <p className="small-note">No run yet.</p>}
              </div>
            </section>
          </details>

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

          <details className="fold-section">
            <summary>Assumptions and warnings</summary>
            <section className="section nested">
              <h3>Assumptions</h3>
              {response?.scenario_plan?.assumptions?.length ? (
                <ul className="list">
                  {response.scenario_plan.assumptions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : <p className="small-note">None recorded.</p>}
              <h3>Warnings</h3>
              {response?.scenario_plan?.warnings?.length ? (
                <ul className="list">
                  {response.scenario_plan.warnings.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : <p className="small-note">None.</p>}
            </section>
          </details>

          <details className="fold-section raw-contract">
            <summary>Raw Contract</summary>
            <section className="section nested">
              <pre>{JSON.stringify(response?.scenario_plan ?? {}, null, 2)}</pre>
            </section>
          </details>
        </div>

        <div className={`write-strip ${terminalFocus ? "terminal-focus" : ""}`}>
          <button className="command-button secondary" type="button" disabled={!canWrite} onClick={writeCase}>
            <FileCode2 size={17} />
            Write case
          </button>
          <button
            className="command-button secondary"
            type="button"
            disabled={!canRunOpenFOAM}
            onClick={runOpenFOAM}
          >
            <Terminal size={17} />
            Mesh/run
          </button>
          <p className="small-note">
            {writeStatus ?? "Files are written under outputs/agent_cases after review."}
          </p>
          <section className={`run-terminal ${terminalOpen ? "open" : ""}`}>
            <div className="run-terminal-header">
              <button
                className="terminal-toggle"
                type="button"
                onClick={() => setTerminalOpen((value) => !value)}
                disabled={!runStatus && !runLines.length}
              >
                <Terminal size={15} />
                OpenFOAM terminal
                {terminalOpen ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
              </button>
              <button
                className="icon-button terminal-clear"
                type="button"
                onClick={() => {
                  setRunLines([]);
                  setRunStatus(null);
                }}
                disabled={!runStatus && !runLines.length}
                aria-label="Clear terminal"
                title="Clear terminal"
              >
                <Trash2 size={15} />
              </button>
              <button
                className="icon-button terminal-clear"
                type="button"
                onClick={() => {
                  setTerminalExpanded((value) => !value);
                  setTerminalFocus((value) => !value);
                }}
                disabled={!runStatus && !runLines.length}
                aria-label={terminalExpanded ? "Shrink terminal" : "Expand terminal"}
                title={terminalExpanded ? "Shrink terminal" : "Expand terminal"}
              >
                {terminalExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              </button>
            </div>
            {runStatus ? <p className="terminal-status">{runStatus}</p> : null}
            {terminalOpen ? (
              <pre className={`run-log ${terminalExpanded ? "expanded" : ""}`} aria-live="polite">
                {runLines.length
                  ? runLines.slice(-180).join("\n")
                  : "No OpenFOAM run output yet."}
              </pre>
            ) : null}
          </section>
        </div>
      </aside> : null}
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
      "IntentDrafted",
      "PreviousPlanApplied",
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
    IntentDrafted: "Intent",
    PreviousPlanApplied: "Memory",
    ValidationRun: "Validated",
    ClarificationNeeded: "Clarify",
    HumanReviewNeeded: "Review",
    RequestOutOfScope: "Blocked",
    AgentOutputPlanned: "Responded",
    AgentError: "Error"
  };
  return labels[eventType] ?? eventType;
}

function IntentValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="intent-value">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatOptionalNumber(value: number | null | undefined, unit: string) {
  if (value === null || value === undefined) return "unset";
  return `${value} ${unit}`;
}

function formatSchemaNumber(value: unknown) {
  if (typeof value !== "number") return "unset";
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function schemaRow(
  field: string,
  rawValue: unknown,
  isSet: boolean,
  fallback: "draft" | "missing",
  unit?: string
): SchemaRow {
  const hasValue = rawValue !== null && rawValue !== undefined && rawValue !== "";
  const value = hasValue
    ? `${String(rawValue)}${unit ? ` ${unit}` : ""}`
    : "unset";
  return {
    field,
    value,
    state: isSet ? "set" : hasValue ? fallback : "missing",
    source: isSet ? "SimulationCaseSpec" : hasValue ? "ScenarioIntent" : "waiting",
  };
}

function intentStateClass(state: string) {
  if (state === "ready_for_spec") return "set";
  if (state === "blocked") return "blocked";
  if (state === "needs_clarification") return "proposed";
  return "draft";
}

function labelIntentState(state: string) {
  const labels: Record<string, string> = {
    ready_for_spec: "ready for spec",
    needs_clarification: "needs clarification",
    blocked: "blocked",
    proposed: "proposed"
  };
  return labels[state] ?? state;
}
