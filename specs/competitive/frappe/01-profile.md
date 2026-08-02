# Frappe Framework — product profile

> Analysis date: 2026-08-02 · Analyst: Claude session for tushard@unops.org
> Sources fetched this session:
> - https://frappe.io/framework (fetched 2026-08-02, marketing page)
> - https://docs.frappe.io/framework/user/en/basics/doctypes (fetched 2026-08-02)
> - https://docs.frappe.io/framework/user/en/basics/users-and-permissions (fetched 2026-08-02)
> - https://docs.frappe.io/framework/user/en/api/rest (fetched 2026-08-02)
> - https://github.com/frappe/frappe/releases (fetched 2026-08-02 — latest page only, not full history)
> - https://frappe.io/cloud/pricing (fetched 2026-08-02, via redirect chain frappecloud.com → cloud.frappe.io → frappe.io/cloud/pricing)
> - Cloned repo: `github.com/frappe/frappe` @ `43666ea` (committed 2026-08-02 — HEAD of default branch, v16-era code), shallow clone in session scratchpad
> - WebSearch: discuss.frappe.io permission threads (result snippets; individual threads not fetched)
> Shelf life: pricing/changelog claims stale after ~1 quarter. Code citations pinned to commit `43666ea`.
>
> Evidence-quality notes, honestly: (1) the docs index at docs.frappe.io returned HTTP 520 on first fetch and a near-empty nav on retry, so doc coverage is from four deep pages plus the codebase, which is the stronger source anyway. (2) Review-site coverage (G2/StackShare/Reddit) is thin to nonexistent for Frappe-as-framework — StackShare lists no pros/cons at all — so "what users complain about" evidence comes from the project's own forum (discuss.frappe.io), which skews toward ERPNext operators. (3) Changelog trajectory is from the latest releases page only.

## Summary

Frappe Technologies Pvt. Ltd. (Mumbai; bootstrapped, publishes its P&L openly; framework started 2005). Frappe Framework is an MIT-licensed, full-stack, metadata-driven web framework in Python + JavaScript, best known as the substrate under ERPNext. Target market is developers building "complex business solutions"; GTM is open-source-led with a managed-hosting monetization layer (Frappe Cloud). It is explicitly *not* aimed at end users: the product is a framework whose flagship claim is that declaring a DocType (a metadata document) yields the database table, form view, list view, REST API, permissions and workflow without writing them.

## Positioning statement (extracted, not invented)

For developers who build database-driven business applications, Frappe Framework is a "full stack, batteries-included" web framework that generates the model, views, API and permissions from DocType metadata. Unlike conventional MVC frameworks (their comparison targets are Django-class frameworks), Frappe treats metadata as the application. Source: https://frappe.io/framework.

## Claimed USP (verbatim quotes)

- "Meet Framework. It's full stack, batteries-included, and written in Python and JS." — https://frappe.io/framework [marketing]
- "A DocType is the basic building block of the application and represents a database table, a form, a class and so on" — https://frappe.io/framework [marketing]
- "97.42% development effort is thus eliminated" (Zerodha CTO testimonial) — https://frappe.io/framework [marketing]
- "Framework is not for the light hearted" — https://frappe.io/framework [marketing]
- "Frappe framework generates REST API for all of your DocTypes out of the box." — https://docs.frappe.io/framework/user/en/api/rest [verified in code, see below]

## Feature inventory

All `frappe/...` paths are in the cloned repo at commit `43666ea` (2026-08-02).

