# GCP provisioning required

Everything Frame needs provisioned on Google Cloud, and what is blocked until each item exists.

**Nothing in this list has been done.** Frame has touched no GCP resource: the only cloud access used
so far is read-only BigQuery queries against `unops-datahub` with the repo owner's ADC, which was
explicitly sanctioned. Every item below needs a decision or an action from someone with the rights to
take it.

Ordered by what unblocks the most. Each item says what it is, why Frame needs it, and — where
relevant — **what is already built and waiting**, so nothing has to be rediscovered.

Living document: updated as the build proceeds.

Last updated: 2 August 2026.

---

## 1 · A Frame GCP project

**What.** One project Frame owns, for the API, Firestore, Pub/Sub and — separately — corporate-data
query billing.

**Why.** Everything else hangs off it. Frame currently runs entirely against emulators; there is no
deployed anything.

**Waiting on it.** Deployment of any kind. All local development continues without it.

**Note.** The repo owner said this arrives "later in the week" as of the initial planning
conversation. Nothing is blocked *locally* by its absence.

---

## 2 · The corporate-data billing project and budget

**What.** A project that submits BigQuery jobs, plus a budget and alert on it.

**Why.** BigQuery bills the **submitting** project, not the one holding the data. That is what makes
a Frame-owned ceiling both possible and necessary: Frame pays for every corporate-data query its
users run, so an unbounded scan is Frame's bill.

**Config.** `CORPORATE_BILLING_PROJECT`. Currently set locally to `unops-ai-playbook-dev` (the gcloud
default) so the sweep could be run and verified; that is a development stand-in and must not be the
deployed value.

**Grants needed.** `roles/bigquery.jobUser` on this project, for:
- every Frame user who will read corporate data (they need to *run* a job; their own IAM still
  governs what data they can read), and
- the sweep's service account.

**Already built and waiting.** Per-job `maximumBytesBilled`, a job timeout, and per-workspace query
labels are set on every job Frame submits — none of which appear anywhere else in the estate. A
budget will therefore have per-workspace attribution from day one rather than one unattributable
line.

**Measured, so the budget can be set from a real number.** One full catalogue sweep of
`unops-datahub` reads ≈5.3 MB of metadata (15,703 dictionary rows, 962 tables, 3,629 edges) plus
≈40 MB for the disclosure probe, which is dominated by `INFORMATION_SCHEMA`'s 10 MB minimum billing
per query. Call it **≈45 MB per sweep**. At a daily sweep that is under 1.5 GB a month before any
user query.

---

## 3 · The BigQuery OAuth client  ← *blocks the connector end-to-end*

**What.** A Google OAuth 2.0 **Web application** client, with:
- authorised redirect URI: `https://<frame-host>/api/v1/corporate/connection/callback`
- the `https://www.googleapis.com/auth/bigquery.readonly` scope available to it
- the consent screen configured as **Internal** to the UNOPS Workspace org

**Why.** Corporate data is read in each user's own context, so Frame holds a per-person OAuth grant
and BigQuery's IAM is the enforcement point. Frame implements none of it.

