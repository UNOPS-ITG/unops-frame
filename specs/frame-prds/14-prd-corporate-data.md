# PRD 14: Corporate Data — Master Data and Facts

## Purpose

Frame's rows are full of strings that should be keys. Somebody types "Kenya CO" in one tracker and "KECO" in another, and the archaeology problem the vision describes reappears one column at a time. UNOPS already holds the answer: every project, country, fund, business unit, supplier and position, plus the transactional facts about them, lives in BigQuery, where access is decided by IAM, row access policies and column policy tags evaluated against each staff member's own Google identity.

This PRD makes a Blueprint field bindable to that data. Two properties make it more than an integration. The catalogue is **discovered**, not registered, so there is no queue between a Blueprint author and the master data. And every warehouse read that could vary by person executes under that person's own credentials, so BigQuery remains the single place "who may see which corporate data" is ever answered. Frame adds no rule about corporate data and holds no copy of anyone's entitlements.

It is also the one capability in this product set that no external vendor can match, and the reason is structural rather than competitive: a SaaS platform outside our tenancy cannot run a query inside our warehouse as our staff member. What it sells instead is a scheduled copy, whose entitlements stay behind at the tenancy boundary and must be re-expressed by hand, inside its product, forever.

**What the warehouse already provides.** This PRD is unusually cheap because the data platform team has already built most of it. `unops-datahub` publishes a curated interface layer — `Dimensions_Api` (569 views), `Facts_Api` (393 views), `Integrations_Api` — over base datasets, alongside `Metadata_Api`, a purpose-built catalogue of eight views carrying table and column descriptions, declared business keys, a DIMENSION-or-MEASURE classification per column, security policy tags, named data stewards for eight business domains, and a declared relationship graph of roughly 3,600 edges — 2,780 of them from facts to the dimensions that define their grain. Frame reads that catalogue rather than inferring one.

**One constraint shapes everything below.** BigQuery has no sub-100ms point lookup and no acceleration path on the tables that matter. Query results are not cached for tables under row-level security and may not be under column-level security; BI Engine does not accelerate queries on tables carrying row access policies; a materialized view over such a table performs like the base table. There is no warehouse-side trick that makes an entitlement-varying picker fast, so speed comes from a narrow projection in our own store — of data that is *provably* no more revealing than what the least-entitled member of staff already sees, and of nothing else. **Frame caches no label that anyone may be denied.** That single line is the difference between a projection and a permission bypass.

## Scope

**In:** source registration, the discovery sweep and its classification, disclosure classification and its mechanical proof, the dimension mirror, the corporate reference and corporate figure field types and what they persist, resolution paths and their budgets, user-context OAuth and consent lifecycle, non-interactive execution rules, cost governance, referential integrity and retirement, the published descriptor, and the corporate-data behaviour of search, replication, documents, import and AI.

**Out:** authentication mechanics beyond the added scope (platform standard, PRD 09); permission evaluation semantics (PRD 05, consumed here); semantic modelling, metrics, joins for analysis and any charting over warehouse data (Prism, per vision N2 and N10); and warehouse curation itself — the data platform team owns views, grain, partitioning, aggregation and policies, and this PRD depends on that ownership rather than substituting for it.

## Sources and discovery

**CD-1 (P1).** A **Source** is the only corporate-data artifact a human authors. It names a warehouse platform, a per-environment GCP project, a location, the execution project for each operation class, and a dataset filter — Frame lists the available datasets and selects all by default, so exclusion is the administrator's only routine act. Sources are **code-first application configuration**: they name per-environment GCP projects and execution projects, they are ITG platform property, and they legitimately differ per environment, which is exactly what the index's configuration architecture describes.

