# Estate findings

Defects and deficiencies found in **other** applications in the UNOPS estate while building Frame.

None of this is Frame's code. It is recorded here because Frame is deliberately copying patterns from
these repositories, and each entry is either something Frame chose **not** to inherit or something the
owning team would probably want to know. Several are worth acting on independently of Frame.

**How to read this.** Severity is about impact on the owning application, not on Frame. "Verified"
means I read the code or ran the query myself; "reported" means it came from a subagent's read and I
have not personally confirmed it — treat those as leads rather than facts.

Living document: updated as the Frame build proceeds.

Last updated: 2 August 2026.

---

## ai-playbook

### Security

**P-1 · SQL injection in the BigQuery stored-procedure call · HIGH · verified**
`functions/fn_impl/case_management.py:2752-2765`. The `CALL` statement is built by string
concatenation, escaping only apostrophes:

```python
escaped_value = str(param_value).replace("'", "\\'")
param_parts.append(f"{param_name} => '{escaped_value}'")
query = f"CALL `{PROJECT_ID}.{BIGQUERY_DATASET}.{function_name}`({param_string})"
```

Backslashes are never escaped. GoogleSQL *does* honour `\'` inside a single-quoted literal, and that is
precisely the problem: a value ending in a backslash (`abc\`) emits `'abc\'`, where the closing quote is
consumed as an escape and the literal runs on into the rest of the query. With two parameters the first
string swallows `', param2 => '` and terminates on the quote before the second value, leaving
attacker-controlled text in raw SQL position. BigQuery supports multi-statement scripts, so the ceiling
is whatever the service account can do.

Values come from case field data (`case_data.get(field_id)`), so they are user-controlled. Reachable via
an authenticated endpoint at `functions/api/routers/cases.py:637`. `function_name` is validated against
the case-type config and `PROJECT_ID`/`BIGQUERY_DATASET` are environment config, so those are not the
vector.

*Fix:* use the client's parameter binding rather than better escaping —
`CALL \`…\`(name => @name)` with `ScalarQueryParameter`s. Allowlist parameter *names* against
`^[A-Za-z_][A-Za-z0-9_]*$`, since those still land in SQL text.
*Secondary:* line 2767 logs the fully-interpolated query including case field values.

**P-2 · IAP middleware fails open on an unset audience · HIGH · reported**
The middleware disables assertion validation with a log warning when `IAP_EXPECTED_AUDIENCE` is empty,
leaving authentication dependent on every endpoint remembering to declare a dependency. *Fix:* refuse
to start.

**P-3 · Rejected assertion echoed in the response body · HIGH · reported**
The 401 returns `{"detail": …, "jwt_payload": <the raw bearer token>}`. A bearer token in a response
body lands in devtools, proxy access logs and any error-reporting SDK the frontend has installed.

**P-4 · Dev auth bypass permits arbitrary impersonation · HIGH · reported**
`x-dev-auth-email` can name any address; there is no allowlist. A forged identity then appears in the
audit log indistinguishable from a real session. Compounded by P-5.

**P-5 · Bypassed requests are not distinguishable downstream · MEDIUM · reported**
The bypass sets `source="iap"` with a flag buried in claims rather than a distinct channel value, so an
audit record cannot tell a bypassed request from a real one.

**P-6 · No `email_verified` or hosted-domain check · MEDIUM · reported**
Locally the trust anchor is `accounts.google.com` with a public OAuth client id as the audience, so the
backend will accept an id_token minted for that client by *any* Google account. oauth2-proxy's
`email_domains` only protects traffic that goes through the proxy — and the agent-browser harness proves
people reach the backend port directly.

**P-7 · The auth-exempt path allowlist exists twice · MEDIUM · reported**
Two copies in two middleware modules. A security-relevant allowlist that exists twice will drift, and
the drift is invisible until an endpoint is unauthenticated.

**P-8 · `oauth2-proxy` `api_routes` is commented out · LOW · reported**
An unauthenticated XHR to `/api/*` gets a 302 to Google's sign-in page instead of a 401, so the SPA sees
an opaque cross-origin failure rather than "you are logged out".

### Correctness

**P-9 · JWKS cache `Expires` parsed as local time · MEDIUM · reported**
`time.mktime(strptime(…, "%Z"))` reads a GMT timestamp as local time, so on any non-UTC machine the key
cache expires hours early or late. *Fix:* `email.utils.parsedate_to_datetime` plus `calendar.timegm`.

**P-10 · No JWKS refresh on key rotation · MEDIUM · reported**
A `kid` miss against a still-valid cache is not treated as a rotation signal, so key rotation causes an
outage until the TTL expires.

**P-11 · Paginator silently truncates for permission-trimmed users · HIGH · reported**
`nextCursor` is derived from `len(page) < page_size`. Under permission trimming a short page means "this
page was trimmed", not "this is the last page", so result sets end early for precisely the users whose
access is most restricted — the hardest failure to notice in testing.

**P-12 · Pagination tiebreaker encoded but never used · MEDIUM · reported**
The cursor encodes a doc-id tiebreaker and then calls `start_after({'sort_field': sort_val})` without
it, so the tiebreaker the same code mandates two sections earlier never applies. Equal sort values cause
page drift.

**P-13 · One OpenAPI schema memoised for the process lifetime · LOW · reported**
Memoising onto `app.openapi_schema` freezes the first schema observed, which is wrong for anything
version-dependent.

**P-14 · `cloudrun.py` does not export `FIREBASE_STORAGE_EMULATOR_HOST` · LOW · reported**
The setting is declared but never round-tripped into `os.environ`, so the storage client silently talks
to the cloud while everything else is emulated.

### Architecture and maintenance

**P-15 · 403 auditing scrapes the resource type out of the URL · MEDIUM · reported**
Denial auditing hangs off the global exception handler and identifies the resource with per-noun regexes
(`/cases/`, `/dossiers/`). It is both coupled to every new noun and routable-around by raising a
different exception class. Auditing belongs at the decision point, where the ids are already structured.

**P-16 · Hand-maintained callable-to-REST map plus duplicated types · MEDIUM · verified**
`src/services/callable-to-rest.mapping.ts` (340 lines) and a re-declared `src/types/` tree mirror the
backend's pydantic schemas by hand, guarded by a build-time check. A real OpenAPI document is already
served at `/api/openapi.json`; generating the client would delete both.

**P-17 · Mixed `camelCase`/`snake_case` Firestore field naming · LOW · reported**
The stated convention is camelCase; `last_accessed`, `created_at` and others are not.

**P-18 · `agent-os` docs describe a stack that was replaced · LOW · verified**
`agent-os/product/tech-stack.md` and `README.md` say Angular 19; the code is React 19. Angular remnants
also survive in `scripts/patch-angular-config.mjs` and `.cursor/rules/angular-templates-scss.mdc`.

**P-19 · Ruff runs with `continue-on-error: true` · LOW · verified**
The lint baseline is not clean, so the CI signal is advisory.

---

## unops-prism

**PR-1 · Foreign-key metadata is declared but never populated · HIGH · reported**
`internal/models/types.go` defines `IsPrimaryKey`, `IsForeignKey` and `ForeignKeyRef`. Grepping the
repository, they are only ever *read* (`autodetect.go:51,63,79,80,156`) and never assigned;
`flattenBQSchema` does not set them. Two of the three auto-join detection rules are therefore dead
against BigQuery, and the third requires a target column literally named `id`, which UNOPS warehouse
tables do not have. **Prism's automatic join detection returns effectively nothing against
`unops-datahub`.**

The information it is trying to infer is already published: `unops-datahub.Metadata_Api.Datahub_Table_Reference`
declares ~3,600 edges with cardinality, join semantics and a human-readable relationship verb.

**PR-2 · No data-level entitlement model, despite the spec describing one · HIGH · reported**
`internal/auth/middleware.go` builds a `UserInfo` whose `Role` is hardcoded to `"viewer"` on both the
dev and production paths, and no handler ever reads it. No Firestore document type carries the ACL field
the architecture document describes. `firestore.rules` is the 163-byte default template. The frontend
route guards check a hardcoded `currentUser.role = 'admin'` in `stores/app.ts`.

**PR-3 · The planned result cache is entitlement-blind · HIGH · reported**
The Phase-1.5 Parquet cache is keyed on `query hash + connection ID + parameter hash`
(`prism-analytics-architecture.md:1433`) — no user, group or entitlement component. Combined with PR-4
this would be a cross-user shared cache over data with no access model. Worth resolving before that
cache is built rather than after.

**PR-4 · BigQuery is queried as a single service identity · MEDIUM · reported**
`internal/bigquery/client.go` uses ADC only; `auth.UserFromContext` is never passed to the BigQuery
layer. Deliberate per the architecture document, but it means row-level and column-level policies in the
warehouse have no effect on what Prism returns.

**PR-5 · Metadata import/export are 501 stubs · MEDIUM · reported**
`api/datagraph_handlers.go:430-441`. No other system can consume Prism's model, and Prism cannot import
one — including the published catalogue in `Metadata_Api` that would fix PR-1.

**PR-6 · Governed dimension CRUD is unreachable · LOW · reported**
`datagraph/service.go` implements `ListDimensions`/`CreateDimension`; `RegisterDataGraphRoutes` never
mounts them.

**PR-7 · Dead views and stale mocks · LOW · reported**
`SemanticView.vue` and `ModelMetadataView.vue` are unrouted (`/semantic` redirects to `/data`).
`mock/worksheets.json` still uses the superseded `connectionId` + flat `shelves` shape.

---

## ai-bob

**B-1 · No OAuth revocation path anywhere · HIGH · reported**
`POST /v1/connectors/{id}/disable` is explicit that it "does NOT revoke OAuth token" — it flips a
Firestore flag and the encrypted refresh token remains indefinitely. Nothing calls
`oauth2.googleapis.com/revoke`, and nothing handles a user revoking access from their Google account
(which would surface as an unhandled `invalid_grant`). This is a compliance question rather than a
nicety once tokens are used to act as the user.

**B-2 · Access-token refresh has no cache · MEDIUM · reported**
`token_store.py:129-146` performs a KMS decrypt and a full OAuth round-trip on *every* call. Acceptable
for occasional Drive metadata; unacceptable on any query path. The Atlassian branch in the same file
already implements the right pattern (per-user lock, double-checked cache, expiry skew, `invalid_grant`
guard that refuses to overwrite the store) — the Google branch has none of it.

**B-3 · Cross-instance token refresh race · MEDIUM · reported**
Acknowledged in a code comment: "two Cloud Run instances refreshing the same user concurrently can still
race. Closing that needs a Firestore lease." The lease was never built.

**B-4 · Foreign keys re-derived by heuristic at asserted high confidence · MEDIUM · reported**
`bigquery_heuristics.py:37-140` strips `_id`/`_key`/`_code` suffixes and matches table names, emitting
`{"derivedBy": "fkColumnNameMatchesTable", "confidence": "high"}` with no ground truth. This is a
strictly weaker re-derivation of `Metadata_Api.Datahub_Table_Reference`, which declares the same edges
plus relationship path, join semantics and enablement state.

**B-5 · Entity identity is guessed rather than read · MEDIUM · reported**
`entity_resolution.py:675-681` picks an id column by looking for a name ending in `_id`;
`_query_dimension_row` brute-forces candidate id columns, running one query per candidate until one
returns a row. Display name is guessed by substring match on `name`/`title`/`description`.
`Datahub_Table.Business_Key` and `Datahub_Table_Column.Business_Key_Flag` declare both upstream — 398
flagged columns in `Dimensions_Api` alone.

**B-6 · Row cap without a bytes cap · MEDIUM · reported**
`bigquery_config.py` enforces `maxQueryRows: 10_000` as a SQL `LIMIT`. That bounds the result set and
does nothing about a full-table scan, which is what actually costs money.

**B-7 · Documented DWD credential with no call site · LOW · reported**
`SA_WORKSPACE_DWD_EMAIL` is wired and documented as "Flow 4" but never used. Either finish it or remove
it; an unused domain-wide-delegation credential is a standing risk with no benefit.

**B-8 · Points at base datasets while the rest of the estate points at `_Api` · LOW · verified**
`seed_bigquery_config.py` configures `unops-datahub.Dimensions` and `.Facts`; every platform integration
YAML in `unops-procurement`, `hr-partner-portal` and `unops-talent` uses `Dimensions_Api` / `Facts_Api`.
The `_Api` layer is where table descriptions and metadata coverage live.

---

## unops-toolbelt

**T-1 · Row filtering by query parameter rather than caller identity · MEDIUM · reported**
`functions/main.py:927` calls `CALL \`…user_tasks\`(@email)`, passing the caller's email as a parameter.
This is the estate's only example of filtering BigQuery by the caller — and it is filtering by a value
the caller's client supplies rather than by the identity the warehouse sees. Real row-level access
policies would make the filter unforgeable.

**T-2 · Production code path points at a personal project · LOW · reported**
Default `BQ_USER_TASKS_PROC` is `unops-dev-tushard.unopstoolbelt.user_tasks`.

---

## unops-external-dataservice

**E-1 · Schema discovered by executing the query · LOW · reported**
`Services/DataSource/BigQuerySourceService.cs:92-123` obtains a schema with
`SELECT * FROM (<user query>) LIMIT 0` and reads the field list. It gets name, type and mode only — no
descriptions, no keys, no policy tags — where `INFORMATION_SCHEMA` and `Metadata_Api` carry all of it.

---

## unops-datahub (the warehouse catalogue)

Not an application, but a system Frame now depends on, and the metadata below is consumed by
`ai-bob`, Prism, `unops-external-dataservice` and Frame.

**W-1 · `Column_Type = MEASURE` marks identifier columns · MEDIUM · verified**
`Metadata_Api.Datahub_Data_Dictionary` declares a `Column_Type` of `DIMENSION` or `MEASURE` per
column, and it is the only machine-readable statement of a column's role — so every consumer that
wants "the numbers on this fact" reads it. On `Facts_Api.Asset_Transactions` it marks both `Period`
(INT64, an accounting period identifier) and `Voucher_No` (INT64, a document number) as `MEASURE`,
alongside genuine amounts like `Amount` and `Asset_Depreciation_Amount`.

`MEASURE` is evidently being used to mean "numeric", not "additive". Any consumer that offers every
`MEASURE` column as something to sum will produce a total of period numbers and a total of voucher
numbers, and both look like money in a chart. `Period` is additionally a *grain* column — it appears
as a dimension key on the same table's relationships — so it is simultaneously declared a measure and
used as a key.

Verified by reading the dictionary rows for that table directly. Frame is only lightly exposed
because it never aggregates — it would display a period number where a figure was expected, which is
visibly odd rather than silently wrong — but a BI tool consuming the same field will not be.

Worth raising with the data team as either a definition fix (`MEASURE` should mean additive) or an
additional column (`Additive_Flag`), since the ambiguity cannot be resolved downstream: no consumer
can tell `Voucher_No` from `Amount` by type alone.

**W-2 · Four of eight `Metadata_Api` views are undocumented in the estate · LOW · verified**
Every consumer found in the estate filters `WHERE Dataset_Name = 'Dimensions_Api'`, so
`Datahub_Table_Reference`'s 2,780 `Fact → Dimension` edges and 849 `Dimension → Dimension` edges are
present, maintained, and unused. Two separate teams (`ai-bob`, Prism) built weaker relationship
inference instead — one by stripping `_id` suffixes and matching names, the other by declaring
foreign-key fields that are never populated. This is a discoverability problem rather than a defect,
but the cost of it is two private, worse copies of a graph that already exists.

---

## Estate-wide

**X-1 · No BigQuery cost controls in any repository · HIGH · verified**
Grepping every repo for `maximum_bytes_billed`, `dry_run`, query labels and job timeouts returns
nothing. Six services query BigQuery. BigQuery bills by bytes scanned, so a single unbounded query is
unbounded spend, and there is currently no per-application attribution to even notice it. Frame is
building this apparatus (PRD 14, CD-23/CD-24) and the pattern should probably be lifted estate-wide.

**X-2 · The published metadata catalogue has one consumer, and it only asked about dimensions · HIGH · verified**
`unops-datahub.Metadata_Api` carries eight views — table and column descriptions, declared business keys,
per-column DIMENSION/MEASURE classification, security policy tags, named data stewards for eight
business domains, and a declared relationship graph. It is read by exactly one script in the estate
(`unops-procurement/specs/full-v1-initial/extract-bq-schema.py`, a one-off extraction dated 2026-05-24),
and every query in it filters `WHERE Dataset_Name = 'Dimensions_Api'`.

Nobody had checked whether it covers facts. I queried it directly: it does, and comprehensively —
**2,780 `Fact → Dimension` edges** alongside 849 `Dimension → Dimension`. Two products (see PR-1, B-4)
have independently built weaker inference to reconstruct a graph that is already published.

**X-3 · No OAuth revocation anywhere · HIGH · reported**
See B-1. Worth stating as an estate-level gap rather than one product's, because every product that
stores a refresh token has it.

**X-4 · Secrets travel between repositories by copy · MEDIUM · verified**
`scripts/agent-browser/.env.local`, carrying a live Playbook `DEV_AUTH_BYPASS_SECRET` and a real staff
address, was found in the Frame repository — copied along with the tooling, into a directory with no
`.gitignore` and no git history yet. Deleted before Frame's first commit; **the secret should be rotated
in Playbook**, since it has been outside its home repository for an unknown period. Worth checking
whether the same file travelled anywhere else.

---

## Suggested triage order

1. **P-1** (SQL injection) — user-controlled input reaching a `CALL` statement.
2. **X-4** (rotate the leaked bypass secret) — cheap, and the exposure window is unknown.
3. **P-3, P-4** (token echoed in a response; arbitrary impersonation) — both small fixes.
4. **P-2, P-6** (auth fails open; no domain check) — both change a default from permissive to closed.
5. **X-1** (BigQuery cost controls) — no incident yet, but there is no mechanism to notice one.
6. **PR-2, PR-3** (Prism's entitlement model) — best resolved before the cache is built, not after.
7. **P-11** (paginator truncates for trimmed users) — silent wrong answers, hardest class to notice.
