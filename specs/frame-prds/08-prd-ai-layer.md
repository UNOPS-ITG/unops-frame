# PRD 08: AI Layer

## Purpose

Two altitudes, one boundary: native assists for interactive, human-reviewed moments; Playbook for repeatable, consequential, or autonomous patterns. The documented rule: if a person asks and immediately reviews, it is native; if a process runs and people rely on its output, it is Playbook. Frame is MCP-native so the agent ecosystem can act on structured work under permissions.

## Scope

In: native assist features, the AI gateway, the promotion review assistant, MCP surface, AI provenance. Out: agent orchestration, evaluation workflows, scheduled AI processes (Playbook's product; Frame integrates).

## Functional requirements

### Native assists

**AI-1 (P1).** Model from language: a description ("track vendor security assessments with a reviewer, a risk rating, and a 30-day follow-up") yields a draft Blueprint (fields, types, a starter state machine, suggested validation) rendered for edit before creation. Also accepts a pasted spreadsheet header row or CSV sample as input for type inference (feeds BP-16).

**AI-2 (P1).** Formula and filter authoring: natural language to the shared grammar, inserted in an editable state with a plain-language readback ("this filters rows where amount exceeds 50,000 and state is Submitted"). Same surface serves automation conditions.

**AI-3 (P2).** Ask-this-view: questions over the current trimmed view, answered with citations to specific rows (two-pass citation pattern per Playbook practice), operating strictly on the viewer's trimmed data; the assistant is architecturally incapable of reading past a trim because it queries through the same evaluated path (PM-4).

**AI-4 (P2).** Field cleanup assists: normalize values in a selected column (vendor name variants, date formats), proposed as a reviewable change set applied atomically after confirmation; never auto-applied.

**AI-5 (P2).** One-shot summaries: a filtered view to a status paragraph or briefing bullet set, inserted where the user asked (comment, clipboard, dashboard text tile), tagged as AI-generated.

**AI-6 (P1).** Gateway: native assists call models through the standard estate gateway (model choice, logging, cost attribution per workspace, prompt retention per governance). No direct model calls from the client; the gateway applies our data handling rules (restricted-marked fields excluded from prompts unless the feature explicitly requires and the user's export permission allows).

**AI-12 (P2).** Recipe authoring from language: a described rule ("when an invoice over 50,000 arrives, get finance approval and notify the requester") yields a complete draft automation record — trigger from the AU-2 vocabulary, conditions in the shared grammar, actions from the AU-3 closed vocabulary — rendered in the sentence-style editor (AU-14's surface) for review before activation, with AI-2's plain-language readback. Where the described behaviour exceeds the closed vocabulary, the assist says so and names the sanctioned route (AU-3a); it never emits script and never proposes an action outside the vocabulary, so the boundary the platform enforces is the same one the assist teaches. One grammar and one closed vocabulary are what make this generation target checkable — the same request against an open-ended workflow builder has no validatable output shape.

**AI-13 (P3).** Usage visibility: workspace owners see their workspace's AI-assist and automation usage — assist counts and cost attribution from the AI-6 gateway, run volume from AU-6 — as attribution, never as a meter (PRD 04 anti-requirements). The incumbent ships the equivalent as an admin spend dashboard because usage is billing; Frame keeps the visibility, which is how a workspace notices a runaway pattern before operations does, without the toll.

### Governance boundary

**AI-7 (P1).** Anything autonomous, scheduled, bulk-affecting beyond a reviewed change set, or in a flagged domain routes to Playbook: Frame surfaces "run as a Playbook process" where users try to stretch native assists past the boundary, deep-linking into Playbook registration. The boundary is enforced in product, not just documented.

**AI-8 (P2).** Playbook integration: Playbook agents authenticate as registered service principals with scoped grants (PM-9), read and write through the public API and MCP, and their actions attribute in the activity log with process identity and run id, linking to Playbook's run record.

### Promotion review assistant

**AI-9 (P2).** For BP-17: catalog similarity scan (structural diff plus embedding similarity over field names, descriptions, and sampled values), normalization suggestions against data standards, inferred validation from team-tier data distributions, permission gap flags (content classification suggesting sensitivity markers), and a draft migration plan for identified look-alike trackers. All output lands as a pre-filled review case for Ingrid; nothing auto-approves.

### MCP surface

**AI-10 (P2).** Frame exposes an MCP server: tools for Blueprint discovery, query (shared grammar), row read/create/update, state transition, and document generation, each gated by the calling principal's grants and rate limits, with restricted-field handling per PM-10. Tool responses include transparency annotations so agents also know when they see a partial picture (an agent reasoning over silently trimmed data is a subtle failure mode; the annotation prevents it).

### Provenance

**AI-11 (P1).** Every AI-produced artifact carries provenance: feature, model and version, prompt reference, reviewing user. Blueprint provenance (BP-13) records AI assistance flags. This is what makes "AI-assisted, human-decided" auditable rather than asserted.

## Dependencies

Estate AI gateway, Playbook (registration, run records, citation utilities), PRD 01, PRD 05, PRD 04 (event context for assists).

## Open questions

1. Model routing per assist (fast model for formula authoring, stronger model for Blueprint drafting): gateway policy to be tuned with cost data.
2. Whether ask-this-view answers may aggregate across a user's multiple accessible Blueprints or stay single-view in v1. Position: single view; cross-Blueprint questions are Prism's conversational surface.
3. Embedding store for the similarity scan: reuse Corpus infrastructure vs a small dedicated index. Leaning Corpus reuse once its service boundary is stable.
