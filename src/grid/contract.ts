/**
 * The wire contract, as the client sees it.
 *
 * Mirrors `functions/api/schemas/rows.py`. Kept as plain types rather than a
 * generated client because the shape is small, fixed, and the same for every
 * Blueprint — the *values* map is what varies, and no generator can type that
 * without a build step, which is exactly what Frame's "publish takes effect
 * immediately" claim rules out.
 *
 * Nothing here decides anything. The server has already evaluated every
 * permission and trimmed the page; these types describe what arrived. A
 * restricted value is a value the client renders, not a condition it evaluates.
 */

/**
 * The typed stub standing in for a field the viewer may not read.
 *
 * Never an absent key and never a type default — a zero where a number was
 * withheld is a lie that then gets summed. Because the key is always present,
 * no renderer branches on key existence.
 */
export interface RestrictedValue {
  readonly restricted: true
}

/**
 * `undefined` is a real case, not a laxity: a row that has never been given a
 * value for a field has no key for it, and that is different from a value of
 * `null` (explicitly cleared) and from a restricted stub (present, withheld).
 * Collapsing the three is how "not recorded" comes to read as "zero".
 */
export type FieldValue =
  | RestrictedValue
  | string
  | number
  | boolean
  | null
  | undefined
  | readonly unknown[]

export function isRestricted(value: unknown): value is RestrictedValue {
  return typeof value === 'object' && value !== null && (value as RestrictedValue).restricted === true
}

export interface Row {
  readonly id: string
  readonly values: Readonly<Record<string, FieldValue>>
  readonly fieldVersions: Readonly<Record<string, number>>
  readonly lifecycleStatus: string
  readonly updatedAt?: string | null
  readonly updatedBy?: string | null
}

/**
 * PM-5 transparency, machine-readable.
 *
 * `certainty` is the discriminator that lets a windowed count stay honest: an
 * exact view-level total means evaluating every row in the filtered set, which
 * collides with the 50,000-row windowed requirement.
 */
export interface Annotation {
  readonly visible: number
  readonly withheld: number
  readonly total: number
  readonly scope: string
  readonly certainty: 'exact' | 'estimated'
  readonly ceiling: number | null
}

export interface PagePlan {
  readonly storeFilters: number
  readonly postFiltered: boolean
  readonly scanned: number
  readonly rounds: number
  readonly scanBudgetExhausted: boolean
  readonly reasons: readonly string[]
  readonly unsortable: string | null
}

export interface RowPage {
  readonly rows: readonly Row[]
  readonly annotation: Annotation
  readonly cursor: string | null
  readonly hasMore: boolean
  /** Fields withheld on EVERY row of the page — rendered as a restricted
   * column rather than a grid of restricted cells. */
  readonly columnStubs: readonly string[]
  readonly plan: PagePlan
  readonly blueprintId: string
  readonly blueprintVersion: number
}

export interface BlueprintField {
  readonly id: string
  readonly label: string
  readonly type: string
  readonly variant: string | null
  readonly storage: string
  readonly required: boolean
  readonly readOnly: boolean
  readonly setOnce: boolean
  readonly sensitivity: number
  readonly restricted: boolean
  readonly indexed: boolean
  /** Whether the STORE can order by it — not whether the type is orderable.
   * Slots are finite, and a client that assumes otherwise renders a sort
   * control that silently does nothing. */
  readonly sortable: boolean
  readonly filterable: boolean
  readonly options: readonly { key: string; label: string }[] | null
  readonly default: unknown
  readonly helpText: string | null
}

export interface Blueprint {
  readonly id: string
  readonly name: string
  readonly version: number
  readonly tier: string
  readonly fields: readonly BlueprintField[]
  readonly titleField: string | null
  readonly searchableFields: readonly string[]
  readonly slotPressure: Readonly<Record<string, string>>
  readonly unassignableSorts: readonly string[]
}

export interface Delta {
  readonly kind: 'upsert' | 'remove'
  readonly rowId: string
  readonly changedFields: readonly string[]
}