**Config.** `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, optionally
`CORPORATE_OAUTH_REDIRECT_URI` (left empty derives it from the request origin, which is correct for
both local and deployed).

**Read-only, deliberately.** Frame never writes to the warehouse. Requesting `bigquery` rather than
`bigquery.readonly` would put a consent screen in front of every user saying Frame may modify their
data — untrue, and the kind of over-ask that makes people decline the whole connector.

**Already built and waiting.** The whole connector: scope-delta incremental consent, the state check
bound to the authenticated subject, envelope-encrypted token storage keyed on the stable subject, a
per-principal access-token cache, `invalid_grant` handling that never overwrites the store, and a
disconnect that revokes at Google before deleting locally. `GET /api/v1/corporate/connection`
reports `connected: false` today and will report the truth the moment a client exists.

**Until then.** No user can connect, so no `entitled` relation can be read at runtime. The catalogue
and the classifier work regardless; they read metadata, not data.

---

## 4 · A Cloud KMS key for refresh tokens  ← *blocks any non-local deployment of the connector*

**What.** A KMS key ring and key, plus a dedicated service account with
`roles/cloudkms.cryptoKeyEncrypterDecrypter` on it that the API impersonates.

**Why.** A refresh token is a long-lived credential that reads corporate data as its owner. Encrypted
before it reaches Firestore, it survives an export, a backup, or a mis-scoped read of the collection
as ciphertext. The dedicated principal means "can decrypt a user's token" is a grant that can be
reviewed and revoked on its own, rather than implied by running the API.

**Config.** `CORPORATE_KMS_KEY`, `CORPORATE_KMS_SERVICE_ACCOUNT`.

**Already built and waiting.** `build_cipher` refuses to start without a key unless the process is
both `ENVIRONMENT=local` and has no `K_SERVICE` — three gates, any one of which fails closed, the
same shape as the dev auth bypass. Locally it uses a `LocalDevCipher` that is honestly named,
base64 only, logs a warning, and marks every value `local-dev:v1:` so a deployed process refuses it
rather than failing in a way that looks like corruption.

---

## 5 · The floor principal  ← *blocks the entire `open` fast path*

**What.** A service account that is a member of **exactly** the all-staff group
(`g.reporting.allpersonnel@unops.org`) and nothing else — no project-level BigQuery roles, no
dataset grants, no Fine-Grained Reader on any policy tag taxonomy.

**Why.** This is check 3 of the disclosure probe, and it is the one that cannot be worked around.

The question the probe has to answer is "can *everyone* see this?", and a privileged account
structurally cannot answer it. Verified rather than assumed: reading a policy-tagged column
(`Dimensions.Bank.Bank_Account_IBAN`) with the repo owner's credentials succeeds **both** through the
published `Dimensions_Api` view and directly against the base table. That tells us the account is
privileged; it says nothing about what an ordinary staff member sees. Only a principal holding
exactly the floor's grants can distinguish "everyone may read this" from "you may read this".

**Grants needed.** Membership of the all-staff group, `roles/bigquery.jobUser` on the billing
project, and nothing else. Its value comes entirely from what it does *not* have, so any additional
grant silently destroys it — this is worth stating in whatever provisions it.

**Waiting on it.** All 555 swept dimensions are classified `entitled`. That is the correct and safe
outcome — `classify` treats an unperformed check as a failure, because an unanswered audience
question is not a negative answer — but it means:
- no dimension is mirrored, so every lookup is a live per-user warehouse query;
- the `open` fast path exists and is completely untested against real data;
- the measured premise that ~96% of dimension columns are `Level 0` cannot be converted into actual
  performance.

It is now visible rather than theoretical. With the read path resolving references, a
`corporate_reference` column on a real dimension renders as PM-5 restricted stubs for anyone without
a BigQuery consent, and as a live per-user query for anyone with one. Nothing renders from a
snapshot, because no dimension is allowed to have one.

**Already built and waiting.** `Probe.floor_principal_sees_all_rows` and the comparison logic in
`classify`. The probe reports it as unperformed with a reason naming exactly this gap, and that
reason is visible on every relation through `GET /workspaces/{ws}/corporate/dimensions` and on the
corporate-data page in the browser.

**How the snapshot path is exercised meanwhile.** `npm run seed` writes one `open` dimension,
`Demo_Api.Agency`, beside whatever the sweep found, and points the demo register's `agency` field at
it. It is labelled as a development fixture in the catalogue's own
`classification_reasons`, so nobody can mistake it for a probe result. It exists because the
snapshot, staleness and orphan treatments would otherwise never render anywhere — and an
untested rendering path is one that is wrong the first time it matters.

---

## 6 · Read access to `INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`

**What.** Whatever grant makes
`unops-datahub.Dimensions.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES` readable — likely
`roles/bigquery.metadataViewer` or a `rowAccessPolicies.list` permission on the base datasets.

**Why.** Check 2a. Row access policies are the mechanism that makes a table's *rows* vary by reader,
and Frame must not cache a slice of a table that does.

**Current state.** The view reports `Not found: Table ... was not found in location EU` on both
`Dimensions` and `Facts` — which is indistinguishable from "there are none", and only one of those is
safe to act on. Recorded as a failed check.

**Waiting on it.** Nothing beyond item 5, since check 3 already forces `entitled` on everything. But
both must be resolved before anything can be classified `open`.

**Already built and waiting.** `BigQueryInspector.row_access_policy_count` returns `None` on failure
rather than `0`, and the probe records it as an error. The moment the grant exists it starts
returning real counts with no code change.

---

## 7 · The sweep's service account

**What.** A service account for the scheduled catalogue sweep, with
`roles/bigquery.jobUser` on the billing project and read access to `unops-datahub`'s `Metadata_Api`
and the base `Dimensions` / `Facts` datasets (for the probe's policy-tag check).

**Why.** The catalogue is Frame's own record and every workspace shares it. Sweeping it as whoever
happened to open a page would make its contents depend on that person's entitlements — wrong, and
unstable.

**Waiting on it.** Nothing locally: the sweep currently runs on ADC, which is why it works today.
Deployment needs it.

**Already built and waiting.** `jobs/sweep_corporate_catalogue.py` resolves its identity through
`google.auth.default`, so it picks up a service account with no code change. Every read it makes is
already labelled `surface=catalogue-sweep` and bounded by the Source's ceiling.

---

## 8 · Cloud Scheduler for the sweep

**What.** A scheduled trigger — daily is the working assumption — invoking the sweep per workspace.

**Why.** An always-current catalogue is the whole premise of "discovered, not authored". Without a
schedule the catalogue is whatever it was when someone last ran the job by hand.

**Already built and waiting.** The job is idempotent, compares against the previous catalogue, and
reports what was quarantined and restored. A failed run leaves the previous catalogue untouched
rather than emptying it — a sweep that emptied on failure would quarantine every relation at once and
present as a mass retirement, which is the most alarming possible symptom of a network error.

---

## 9 · Firestore, deployed

**What.** A Firestore database named **`frame`** (not `(default)`), created with **CMEK** encryption
and **PITR** enabled **at creation time** — neither can be turned on afterwards.

**Why.** The named database is not optional: a client built without it reads an empty store and
reports success. CMEK and PITR are creation-time-only, so getting this wrong means recreating the
database and migrating.

**Already built and waiting.** `lib/firestore.py` passes the database name explicitly in both
constructors and documents why. `firestore.rules` denies everything, permanently and deliberately —
every read and write goes through the API and the permission library.

---

## 10 · Sign-in: IAP deployed, oauth2-proxy locally

**What.** Two things sharing one mechanism:

- **Deployed** — Identity-Aware Proxy in front of the API, and the audience value it issues.
- **Locally** — oauth2-proxy on port 6302, issuing an equivalent assertion, which needs a **second**
  Google OAuth client (a *Desktop* or *Web* client for sign-in, distinct from the BigQuery connector
  client in item 3) with `http://localhost:6302/oauth2/callback` as a redirect URI.

