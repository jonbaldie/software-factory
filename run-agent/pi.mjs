// Runs pi headless, prints a readable log, and appends a final `result` line to
// the transcript in the same shape as Claude Code's, so action.yml can treat
// both harnesses alike.
//
// pi has no budget flag and no structured output, so this script adds both:
// it stops pi once the cost pi reports passes BUDGET, and when JSON_SCHEMA is
// set it asks for a JSON block and checks the one it gets back.
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";

const { PROMPT_FILE, MODEL, BUDGET, ALLOWED_TOOLS, JSON_SCHEMA, TRANSCRIPT } = process.env;
const budget = Number(BUDGET);
const schema = JSON_SCHEMA ? JSON.parse(JSON_SCHEMA) : null;

let prompt = readFileSync(PROMPT_FILE, "utf8");
if (schema) {
  prompt += [
    "",
    "## Output format",
    "",
    "End your final message with one JSON object in a ```json fenced block. It must match this JSON Schema:",
    "",
    "```json",
    JSON.stringify(schema, null, 2),
    "```",
    "",
  ].join("\n");
}

// --no-approve ignores project-local pi config (.pi/extensions and so on), so a
// PR under review can't load code into the agent.
const args = ["--print", "--mode", "json", "--no-session", "--no-approve", "--model", MODEL];
if (ALLOWED_TOOLS) {
  // The workflows use Claude Code's tool names. pi calls Glob `find`.
  const tools = ALLOWED_TOOLS.split(",").map((t) => (t.trim() === "Glob" ? "find" : t.trim().toLowerCase()));
  args.push("--tools", tools.join(","));
}

writeFileSync(TRANSCRIPT, "");
const pi = spawn("pi", args, {
  stdio: ["pipe", "pipe", "inherit"],
  detached: true, // its own process group, so a budget stop also ends any commands it started
  env: { ...process.env, PI_SKIP_VERSION_CHECK: "1", PI_TELEMETRY: "0" },
});
pi.stdin.end(prompt);

let spent = 0; // cost of finished assistant messages
let streaming = 0; // cost so far of the message being streamed
let turns = 0;
let last = null; // the last finished assistant message
let overBudget = false;

function handle(event) {
  switch (event.type) {
    case "message_update":
      streaming = event.usage?.cost?.total ?? 0;
      break;
    case "message_end": {
      const message = event.message;
      if (message.role !== "assistant") break;
      spent += message.usage?.cost?.total ?? 0;
      streaming = 0;
      last = message;
      for (const block of message.content ?? []) {
        if (block.type === "text" && block.text.trim()) console.log(`💬 ${block.text}`);
      }
      if (message.stopReason === "error") console.log(`❌ ${message.errorMessage}`);
      break;
    }
    case "tool_execution_start":
      console.log(`🔧 ${event.toolName} ${JSON.stringify(event.args).slice(0, 200)}`);
      break;
    case "turn_end":
      turns++;
      break;
    case "auto_retry_start":
      console.log(`🔁 Retry ${event.attempt} of ${event.maxAttempts}: ${event.errorMessage}`);
      break;
  }
  if (!overBudget && spent + streaming > budget) {
    overBudget = true;
    console.log(`🛑 Spent $${(spent + streaming).toFixed(4)}, over the $${budget} budget. Stopping pi.`);
    try { process.kill(-pi.pid, "SIGTERM"); } catch {}
    setTimeout(() => { try { process.kill(-pi.pid, "SIGKILL"); } catch {} }, 5000).unref();
  }
}

// pi's stream is JSONL split on LF only (see pi's docs/json.md), so don't use readline.
let buffer = "";
pi.stdout.setEncoding("utf8");
pi.stdout.on("data", (chunk) => {
  appendFileSync(TRANSCRIPT, chunk);
  buffer += chunk;
  let newline;
  while ((newline = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, newline).replace(/\r$/, "");
    buffer = buffer.slice(newline + 1);
    if (!line) continue;
    try {
      handle(JSON.parse(line));
    } catch (error) {
      console.log(`⚠️ Unreadable event: ${error.message}`);
    }
  }
});

const exitCode = await new Promise((resolve) => pi.on("close", (code) => resolve(code)));

const text = (last?.content ?? [])
  .filter((block) => block.type === "text")
  .map((block) => block.text)
  .join("\n")
  .trim();

let subtype = "success";
let structured = null;
if (overBudget) {
  subtype = "error_max_budget_usd";
} else if (exitCode !== 0 || !last || ["error", "aborted"].includes(last.stopReason)) {
  // pi exits 0 in JSON mode even when the provider fails, so check the last message too.
  subtype = "error_during_execution";
} else if (schema) {
  structured = readStructured(text, schema);
  if (!structured) subtype = "error_structured_output";
}

const result = {
  type: "result",
  subtype,
  is_error: subtype !== "success",
  num_turns: turns,
  total_cost_usd: spent + streaming,
  result: text || last?.errorMessage || "",
  ...(structured && { structured_output: structured }),
};
// If pi was stopped mid-event, end that partial line first.
appendFileSync(TRANSCRIPT, (buffer ? "\n" : "") + JSON.stringify(result) + "\n");
console.log(`🏁 ${subtype} · ${turns} turns · $${result.total_cost_usd.toFixed(4)}`);

// The last ```json block in the message, if it has the schema's required keys and
// top-level types and enums. Anything else counts as no answer, so the stage fails
// rather than acting on a guess.
function readStructured(text, schema) {
  const value = lastJsonBlock(text);
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  for (const key of schema.required ?? []) {
    if (!(key in value)) return null;
  }
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    if (!(key in value)) continue;
    const v = value[key];
    if (property.enum && !property.enum.includes(v)) return null;
    if (property.type === "string" && typeof v !== "string") return null;
    if (property.type === "array") {
      if (!Array.isArray(v)) return null;
      if (property.items?.type === "string" && !v.every((item) => typeof item === "string")) return null;
    }
  }
  return value;
}

// The parsed value of the last ```json block, or undefined if there is none or it
// isn't closed or isn't valid JSON. A block ends at the first ``` after its opening
// line, unless what comes before that isn't valid JSON but runs on to a later ```
// that is: then the earlier ``` was inside a JSON string.
function lastJsonBlock(text) {
  const parse = (json) => { try { return { value: JSON.parse(json) }; } catch { return null; } };
  const opener = /```json\s*\n/g;
  let last;
  while (opener.exec(text)) {
    const start = opener.lastIndex;
    const first = text.indexOf("```", start);
    if (first < 0) return undefined;
    let end = first;
    let parsed = parse(text.slice(start, first));
    for (let e = text.indexOf("```", first + 1); !parsed && e >= 0; e = text.indexOf("```", e + 1)) {
      parsed = parse(text.slice(start, e));
      if (parsed) end = e;
    }
    last = parsed?.value;
    // A block with no valid JSON may have run on to the next block's opening fence.
    opener.lastIndex = parsed ? end + 3 : first;
  }
  return last;
}
