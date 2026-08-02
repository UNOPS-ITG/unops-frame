-- Runs ONCE, on first initialisation of an empty volume. It does not re-run after
-- `docker compose restart db`, because the named volume survives — so anything that needs
-- to be re-applied belongs in functions/migrations/, not here.
--
-- Extensions and roles only. Application schema is a migration.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

-- The search projection (PRD 13) needs both of these: tsvector for full-text and pg_trgm
-- for the prefix and typo-tolerant matching SR-3 requires. Created now so the extension is
-- never the reason a migration fails.
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Schemas, so the three consumers never collide. Each is disposable and rebuildable:
-- Firestore is the system of record and nothing here is authoritative.
CREATE SCHEMA IF NOT EXISTS replica;   -- RP-7 analytics replica of organizational tiers
CREATE SCHEMA IF NOT EXISTS search;    -- SR-5 search projection
CREATE SCHEMA IF NOT EXISTS cdr;       -- PRD 14 corporate-data mirror and ledgers