**CD-2 (P1).** Everything else is **discovered**. A scheduled sweep reads the warehouse's own published metadata and maintains the catalogue of bindable dimensions, facts and relationships. There is no registration queue, no steward turnaround target and no approval gate between a Blueprint author and the master data — deliberately, because a gate here would produce exactly the failure the promotion ladder exists to prevent: a slow gate is not bypassed politely, it is bypassed, and the bypass is somebody typing the project name as free text.

The sweep runs on a declared cadence per source and on demand. Catalogue state — dimensions, facts, relationships, disclosure classes, the mirror, probe results, the key ledger, the cost ledger — is neither configuration nor user content: it is disposable, rebuildable, environment-local projection data, and it never rides a build.

**CD-3 (P1).** What the sweep reads, in precedence order. The **published metadata catalogue** is authoritative where it exists: relation inventory with descriptions, business keys, partition and cluster columns, per-column descriptions and DIMENSION-or-MEASURE classification, security policy tags, business domains with named data stewards, lifecycle flags, and the declared relationship graph with cardinality, join semantics, a human-readable relationship verb and per-edge enablement. **`INFORMATION_SCHEMA`** supplies what the catalogue does not: live column lists and types as ground truth against possibly-stale catalogue rows, native per-column descriptions, row counts and byte sizes for cardinality and cost tiering, and row-access-policy and policy-tag presence for CD-9.

Where a warehouse offers no published catalogue, the sweep degrades to `INFORMATION_SCHEMA` alone, including declared primary and foreign key constraints where present, with name-and-type matching as a last resort surfaced at low confidence for administrator confirmation. Frame does not require a published catalogue; it prefers one, strongly, and says so in the source registration UI.

**CD-4 (P1).** Classification. A relation resolves to a **dimension** (master data: a key, a label, attributes, optionally a hierarchy), a **fact** (a grain expressed as dimension references plus a period, and measure columns), or neither. Where the warehouse declares the answer — by dataset membership, by a declared business key, by a per-column DIMENSION-or-MEASURE marker — that declaration is taken. Where it does not, classification is heuristic and carries a confidence.

An administrator may **correct** a classification, and the correction survives subsequent sweeps. This is a permanent but narrow human surface: correction, never authoring. A correction may never widen a disclosure class (CD-9), which remains machine-assigned only.

Every relation Frame binds is a **view**, by convention one the data platform team owns and commits to as a published interface. Frame composes no SQL of its own shape: every relation is a named dataset object and every filter is a declared, typed, named parameter.

**CD-5 (P1).** Change detection and retirement. Each sweep diffs against the previous catalogue and emits additions, changes and removals on the AU-8 event contract. Where the warehouse declares lifecycle state — a table status, an enablement flag, a deletion flag, a per-edge enablement flag — that declaration is the trigger rather than an inference.

A relation that disappears, is disabled upstream, or is re-pointed at a different base table is **quarantined**: it stops serving new picks immediately, existing stored labels keep rendering with a staleness marker, and the change raises on an integrity panel for a steward. Detection is instant and free; remediation is a scheduled migration with a costed downstream cascade, and the two are never conflated into one button. **Frame does not auto-rewrite governed rows from the warehouse.** This matters more under automatic discovery than it would under manual registration, because the catalogue moves without a human deciding.

## The two authorities

**CD-6 (P1).** Composition invariant, normative. PM-4 governs every read of Frame data; BigQuery governs every read of warehouse data; the two govern disjoint object universes and are composed **by sequence, never by conjunction over the same object**. A value crosses the boundary exactly once — at pick time, at a mirror sync, or at a declared refresh — under a named identity, and from that instant it is ordinary Frame data subject to PM-4 alone.

Frame computes no entitlement decision about warehouse data. It either delegates the whole decision to BigQuery by executing in the user's own context and rendering what comes back, or it records that a value was admitted under a named principal and governs the copy under PM-2 and PM-3 like any other field. Frame may **narrow** what BigQuery returns; Frame may never **widen** it.

