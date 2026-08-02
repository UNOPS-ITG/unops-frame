import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import { walk, stripComments, pendingSubject } from './walk'

/**
 * The architectural fitness suite.
 *
 * These are the invariants the specification says are true. Left as prose they
 * decay: someone adds a second write path for imports, a permission check in
 * the client "just for the UI", a per-Blueprint router because that is how the
 * sibling repo does it — each individually reasonable, collectively fatal.
 * PM-4 says "no second implementation anywhere, including the client"; that is
 * either enforced by a machine in week one or it is aspirational by month nine.
 *
 * Every failure message states the REASON, not just the rule. An agent or an
 * engineer who understands why will comply; one who only sees a red test will
 * route around it.
 *
 * Checks whose subject does not exist yet report as skipped-with-a-reason
 * rather than passing silently.
 */

const SRC = 'src'
const BACKEND = 'functions'

describe('one permission evaluator (PM-4)', () => {
  it('the client contains no permission or validation logic', () => {
    const files = walk(SRC, ['.ts', '.tsx'])
    expect(files.length, 'no client source found — is SRC still "src"?').toBeGreaterThan(0)

    // Deliberately identifier-shaped rather than substring-shaped: "canReadMore"
    // in a pagination helper is fine, a function named canRead is not.
    const banned =
      /\b(canRead|canWrite|canEdit|canDelete|isAllowed|hasPermission|checkPermission|evaluateRule|validateField|trimRow|applyPermissions)\s*[=(:]/

    const offenders = files
      .filter((f) => banned.test(stripComments(f.text)))
      .map((f) => f.path)

    expect(
      offenders,
      'Permission and validation decisions belong to the server, on one path (PM-4, BP-4).\n' +
        'The client renders the trimmed row page and its rendering hints and decides nothing.\n' +
        'If the UI needs to know something, add it to the wire contract as a hint —\n' +
        'do not recompute the decision here, because the two will drift and the\n' +
        'divergence will be found by an auditor rather than by a test.\n' +
        'Offending files:',
    ).toEqual([])
  })

  it('only the permission library returns an allow/deny decision', () => {
    const permDir = `${BACKEND}/lib/permissions`
    if (!existsSync(BACKEND)) {
      console.warn(pendingSubject('single permission evaluator', BACKEND))
      return
    }

    const files = walk(BACKEND, ['.py']).filter(
      (f) => !f.path.startsWith(permDir) && !f.path.includes('/tests/'),
    )
    const offenders = files
      .filter((f) => /\bdef\s+(has_permission|can_|is_allowed|check_access)/.test(stripComments(f.text)))
      .map((f) => f.path)

    expect(
      offenders,
      `Only ${permDir} may decide access (PM-4). Everything else calls it and\n` +
        'consumes the Decision it returns. A second decision site is how the\n' +
        'estate ends up with two answers to the same question.\n' +
        'Offending files:',
    ).toEqual([])
  })
})

describe('one write path (BP-4)', () => {
  it('only the row writer touches row storage', () => {
    const writer = `${BACKEND}/lib/rows/writer.py`
    const systemWriter = `${BACKEND}/lib/rows/system_writer.py`
    if (!existsSync(BACKEND)) {
      console.warn(pendingSubject('single row writer', BACKEND))
      return
    }

    const files = walk(BACKEND, ['.py']).filter(
      (f) => f.path !== writer && f.path !== systemWriter && !f.path.includes('/tests/'),
    )
    // Firestore write verbs against a row collection.
    const writes = /\.(set|update|delete|create)\s*\(|batch\(\)|transaction\(\)/

    const offenders = files
      .filter((f) => /rows?_(collection|ref)|collection\(["']rows["']\)/.test(f.text))
      .filter((f) => writes.test(stripComments(f.text)))
      .map((f) => f.path)

    expect(
      offenders,
      `Every channel is a CALLER of ${writer}, never a peer (BP-4).\n` +
        'Grid edits, bulk paste, CSV import, the admin API, undo, and later forms,\n' +
        'automations, bound Sheets, MCP and inbound webhooks all go through it, so\n' +
        'validation, audit and the transactional outbox happen exactly once.\n' +
        'Two paths is the defect class that produces "it validates in the grid but\n' +
        'not on import" for the life of the product.\n' +
        `The one sanctioned exception is ${systemWriter}, for machine re-stamps\n` +
        'that emit no domain events and write one aggregate audit entry.\n' +
        'Offending files:',
    ).toEqual([])
  })
})

describe('the API is generated from metadata, not written per Blueprint', () => {
  it('no per-Blueprint or per-domain router file exists', () => {
    const routers = `${BACKEND}/api/routers`
    if (!existsSync(routers)) {
      console.warn(pendingSubject('metadata-generated API', routers))
      return
    }

    // The whole router surface is a small fixed set. Anything named after a
    // business noun means someone hand-wrote an endpoint for one Blueprint.
    const ALLOWED = new Set([
      'blueprints.py',
      'rows.py',
      'query.py',
      'views.py',
      'health.py',
      'docs.py',
      'admin.py',
      'corporate_data.py',
      '__init__.py',
    ])

    const offenders = walk(routers, ['.py'])
      .map((f) => f.path.split('/').pop() ?? '')
      .filter((name) => !ALLOWED.has(name))

    expect(
      offenders,
      'Frame generates its REST surface from compiled Blueprint metadata, so\n' +
        '`api/routers/` holds a small fixed set and never a file named after a\n' +
        'business noun. This is a deliberate, ADR-documented break from the\n' +
        'estate convention of one router per feature — and it IS the Frappe\n' +
        'claim. The moment one hand-written per-Blueprint router exists, "zero\n' +
        'per-Blueprint code" stops being demonstrable and the exit criterion dies.\n' +
        'If you need a genuinely new platform-level surface, add it to ALLOWED\n' +
        'here in the same change, so the decision is visible in review.\n' +
        'Unexpected router files:',
    ).toEqual([])
  })
})

describe('the event consumer cannot reach row storage (AU-8, SR-5)', () => {
  it('consumers read through the API, never the store', () => {
    const consumers = `${BACKEND}/consumers`
    if (!existsSync(consumers)) {
      console.warn(pendingSubject('event consumer isolation', consumers))
      return
    }

    const offenders = walk(consumers, ['.py'])
      .filter((f) => /firestore|from lib\.rows/.test(stripComments(f.text)))
      .map((f) => f.path)

    expect(
      offenders,
      'Event payloads carry identifiers and deltas, never row bodies (AU-8), and\n' +
        'consumers refetch through the public API under their own identity. A\n' +
        'consumer that reads the store directly bypasses PM-4 and turns the event\n' +
        'stream into a permission bypass with a subscription.\n' +
        'Offending files:',
    ).toEqual([])
  })
})
