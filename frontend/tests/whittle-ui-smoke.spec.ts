import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

const coachingResponse = {
  status: "needs_clarification",
  phase: "scenario_discovery",
  assistant_message: "That is a design goal rather than a CFD case yet.",
  summary: "Need scenario, speed, and rotor modelling choice before case writing.",
  scenario_plan: {
    user_request: "Make this drone more aerodynamic.",
    scenario_type: "vague_request",
    spec: null,
    assumptions: [],
    warnings: [],
    missing_information: ["Request does not specify a CFD scenario, velocity, or geometry."],
    clarifying_questions: [
      "Do you want external cruise, a pitched attitude case, or a rotor/downwash case?",
    ],
    trace_events: [],
  },
  trace_events: [
    {
      event_type: "RequestReceived",
      message: "Natural-language scenario request received.",
      data: {},
    },
    {
      event_type: "ClarificationNeeded",
      message: "Planner needs more information before files can be written.",
      data: {},
    },
  ],
  model: "deterministic-test",
  source: "deterministic_fallback",
  next_actions: [
    "Set up cruise at 5 m/s with MRF rotors.",
    "Run pitch 10 degrees at 5 m/s with MRF rotors.",
  ],
};

test("coaching response shows quick actions and no stale typed spec", async ({ page }) => {
  await page.route("**/api/plan/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/x-ndjson",
      body: `${JSON.stringify({ type: "complete", response: coachingResponse })}\n`,
    });
  });

  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.getByPlaceholder("Describe the CFD case...").fill("Make this drone more aerodynamic.");
  await page.getByRole("button", { name: "Plan" }).click({ force: true });

  await expect(page.locator(".quick-action").first()).toBeVisible();
  await expect(page.locator(".phase-label")).toContainText("scenario_discovery");
  await expect(page.locator(".empty-spec")).toContainText("No writeable typed spec yet");
  await expect(page.locator(".trace-chip")).toHaveText(["Received", "Clarify"]);
});