PM-4 is the outer gate and evaluates first, so a field PM-4 denies never causes a warehouse job to be issued. Otherwise the presence of an upstream error becomes an oracle about restricted content, and we pay money to leak.

**CD-7 (P1).** The structural guarantee behind CD-6: the catalogue schema and the corporate-data administration UI contain **no permission fields and no SQL entry surface**, at any tier, for any role. There is nowhere to express a rule about corporate data, so there is nothing to drift, and adding either is a platform decision rather than a configuration option. The two genuine Frame-side permission questions — who may register a source, and who may bind one into a Blueprint — are ordinary PM-2 rules on ordinary Frame objects, evaluated by the single library.

The falsifiable test, stated at the width it can actually hold: **no conditional anywhere in the Frame codebase may decide whether a given principal may see a given corporate value.** Frame may branch on whether a projection is entitlement-varying, which is a per-dimension fact; it may never branch on who is entitled to what. The CD-9 probe is the only code permitted to read IAM or policy metadata from the warehouse, and it may write only a per-dimension class, never a per-principal fact. Both halves are CI-enforceable and must be enforced in CI.

**CD-8 (P1).** Corporate data enters Frame only through an enumerated acquisition surface and nowhere else: an interactive picker under the viewer's own credentials; an interactive detail panel under the viewer's own credentials; an asynchronous per-viewer label or figure fill for a page the viewer is already rendering, under that viewer's own credentials; the mirror sync (CD-17) under the floor principal; and a declared figure refresh (CD-16). **No warehouse call is synchronous on a GR-9 interaction path.** No warehouse result is ever rendered to, cached for, or reused by a principal other than the one whose credentials produced it. The enumeration is the CI test: a call site outside the five listed surfaces fails the build.

## Disclosure classification

**CD-9 (P1).** Every dimension carries a disclosure class, assigned by mechanical probe and **never by assertion**.

- **`open`** — the key, code, label and declared attributes of this projection are disclosable to any authenticated staff member.
- **`entitled`** — rows, columns or labels vary by principal, *or the audience question cannot be answered mechanically*.

Four independent checks, any one of which forces `entitled`:

1. **Declared sensitivity.** Where the warehouse publishes a security policy tag per column, anything above the unrestricted level forces `entitled`. This is the fast path and it starts from a declared answer rather than a discovered one, but it is never sufficient alone — a policy tag describes a column's sensitivity, not who holds a grant on the dataset.
2. **Policy metadata.** `INFORMATION_SCHEMA` on the resolved base tables must show no row access policies and no policy tags on any projected column, **including the key and code columns** — a project code that encodes geography and funding line discloses as surely as a project name does.
3. **Dataset audience.** The dataset IAM policy on the registered relation's dataset and on every resolved base dataset must show the organization-wide all-staff group, or the domain, holding a data-read role. Anything narrower forces `entitled`. This check exists because plain dataset IAM is the most common way a dataset is narrowed, and it leaves no trace in a row-set comparison.
4. **Frame audience breadth.** No principal class Frame admits may be broader than the dataset's audience. A surface that would show mirror-served data to a principal without a UNOPS identity — an external form, an unauthenticated status page — is gated separately and the dimension is not `open` for it.

Policies attach to **base tables, not views**: a view cannot be referenced in a row access policy, and a view's data is filtered according to its underlying source table's policies. The sweep therefore resolves every registered relation to its full set of referenced base tables and runs checks 2 and 3 against those. A registered view silently re-pointed at a different base table is a quarantine event under CD-5.

The probe runs in two modes. At **registration or first classification**, interactively, with the administrator's own read compared against a floor principal's. At **every sweep**, non-interactively: checks 1, 2 and 4 are all readable by a service account and are what actually detect an upstream tightening, plus a floor-principal read compared against the previous floor-principal snapshot. The floor principal is constrained by construction — a member of exactly the all-staff group and nothing else — and any change to its group membership is a class-affecting audited event. An interactive re-attestation is required every 90 days; a catalogue entry whose attestation lapses auto-quarantines.

