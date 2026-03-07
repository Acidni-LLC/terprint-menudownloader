# ADR-006: Persistent Stock Ledger — Cosmos DB Event Log

## Status

**Accepted**

## Date

2026-03-07

## Context

The Terprint Stock API tracks cannabis product availability across Florida dispensaries. The existing `StockAvailabilityTracker` writes diff events (appeared, disappeared, restocked) to blob storage with two limitations:

1. **90-day retention window** — events older than 90 days are purged
2. **50-event cap per item** — only the most recent 50 events are kept per stock item

These limitations prevent long-term historical queries such as:
- "When was Blue Dream last in stock at Trulieve Tampa?"
- "How often does MUV restock Wedding Cake?"
- "Show me all price changes for Gorilla Glue #4 over the past year"
- "What's the average time a strain stays in stock?"

Users and downstream systems (AI chat, analytics) need access to **complete, permanent stock history** for trend analysis, availability predictions, and compliance audits.

## Decision

Implement a **Persistent Stock Ledger** in Azure Cosmos DB that writes immutable event documents for every stock change.

### Key Design Choices

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Data store** | Azure Cosmos DB (serverless) | Low cost at rest, scales automatically, existing auth via Managed Identity |
| **Container** | `stock-ledger` in `TerprintAI` database | Co-located with other Terprint data, partition isolation |
| **Partition key** | `/strain_slug` | Queries typically filter by strain — keeps hot queries efficient |
| **Write timing** | After `StockAvailabilityTracker.update()` | Non-blocking, failure is logged but doesn't fail the index build |
| **Document ID** | SHA-256 hash of `{event}:{item_key}:{timestamp}` | Deterministic, prevents accidental duplicates |
| **Retention** | Permanent (no TTL) | The ledger is the long-term source of truth |

### Event Document Schema

```json
{
    "id": "abc123...",
    "type": "stock_event",
    "event": "appeared | disappeared | restocked",
    "timestamp": "2026-03-07T14:30:00Z",
    "strain_slug": "blue-dream",
    "strain": "Blue Dream",
    "dispensary": "trulieve",
    "dispensary_name": "Trulieve",
    "store_id": "TL-0123",
    "store_name": "Trulieve Tampa",
    "product_name": "Blue Dream TruFlower 3.5g",
    "category": "flower",
    "batch_id": "OMMU-2026-123456",
    "price": 35.00,
    "weight_grams": 3.5,
    "thc_percent": 22.5,
    "terpene_total_percent": 2.1,
    "top_terpenes": ["myrcene", "pinene", "limonene"],
    "build_id": "idx-20260307-1430",
    "item_key": "trulieve:TL-0123:blue-dream:flower"
}
```

### API Endpoints

| Route | Purpose |
|-------|---------|
| `GET /api/stock/ledger/strain/{slug}` | Full event history for a strain |
| `GET /api/stock/ledger/strain/{slug}/timeline` | Condensed in-stock/out-of-stock periods |
| `GET /api/stock/ledger/store/{store_id}` | All events at a specific store |
| `GET /api/stock/ledger/recent` | Recent events with filters |
| `GET /api/stock/ledger/stats` | Aggregate ledger statistics |

## Consequences

### Positive

- **Complete history** — no data loss after 90 days or 50 events
- **Efficient queries** — partition key on `strain_slug` optimizes common access patterns
- **Decoupled** — ledger writes are non-fatal; index build succeeds even if Cosmos is unavailable
- **Auditable** — immutable event log can be used for compliance and forensics
- **AI-ready** — chat and recommendation systems can query "when was X last in stock"

### Negative

- **Additional cost** — Cosmos serverless has per-request pricing (mitigated by low write volume ~3 builds/day)
- **Eventual consistency** — ledger may lag a few seconds behind the live index
- **Storage growth** — ledger grows indefinitely (acceptable — Cosmos scales horizontally)

### Risks Mitigated

| Risk | Mitigation |
|------|------------|
| Cosmos unavailable | Write failure is logged and skipped — index build continues |
| Duplicate events | Deterministic document ID prevents accidental duplicates |
| Query cost | Partition key on strain_slug keeps cross-partition queries rare |

## Implementation

1. **Code**: `StockLedgerWriter` class in `container_app/stock_indexer.py`
2. **Integration**: Called after `tracker.update()` in `save_index()`
3. **Routes**: Added to `container_app/stock_routes.py`
4. **Dependency**: `azure-cosmos>=4.5.0` in `requirements.txt`
5. **Container**: Created via Azure CLI:
   ```bash
   az cosmosdb sql container create \
     --account-name cosmos-terprint-dev \
     --database-name TerprintAI \
     --name stock-ledger \
     --partition-key-path /strain_slug \
     --resource-group rg-dev-terprint-shared
   ```

## Related

- [CMDB: stock/product.yaml](../../../products/stock/product.yaml) — updated with `stock-ledger` container
- [StockAvailabilityTracker](../../container_app/stock_indexer.py) — existing 90-day blob tracker
- [Stock API Routes](../../container_app/stock_routes.py) — ledger endpoints
