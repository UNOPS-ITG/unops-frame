"""Scheduled jobs.

Distinct from `consumers/` on purpose, and the distinction is a security one
rather than a filing convenience.

An **event consumer** reacts to a domain event about a row. It must refetch
through the public API under its own identity, because a consumer that read row
storage directly would bypass the single permission evaluator and turn the event
stream into a permission bypass with a subscription. A fitness test enforces
that, with no exception list — an exception list on a rule of that shape is how
the rule erodes.

A **job** here runs on a schedule against configuration and metadata, not
against rows. The corporate-data sweep reads a registered Source and writes a
catalogue of table names; there is no per-row decision available to bypass. It
touches the store directly and that is correct.

If a job ever needs to read or write rows, it calls `lib.rows.writer` like every
other channel — it does not become a second write path by virtue of being
scheduled.
"""