Column-level security manifests as an access **error** naming inaccessible columns, not as nulls, so the check tests for a successful select of the declared column list rather than for column nullity.

An administrator may register a **narrowed projection** — a view excluding a tagged column, or filtered to non-confidential rows — so the open subset of a partly sensitive dimension can serve as `open` while the remainder resolves live.

**CD-10 (P1).** Label visibility. Each dimension declares whether its label is `org`-visible or `entitled`. Most master-data labels are not sensitive; some disclose. Where `entitled`, a key the viewer cannot resolve renders as a PM-5 restricted stub rather than as a stored snapshot. Without this knob, the stored snapshot of CD-12 is a quiet bypass of the warehouse's policy, and it is the single most likely way this feature would leak.

## Binding and storage

**CD-11 (P1).** A Blueprint field of type **corporate reference** (BP-2) binds to a dimension. The author picks a dimension by its plain-language display name and description — never a dataset name, never a table name, never SQL — and Frame records the binding, the dimension's catalogue version and an optional narrowing filter over declared parameters. Bindings are ordinary Blueprint metadata, versioned under BP-12 and validated by BP-26.

**CD-12 (P1).** What a row stores: the **key**, a **label snapshot**, the snapshot timestamp, and the catalogue version that resolved it. The snapshot is what lets the grid filter, sort, group, export, search and generate documents without touching the warehouse, and it is deliberately the same shape as BP-9a reference-path formulas — one mechanism family, not two.

**The stored snapshot is the single label authority.** Rendering by joining to the mirror at read time would let the grid disagree with search, the replica and a generated document about the same field. One authority costs batched rewrite on an upstream rename; four authorities cost an unexplainable product.

**CD-13 (P2).** Carried attributes. A field may declare that additional columns of the bound dimension populate designated fields on the row — a project's region, portfolio and cost centre arriving with the project. These are BP-9a reference-path formulas with an external source, obeying the same materialisation, backfill and `overridable` rules, so BP-11's dependency graph and RP-7's schema generation continue to handle exactly two kinds of computed field.

**CD-14 (P2).** Constrained pickers. Where the catalogue declares a relationship between two dimensions, a Blueprint may declare that one bound field constrains another: choosing a project narrows the cost-centre picker to those related to it. The author declares the constraint by naming the two fields; the join is the catalogue's, never Frame's. Behaviour when the driving field is empty is declared as allow-unconstrained, warn, or block.

**CD-15 (P2).** Hierarchies. Where a dimension declares a hierarchy — levelled or recursive through a parent key — Frame exposes ancestor and descendant paths for display, for filtering, and as a source for PM-2a principal allow-lists under CD-28.

**CD-16 (P3).** A Blueprint field of type **corporate figure** binds to a measure on a fact, resolved for the row's own dimension keys. The author picks a figure from those reachable through declared relationships from the dimensions already bound on that Blueprint: they pick a figure, never a join, never a key, never a table. Where no path exists the figure is not offered and the picker names the dimension that would need to be added.

Figures declare a refresh basis — on demand, on a schedule, or on a declared upstream event — and materialise onto the row. Resolution is **batched one query per page**, never per row. A figure resolved under the viewer's own credentials carries the CD-30 annotation.

## Resolution and performance

**CD-17 (P1).** The mirror. Dimensions classified `open` are projected into a narrow schema in Frame's own Postgres — identifiers, label, code, declared attributes, hierarchy paths, timestamps — and served from there. Picker typeahead, label rendering and validation on write all resolve against the mirror. **No warehouse query executes on any read path for an `open` dimension, and no user sees a consent screen for one.**

This is an inversion of the stated mechanism and it is deliberate. For data the warehouse has already ruled every member of staff may see, executing per-user is theatre: it costs latency and money to reach a conclusion already known. User-context execution is preserved exactly where it is load-bearing.

