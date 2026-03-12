# ADR-007: Dispensary Filter Slug Normalisation

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-12 |
| **Author** | Acidni Platform |
| **Affects** | `container_app/stock_routes.py` |
| **Severity** | Critical — broke all multi-word dispensary filtering |

## Context

The Stock Browse API (`/api/stock/browse`) and 8 other filter endpoints
compare a user-supplied `?dispensary=` query parameter against the
`dispensary` field stored in stock index items.

Index items use two fields:

- `dispensary` — the internal slug (e.g. `green_dragon`)
- `dispensary_name` — the human-readable name (e.g. `Green Dragon`)

All filter sites used the pattern:

```python
filtered = [i for i in filtered if i.get("dispensary", "").lower() == dispensary.lower()]
```

The Teams app (and other API callers) pass the **display name** as the
parameter value — e.g. `?dispensary=Green Dragon`.

**For single-word dispensaries** this worked by accident:
`"cookies".lower() == "cookies"` ✅

**For multi-word dispensaries** it failed:
`"green_dragon" != "green dragon"` (underscore vs space) ❌

### Impact

- **Green Dragon**: 1,252 items invisible to filtered queries. 426 items
  with valid price data could not be fetched for the Store Display.
- **Sanctuary Medicinals**: Same bug, different dispensary.
- Any future dispensary with spaces in the name would also be broken.

## Decision

Add two helper functions to normalise dispensary matching:

1. **`_matches_dispensary(item, dispensary_input)`** — checks the item's
   `dispensary` field (slug) and `dispensary_name` field against the input,
   normalising spaces to underscores for slug comparison.

2. **`_resolve_dispensary_key(by_dispensary, dispensary_input)`** — resolves
   a user-supplied dispensary identifier to the correct dict key in the
   `by_dispensary` index dict.

Replace all 9 hard-coded `.lower() == dispensary.lower()` comparisons
with calls to these helpers.

## Consequences

### Positive

- All dispensaries are now filterable regardless of name format
- API callers can pass either slugs (`green_dragon`) or display names
  (`Green Dragon`) — both work
- No frontend changes required
- Single point of normalisation logic

### Negative

- Marginal overhead per comparison (two extra string operations)
- None material for the data volumes involved

## Affected Endpoints

| Endpoint | Line(s) | Type |
|----------|---------|------|
| `GET /api/stock/strains` | ~214 | List filter |
| `GET /api/stock/search` | ~318 | Search filter |
| `GET /api/stock/browse` | ~416 | Browse filter |
| `GET /api/stock/hot-products` | ~813 | Hot products filter |
| `GET /api/stock/new-arrivals` | ~853 | New arrivals filter |
| `GET /api/stock/recently-sold-out` | ~893 | Sold out filter |
| `GET /api/stock/availability-history/{slug}` | ~935 | History filter |
| `GET /api/stock/{dispensary}` | ~1302 | Dict lookup |
| `GET /api/stock/{dispensary}/{batch_id}` | ~1332 | Dict lookup |
