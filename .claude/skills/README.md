# Frame's skill set

Project skills for this repo. The product-management skills are Frame-adapted
ports of Anthropic's
[knowledge-work-plugins/product-management](https://github.com/anthropics/knowledge-work-plugins/tree/main/product-management)
plugin — adapted, not copied: upstream assumes connected SaaS tools (tracker,
analytics, chat); here **the repo is the tracker**, so every skill grounds its
claims in files, suites and commands, in the same evidence-first house style
`competitive-analysis` established.

## Upstream coverage map

| Upstream (plugin) | Here | Adaptation in one line |
|---|---|---|
| `competitive-brief` | `competitive-analysis` | + codebase gap matrix with file paths, + Opportunity Solution Tree bounded by Frame's invariants |
| `write-spec` | `write-prd` | Frame's normative PRD house style: `**XX-N (Px).**` requirements, prefix registry, index integration, fitness-checkable acceptance |
| `synthesize-research` | `synthesize-research` | + the landing rule: every finding becomes a PRD amendment, backlog item, estate finding, or explicit park |
| `metrics-review` | `metrics-review` | inverted sourcing: every number measured this session against spec budgets; vision §8 adoption metrics tracked as not-yet-measurable, honestly |
| `roadmap-update` | `roadmap-update` | Now/Next/Later *derived* from five in-repo sources of truth; statuses are evidence-backed, cuts stay visible one cycle |
| `sprint-planning` | `session-planning` | team-sprint → solo-session: one goal sentence, 70% planning, preflight (ports/emulator/seed), DoD = the verify suites |
| `stakeholder-update` | `stakeholder-update` | assembled from git log + suites + status docs; audiences: owner/engineering, steward/leadership, estate teams |
| `product-brainstorming` + `/brainstorm` | `product-brainstorming` | thinking-partner stance intact; adds the four forbidden patterns and vision N1–N12 as live walls, and routes convergence to `/write-prd` etc. |

Not ported: upstream's `CONNECTORS.md` / `.mcp.json` machinery (tool-connector
placeholders) — meaningless here, replaced by repo grounding.

## Other skills

- `frontend-design` — brand-token-constrained UI craft for this codebase.
- `interface-craft` — storyboarded animation, DialKit, design critique.
- `browser-test` — Playwright driving conventions for this repo.

## House rules all skills share

1. Claims trace to something produced this session (a fetch, a file, a
   command's output) — memory is a hypothesis.
2. Deliverables are files in `specs/` with dates, not chat-only knowledge.
3. Frame's constraints are inputs, not afterthoughts: the four deliberate
   breaks (CLAUDE.md), vision non-goals N1–N12, the fitness suite.
4. Statuses and numbers are earned (grep, run, measure), never asserted.