The mirror is disposable and rebuildable by re-sync. It holds no data older than the source and is not a second source of truth. It is not the analytics replica: team and personal tiers appear here as reference data only, with no analytical modelling.

**CD-18 (P3).** Live resolution. Dimensions classified `entitled` resolve under the viewer's own credentials, asynchronously, never on a GR-9 interaction path. Results are cached **per principal**, never shared, with a short time-to-live and asynchronous refresh; the per-principal key is the rule that keeps CD-6's claim true. A viewer who has not consented to the warehouse scope, or who holds no entitlement, sees a defined state — an explanation and a route to request access — never an error and never an empty picker presented as an empty dimension.

**CD-19 (P1).** Budgets. Mirror-served picker typeahead resolves within the GR-9 interaction budget like any other Frame read. Live per-viewer typeahead targets 1.5s p95 and is debounced and asynchronous, because no result cache, no BI Engine acceleration and no small-table search index exists on policy-protected tables. Batched per-page label and figure fills target 2s p95. Validation of a bulk import against a dimension is batched, never per row.

## Credentials

**CD-20 (P1 for the scope; P3 for use).** The warehouse scope is obtained through the estate's existing user-consented connector pattern: a connector document declaring the scope, incremental consent computed as a delta against already-granted scopes, and refresh tokens held under envelope encryption in the platform key store. Adding the warehouse is therefore configuration rather than new code. The scope is added in Phase 1 even though nothing uses it until Phase 3, because retrofitting a consent round-trip onto an established user base is the part that is genuinely painful later.

Three gaps have no prior art in the estate and are this PRD's responsibility. An **access-token cache** with a per-user lock, double-checked read, expiry skew and an `invalid_grant` guard that refuses to overwrite the store — the existing refresh path performs a key-store decrypt and an OAuth round-trip per call, which is acceptable for occasional metadata reads and not for a query path. A **revocation path**, because nothing in the estate revokes a token today and disconnect explicitly does not; once queries execute as the user this is a compliance obligation. And a **cross-instance refresh lease**, because concurrent instances refreshing the same user race.

**CD-21 (P1).** Non-interactive execution. The mirror sync, catalogue sweeps, figure refreshes, replication and search indexing have no user. Each runs under a **declared service identity** with its own warehouse grants: BigQuery still enforces, on a principal whose grants are visible, audited under PM-7's governance class and reviewed under PM-11. The honest statement of the guarantee is "Frame does not implement the policy", not "Frame never holds entitled data".

**CD-22 (P1).** No credential replay. Frame never stores or replays a named human's credential for scheduled work. Storing a delegator's refresh token for offline use is precisely the confused-deputy surface this design exists to avoid.

## Cost governance

**CD-23 (P1).** Every warehouse query passes through a single wrapper that sets a maximum-bytes-billed ceiling derived from the relation's measured size tier, applies required partition filters where the catalogue declares a partition column, sets a job timeout, and labels the job for attribution. The wrapper emits a fixed, small set of query templates and nothing else, which is what makes CD-31 checkable rather than merely stated. A relation whose size exceeds the picker-eligibility threshold cannot be bound to a picker without a narrowed projection.

**CD-24 (P1).** Frame's project submits and is billed for warehouse queries; the user's own identity still decides what comes back. This is what makes ceilings, attribution and a circuit breaker possible at all — the alternative bills the user's home project and forfeits every control. Cost is attributed per workspace via query labels and reported. Per-workspace and platform ceilings degrade gracefully: on breach, live resolution falls back to stored snapshots with an explicit staleness state, and an ITG-operated circuit breaker can pause live resolution entirely while mirror-served data continues. Nothing in the estate has ever set a bytes-billed ceiling, a dry run or a query label, so this discipline is greenfield and is a first-class deliverable rather than a hardening task.

## Referential integrity

