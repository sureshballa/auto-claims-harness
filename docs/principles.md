# The 13 Harness Engineering Principles

## 1. Deny-first with human escalation

Block anything the harness doesn't recognize, then surface it to a human rather than guessing.

**Obeying:** An agent encounters an unfamiliar shell command; the harness rejects it and prompts the user for explicit approval before retrying.

**Violating:** The harness silently allows an unrecognized tool call because it "looks safe," bypassing any human review.

---

## 2. Graduated trust spectrum

Extend broader permissions to an agent incrementally as it demonstrates reliable behavior, rather than granting full trust at startup.

**Obeying:** After an agent completes 20 read-only tasks without incident, the harness automatically unlocks write permissions without requiring manual reconfiguration.

**Violating:** Every new agent session begins with unrestricted file-system access regardless of past behavior.

---

## 3. Defense in depth with layered mechanisms

Stack multiple independent safety checks using different techniques so no single failure opens the system.

**Obeying:** A destructive action must pass an allow-list check, a confirmation hook, and a rate-limit guard — defeating any one layer still leaves two more.

**Violating:** All safety logic lives in a single middleware function; disabling it removes every protection at once.

---

## 4. Externalized programmable policy

Safety and behavioral rules live in versioned config files with lifecycle hooks, not burned into the application source.

**Obeying:** Operators update allowed domains by editing `settings.json` and committing the diff; no redeploy needed and the change is auditable in git history.

**Violating:** Permitted actions are defined in a hardcoded `if/else` block inside the agent runtime; changing policy requires a code release.

---

## 5. Context as scarce resource with progressive management

Manage context window space through a staged compaction pipeline rather than a single hard truncation when the limit is reached.

**Obeying:** The harness summarizes old tool results first, then compresses conversation turns, then drops low-priority attachments — each stage triggered at a different threshold.

**Violating:** When the context window fills, the harness drops the oldest N tokens all at once, potentially cutting critical task state mid-sentence.

---

## 6. Append-only durable state

Persist history as immutable append-only records so every action is traceable and nothing can be silently rewritten.

**Obeying:** Each tool invocation appends a timestamped entry to an event log; replaying the log fully reconstructs the session.

**Violating:** The harness overwrites the previous checkpoint file with each new state snapshot, destroying the history of intermediate steps.

---

## 7. Minimal scaffolding, maximal operational harness

Keep the scaffolding thin and deterministic so the model's reasoning operates freely; invest engineering effort in reliable infrastructure, not in directing model thought.

**Obeying:** The harness provides stable tool contracts and permission enforcement, then lets the model decide how to sequence calls; no prompt-engineering wrappers second-guess its plan.

**Violating:** The harness wraps every model response in a chain-of-thought template that prescribes exactly which reasoning steps to follow, constraining the model's judgment.

---

## 8. Values over rules

Rely on the model's internalized values and contextual judgment for nuanced decisions, backed by deterministic guardrails for hard limits.

**Obeying:** The model declines a borderline request because it judges the action harmful — the harness enforces the hard floor (e.g., no shell exec) but doesn't need an explicit rule for every edge case.

**Violating:** Every conceivable scenario is encoded as an explicit rule; the model cannot deviate even when a rigid rule produces obviously wrong behavior.

---

## 9. Composable multi-mechanism extensibility

Offer layered extension points at different context costs (MCP servers, plugins, skills, hooks) rather than forcing all extensions through one unified API.

**Obeying:** A lightweight formatter ships as a hook (zero context cost); a knowledge-retrieval integration ships as an MCP server (full tool interface); each fits the right layer for its cost.

**Violating:** All extensions — from simple formatters to complex data sources — must register as full MCP tool servers, paying the same overhead regardless of complexity.

---

## 10. Reversibility-weighted risk assessment

Apply heavier oversight to destructive or irreversible actions and lighter oversight to read-only or easily undone ones.

**Obeying:** Reading a file is auto-approved; deleting a branch requires an explicit user confirmation prompt.

**Violating:** Every action, including `ls` and `cat`, requires manual user approval, creating alert fatigue that causes users to rubber-stamp genuinely dangerous operations.

---

## 11. Transparent file-based configuration and memory

Store configuration and persistent memory in human-readable, version-controllable files — not opaque databases or binary blobs.

**Obeying:** Agent memory is written to `~/.claude/memory/*.md`; users can read, edit, or `git diff` it like any source file.

**Violating:** Memory is stored in a local SQLite database that requires a special CLI command to inspect and cannot be diffed or committed.

---

## 12. Isolated subagent boundaries

Subagents receive only the context and permissions they need for their task; they don't inherit the parent's full context or permission set.

**Obeying:** A spawned review agent receives only the diff it needs to review; it cannot access the parent's API keys or conversation history.

**Violating:** Every subagent is forked with the full parent context and all permissions, meaning a compromised subagent can exfiltrate or act on everything the parent holds.

---

## 13. Graceful recovery and resilience

Handle transient errors silently with automatic recovery; escalate to humans only when a situation is genuinely unrecoverable.

**Obeying:** A flaky network call is retried with exponential backoff; only after five consecutive failures does the harness surface an error to the user.

**Violating:** Every tool call failure immediately halts the session and demands human intervention, including momentary network blips that would self-resolve in seconds.