**Config.** `IAP_AUDIENCE` — there is no default, and the service **refuses to start** without one,
because an empty audience would disable assertion validation entirely.

**Current state — oauth2-proxy is NOT set up.** Port 6302 is reserved in `config/ports.json` and
`scripts/start-oauth-proxy.mjs` exists, but the binary is not downloaded, `oauth2-proxy.cfg.yaml` and
`oauth2-proxy.cfg.template` do not exist, and nothing in `package.json` or `docker-compose.yml`
starts it.

**Nothing is blocked by that locally**, and that is by design rather than by luck: the dev auth
bypass exists precisely so local work does not depend on an interactive Google consent screen. It is
gated by three independent conditions (a configured secret, `ENVIRONMENT=local`, and `K_SERVICE`
absent) and impersonates only allow-listed addresses, so it cannot follow the code to a deployment.

**What it would buy.** Exercising the real assertion path locally — `IapAssertionMiddleware`, the
hosted-domain check, JWKS rotation — rather than trusting that it works because its unit tests pass.
Worth doing before the first deployment; not worth doing to make local development function.

**Already built and waiting.** `IapAssertionMiddleware`, which fixes six defects found in the
estate's equivalents (fail-closed audience, clock leeway, never echoing the token, `email_verified`
and hosted-domain checks, UTC expiry parsing, JWKS refresh on key rotation).

---

## Not required, and deliberately so

**A BigQuery allowlist or Workspace-admin scope grant.** Corporate data uses a per-user OAuth
connector with individual consent, following the `ai-bob` pattern. Adding BigQuery is a client
configuration, not an org ticket.

**Domain-wide delegation.** Never. Frame reads as the signed-in user with their consent, or as a
declared service identity whose grants are visible and reviewable. Delegation would make Frame able
to read as anyone, which is exactly the property this design refuses.

**A service account with broad warehouse access used for user queries.** The one shortcut that would
make the `open` path work today without item 5. It is refused: it would make Frame the enforcement
point for data whose policy Frame does not implement, and the connector explicitly declines to fall
back to a service identity when a user's consent is missing.

---

## Summary

| # | Item | Blocks |
| --- | --- | --- |
| 1 | Frame GCP project | any deployment |
| 2 | Billing project + budget | deployed corporate-data queries |
| 3 | OAuth client | the connector, end to end |
| 4 | KMS key + decrypt SA | deployed connector |
| 5 | **Floor principal** | **the entire `open` fast path** |
| 6 | `ROW_ACCESS_POLICIES` read | classifying anything `open` |
| 7 | Sweep service account | deployed sweep |
| 8 | Cloud Scheduler | an always-current catalogue |
| 9 | Firestore `frame` (CMEK + PITR at creation) | deployed persistence |
| 10 | IAP audience (deployed) / oauth2-proxy client (local) | the deployed API starting at all; locally, exercising the real sign-in path |

Items 5 and 6 are the pair that matter most for the product's shape: until both exist, corporate data
works but every lookup is an `entitled` live query, and the performance premise the design rests on
is untested.