**CD-25 (P1).** A key ledger records which dimension keys are referenced by live Frame rows, maintained from the AU-8 event stream like any other consumer. Each sweep compares the ledger against the catalogue and reports keys that have been retired, superseded or removed upstream.

Affected rows keep their stored key and snapshot and render with a **staleness marker**; they are never silently rewritten and never blanked. Remediation is a steward action on an integrity panel, with a preview and a batched, audited write through the single write path (BP-4). Where the warehouse itself certifies a one-to-one supersession, an opt-in per-dimension auto-remap is available — opt-in because Frame writing to governed rows without a human approving the change is exactly the property CD-5 refuses by default.

**CD-26 (P2).** Drift reporting. The proportion of corporate-reference cells whose snapshot is stale, whose key is retired, or which were never resolved, reported per Blueprint and per workspace, with steward action rates. A governance feature nobody works is a governance feature that does not exist, and the bound-Sheets telemetry precedent (IN-9) shows we already know how to measure that honestly.

## Downstream channels

**CD-27 (P2).** Corporate data behaves consistently across every surface, from the stored snapshot rather than from a live read.

- **Search (PRD 13):** the label snapshot is indexed as ordinary row text; the mirror is not a search corpus and live-resolved labels are never indexed.
- **Replication (PRD 06):** the analytics replica carries the **key only**, never a copy of dimension data. The warehouse already holds the dimension and joining there is the natural act — replicating it would create a second staleness surface and a second entitlement question for no gain.
- **Documents (PRD 07):** merge fields render the stored snapshot, with staleness visible to the generator.
- **Import (IN-13):** imported values are validated against the dimension in batch, with unresolvable keys reported as ordinary exceptions rather than silently accepted.
- **Forms (PRD 03):** an external, unauthenticated form may expose a corporate reference **only** to an `open` dimension, per CD-9's fourth check.
- **AI (PRD 08):** an assist may propose a corporate reference value; it is a reviewable suggestion resolved through the same picker path, never a direct write.

## Transparency, audit and the descriptor

**CD-28 (P2).** A dimension with a declared hierarchy may be designated a **permission source**, materialising PM-2a principal allow-lists — which is how "the regional director sees this office and everything under it" is expressed without Frame maintaining its own copy of the org chart. Designation is an elevated right, is audited under PM-7's governance class, and carries a hard staleness bound: past it, the derived list **freezes and alerts rather than widening**. Warehouse unavailability therefore degrades to stale-but-stable access, never to broadened access.

**CD-29 (P2).** Frame publishes the resolved catalogue as a versioned, machine-readable descriptor. Two products in the estate have independently rebuilt weaker versions of this graph — one re-deriving edges by stripping key suffixes and matching table names at asserted high confidence with no ground truth, the other declaring key fields that are never populated — so publishing is how Frame's copy stops being a third private one. The descriptor mirrors the physical vocabulary of the estate's analytics tool where the concepts coincide, so a future adapter is mechanical.

**CD-30 (P1).** Transparency and audit. Corporate-data reads at or above the restricted threshold, source registration, classification changes, permission-source designation and quarantine events are audited under PM-7's access and governance classes. Frame does not duplicate BigQuery's own audit log; it records what Frame did and under which principal.

Live-resolved figures carry an explicit annotation — *computed under your own warehouse entitlements* — because PM-5's rule that aggregates compute over the full set and are annotated **cannot be honoured here**: BigQuery has already trimmed silently and will not report what it filtered. This is the one place in the product where the transparency principle genuinely cannot hold as written, and it is declared rather than discovered.

## Non-goals

**CD-31 (P1).** **Frame never aggregates.** A corporate figure reads a column that is already the number, on a relation that already has one row per grain key per period. Frame composes no `GROUP BY`, no join, no window function and no aggregation function, ever, on any path. If a number does not exist at a grain, that is a request to the data platform team for a mart, not a feature request for Frame — which is the correct home for it, since they own what "expenditure to date" means and Frame emphatically does not.

