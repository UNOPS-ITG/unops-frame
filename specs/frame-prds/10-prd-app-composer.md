# PRD 10: App Composer

## Purpose

The payoff of the Blueprint model: compose views, forms, dashboards, and pages into role-scoped applications with navigation and branding, no code. The floor under Grant+ style products: domain apps become configuration over governed Blueprints rather than projects.

## Scope

In: app definition, page types, navigation, audience scoping, branding, publishing, app-level analytics. Out: new data capabilities (apps compose existing surfaces only; if a capability is missing, it is built in its home PRD, never as an app special case). Out in v1: external unauthenticated apps beyond forms and status pages (P3 decision point).

## Functional requirements

**AC-1 (P3).** An app is a versioned configuration document: name, icon, brand theme, audience bindings, navigation tree, and pages. Apps live in a workspace, may reference organizational Blueprints, and publish to a stable URL under the Frame domain.

**AC-2 (P3).** Page types: view page (a saved view, optionally locked to its configuration), form page, dashboard page, record page (master-detail form for a Blueprint, reachable from view pages), and content page (rich text/markdown for guidance). Pages accept URL parameters for record routing.

**AC-3 (P3).** Audiences: named roles within the app (requester, reviewer, manager) bound to users/groups; navigation and pages scope per audience. Audience scoping composes with, and never overrides, PRD 05 evaluation: an app can narrow what an audience sees, never widen it. The composer surfaces effective-access preview per audience ("view as reviewer") so builders see the composed result before publishing.

**AC-4 (P3).** Publishing: draft and published versions, change preview, one-click rollback, and an app directory for discovery within the org (with the same attribution model: apps credit their builders).

**AC-5 (P3).** App analytics for builders: page views, form conversion, active users per audience, surfaced in a builder dashboard (privacy-reviewed metric set, no individual browsing surveillance).

**AC-6 (P3).** Templates: an app template gallery seeded with the patterns we know we need (intake and triage, register and review, portfolio room), instantiating apps bound to catalog Blueprints.

## Dependencies

Everything: PRDs 01 through 09 supply the composable surfaces. The composer ships last for exactly that reason, and its scope stays thin by design; the moment the composer needs its own data or logic capabilities, that pressure routes back to the platform PRDs.

## Open questions

1. External authenticated apps (partner logins beyond magic links): identity architecture decision with the PPP experience as prior art; deliberately deferred.
2. Whether apps can embed Playbook conversational surfaces as a page type; attractive for domain apps, sequenced after MCP maturity.
3. Custom domains per app (grants.unops.org style): estate DNS and certificate policy conversation, not a product blocker.