| Area | Feature | Evidence | Source |
|---|---|---|---|
| Metadata model | DocType defines table + form + class; 80 declarable properties per field (type, reqd, unique, permlevel, depends_on, fetch_from, mandatory_depends_on, read_only_depends_on, min/max, virtual, mask, …) | [verified] counted 80 fields in the DocField metaschema | `frappe/core/doctype/docfield/docfield.json`; docs/basics/doctypes |
| Metadata model | Child tables: child rows belong to one parent via parent/parenttype/parentfield; permissions delegate wholly to parent | [verified] `has_child_permission()` resolves the parent and re-runs the check there | `frappe/permissions.py:806-900` |
| Metadata model | Single, Virtual, Tree DocTypes; custom DocTypes creatable from UI without code (standard ones require developer mode + generate controller files) | [verified] `"Not in Developer Mode! Set in site_config.json or make 'Custom' DocType."`; custom skips file/controller generation | `frappe/core/doctype/doctype/doctype.py:334-336, 534, 714-722` |
| "Zero per-DocType code" | The framework itself ships ~312 DocType folders with ~320 hand-written Python controller files; generated CRUD is codeless, *behavior* is not | [verified] counts from clone; controllers hook validate/on_update etc. | `frappe/*/doctype/*/` (find count, this session) |
| REST API | Generic v2 routes: `/api/v2/document/<doctype>` CRUD, list with filters, count, meta, bulk update/delete (async over a threshold, 202 + job id), doc-method execution, RPC `/method/<path>`, discovery endpoints | [verified] one generic rule table, no per-DocType routes | `frappe/api/v2.py:602-649` |
| REST API | Per-DocType query customization via controller static `get_list(query)` and whitelisted controller methods | [verified] documented in-code | `frappe/api/v2.py:118-183` |
| REST API | Auth: token (api_key:secret), session, OAuth bearer | [verified docs] | docs/api/rest |
| Permissions | Role permissions over 14 rights (select, read, write, create, delete, submit, cancel, amend, print, email, report, import, export, share) + custom per-DocType permission types | [verified] | `frappe/permissions.py:13-28`, `get_doctype_ptype_map` |
| Permissions | Field bands via integer `permlevel` per field, role access per level | [verified] | `frappe/permissions.py:314-315, 872-885`; docs |
| Permissions | User Permissions: per-user equality allow-lists on Link field values, `apply_strict_user_permissions` toggle, tree descendants | [verified] | `frappe/permissions.py:351-478` |
| Permissions | `if_owner` rules; owner fallback when user permissions deny | [verified] | `frappe/permissions.py:254-273` |
| Permissions | Per-document sharing (DocShare) as an OR-path around role perms | [verified] | `frappe/permissions.py:177-209`, `frappe/share.py` |
| Permissions | Programmatic ABAC only via hooks: `has_permission` (deny-only, per doc) and `permission_query_conditions` (returns raw SQL / pypika for list queries) — two separate implementations to keep in sync | [verified] | `frappe/permissions.py:481-498`; `frappe/model/db_query.py:1332-1360` |
| Permissions | Permission debug: per-check log of why access was denied (`debug=True` trace) | [verified] | `frappe/permissions.py:43-77` |
| Workflow | Declarative Workflow per DocType: states (with docstatus mapping, update_field/update_value), role-gated transitions, Python `safe_eval` conditions, transition tasks (Webhook / Server Script / app hook methods, sync or async), self-approval block, bulk actions to 500, background submission queue | [verified] | `frappe/model/workflow.py` (whole file) |
| Lifecycle | docstatus draft/submitted/cancelled with submit/cancel/amend rights baked into the model | [verified] | `frappe/model/workflow.py:205-226`, rights list |
| Versioning | Version DocType stores field-level diffs (changed/added/removed/row_changed incl. child rows), impersonator/audit-user attribution, HTML diffs for long text | [verified] | `frappe/core/doctype/version/version.py` |
| Customization | Upgrade-surviving overlay: Property Setter (per-property override on DocType/DocField), Custom Field, Custom DocPerm, Customize Form; permission-relevant property changes are permission-logged | [verified] | `frappe/custom/doctype/property_setter/property_setter.py`; `frappe/custom/doctype/customize_form/customize_form.py` |
| Scripting | Server Script DocType: user-authored Python in a restricted `safe_exec` runtime, disabled unless enabled in site config; can also implement API endpoints and permission query conditions | [verified] | `frappe/core/doctype/server_script/server_script.py:13-18, 290`; `frappe/model/db_query.py:1353-1358` |
| Realtime | Separate Node socket.io process; room subscription authorized by calling back into the app (`/api/method/frappe.realtime.has_permission`) — socket tier holds no permission logic | [verified] | `realtime/handlers.js:12-70` |
| Storage | Four database backends: MariaDB, Postgres, SQLite, DuckDB | [verified] | `frappe/database/{mariadb,postgres,sqlite,duckdb}/` |
| UI | Desk: metadata-driven form/list/kanban/calendar/tree views, "without writing any code" | [marketing] homepage claim; consistent with boot/desk code but UI depth not exercised this session | https://frappe.io/framework |
| Platform | Background jobs, rate limiter, email, print formats, web forms, global search | [verified — modules exist in clone] | `frappe/{email,printing,search,rate_limiter.py}` |

## Pricing & packaging

The framework is MIT-licensed and free. What is sold is managed hosting (Frappe Cloud):

| Tier | Price (billing basis) | Gating |
|---|---|---|
| Framework (self-host) | $0 (MIT) | Everything; you run bench, workers, socketio yourself |
| Frappe Cloud — Sites | from $5/month (monthly; annual not shown on page) | Shared multi-tenant hosting, UI deployments, backups, monitoring |
| Frappe Cloud — Servers | from $40/month (monthly) | Dedicated/shared VMs; enterprise features (granular access control, audit logs, alerts) |

Note: the pricing page shows monthly figures; no "contact us" enterprise tier was visible on the fetched page.

## Trajectory (from releases page, latest page only, fetched 2026-08-02)

- v16 is the current major track (v16.29.0, 28 Jul 2026); v15 still receives parallel maintenance (v15.116.x same week) — long dual-track support.
- Security hardening: one-time sign-in codes, permission/access-rule fixes, unsafe-HTML filtering (multiple releases, Jun–Jul 2026).
- Reporting/data: report snapshots, error-log summaries, batch loading of linked records, export improvements (v16.27–16.29).
- Mobile/UX polish: mobile print menu, touch support, form scrolling (v16.26–16.28).
- Frappe Cloud integration: Cloud Settings surface inside the framework (v16.29) — the open-source core is growing attachment points for the commercial host.
- Web Forms: private links (v16.28) — continued investment in the external-form edge.

## User-pain signal (forum, via search snippets)

- "The design of User Permissions is dangerous" — discuss.frappe.io/t/109103: a mis-created User Permission left an employee able to see all salary slips org-wide; the fail-open shape (no applicable user permission = unrestricted within role) recurs as a complaint. [verified as a reported incident, not reproduced]
- v16 select-permission regression thread (discuss.frappe.io/t/159712) and multiple "insufficient permission for User Permission" administration threads (2017–2026): permission administration is a persistent operator pain point. [verified as reports]