This is what makes vision N10 a mechanism rather than a comment, and it is CI-checkable: the CD-23 wrapper emits a fixed set of templates and nothing else.

Frame also writes nothing to the warehouse, offers no ad-hoc query surface, no group-by builder and no charting over warehouse data, and maintains no server-side aggregate store beside the analytics replica.

## Data model notes

Sources are code-first YAML seeded at build. The catalogue, mirror, probe results, key ledger and cost ledger live in Frame's Postgres as a dedicated schema — disposable, rebuildable, environment-local, holding no data older than its source, with access restricted to the sweep and resolution services. Bindings are ordinary Blueprint metadata in Firestore. Corporate-reference cell values are ordinary row fields carrying key, snapshot, snapshot timestamp and catalogue version.

## Dependencies

PRD 01 (BP-2 field types; BP-9a's shape for carried attributes; BP-12 versioning of bindings; BP-26 validation), PRD 05 (PM-4 composition, PM-2a allow-lists, PM-5 stubs and the declared exception, PM-7 audit classes, PM-9 service principals), PRD 02 (GR-4 pickers, GR-6 restricted rendering, GR-9 budgets), PRD 04 (AU-8 events for the key ledger and sweep changes), PRD 06 (replica carries keys only), PRD 09 (the connector pattern and token store), PRD 13 (snapshot indexing), the data platform team (curated views, grain, policies — a real dependency with a named owner, not an assumption).

## Open questions

1. Whether the mirror should hold every `open` dimension a source exposes, or only those actually bound by some Blueprint. Holding everything makes binding instant and costs storage and sync on data nobody uses; holding only what is bound makes the first binding slow. Proposal: sync on first binding, retain while bound, with a warm set for the most-used dimensions.
2. Sweep cadence, and whether it should be uniform or derived from each relation's declared volatility. Proposal: derived, with a floor, decided once real change rates are measured.
3. Whether an administrator's classification correction (CD-4) should expire and require re-confirmation, as the CD-9 attestation does. Corrections are narrow and cannot widen disclosure, but a wrong one persists silently. Proposal: annual re-confirmation, reported rather than enforced.
4. **Which** facts are bindable, which is a dependency on the data platform team rather than a product choice. CD-31 means Frame reads a measure that already exists as a column at a published grain; where a number a Blueprint author wants does not exist that way, the answer is a mart request, and the lead time on those is unknown. Proposal: inventory the measures the pilot registers actually ask for against what `Facts_Api` already publishes at grain, and treat any gap as a named backlog item with the data team rather than as a Frame requirement.
5. Capacity posture for the sweep and mirror sync — on-demand with per-job ceilings, or a reservation converting unbounded bytes into bounded slot-hours. Proposal: decide with ITG FinOps once the first sweep gives real query shapes.

## Decisions log

Resolved August 2026:

- **The catalogue is discovered, not registered.** A human authors only a Source. The registry-steward role and the turnaround target that an authored registry would have required are deleted, because they would have reproduced BP-17's governance-friction risk in a new place.
- **Two disclosure classes, not three.** A middle class that snapshots an entitled label and compiles an equivalent Frame rule at bind time has an undetectable drift failure mode; narrowed projections serve the practical middle ground instead.
- **The mirror exists because GR-9 is contractual**, and it applies only to data the warehouse has already declared unrestricted.
- **Frame's project pays**, because the alternative forfeits every cost control and excludes users without job-create rights of their own.
- **Separate field types**, rather than a flag on the existing reference type: overloading it would put a corporate-data branch inside every consumer of references, which is the rendering-layer analogue of the second implementation PM-4 forbids.
- **Facts remain in scope.** The relationship graph in the warehouse declares 2,780 fact-to-dimension edges, so grain — the thing that makes a figure bindable — is published upstream at scale rather than being something Frame would have to infer.
