# EOD Invoice Sync - Odoo to NetSuite

## Overview

The End-of-Day (EOD) Invoice Sync feature consolidates POS invoices and creates **separate invoices per payment method per shop per day** in NetSuite.

**Key Features:**
- **Payment Method Separation** - Cash and Credit invoices are separate
- **Split-Payment Handling** - Orders with multiple payments are divided proportionally
- **Customer Entity Mapping** - Different customers for Cash vs Credit
- **Mode-Based Consolidation** - Real-time mode disables consolidation

**Sync Methods:**
- **Manual Sync** - Sync invoices for a specific date on-demand
- **Automatic Sync** - Runs daily at midnight (00:10)

---

## 🔄 Split-Payment Handling

### The Problem

**Scenario:** A customer buys 100 AED of items but has only 60 AED cash, so pays 40 AED by credit card.

**Challenge:** How to create separate Cash and Credit invoices in NetSuite without losing data?

### The Solution

**Proportional Splitting** - Each invoice gets its proportional share of line items.

**Example:**

**Odoo POS Order:**
```
Order #100: Total 100 AED
  Products:
    - Product A: 10 qty @ 5 AED = 50 AED
    - Product B: 5 qty @ 10 AED = 50 AED

  Payments:
    - Cash: 60 AED (60%)
    - Credit Card: 40 AED (40%)
```

**NetSuite Invoices Created:**

**Cash Invoice (Customer: Cash Customer):**
```
- Product A: 6.0 qty @ 5 AED = 30 AED  (60% of 10 qty)
- Product B: 3.0 qty @ 10 AED = 30 AED  (60% of 5 qty)
Total: 60 AED ✓
```

**Credit Card Invoice (Customer: Credit Customer):**
```
- Product A: 4.0 qty @ 5 AED = 20 AED  (40% of 10 qty)
- Product B: 2.0 qty @ 10 AED = 20 AED  (40% of 5 qty)
Total: 40 AED ✓
```

**Result:** No data loss, perfect reconciliation! 🎉

---

## Manual EOD Invoice Sync

### How to Trigger Manual Sync

1. Navigate to: **NetSuite → Operations → Sync Invoices**

2. Click the **"Sync Invoices"** button

3. Odoo will:
   - Find all paid/invoiced orders for yesterday (default)
   - Group by shop
   - Create one consolidated Invoice per shop
   - Display results notification

### What Happens During Sync

1. **Validate** all products have NetSuite IDs
2. **Fetch** all invoices for target date with status: `paid`, `done`, or `invoiced`
3. **Calculate** payment proportions for each invoice (handles split payments)
4. **Group** invoices by **(warehouse, payment_method)** combination
5. **Aggregate** line items proportionally by product
6. **Create** ONE Invoice in NetSuite per **(warehouse, payment_method)** group
7. **Update** Odoo invoices with NetSuite invoice ID
8. **Log** sync results

**Example:**
```
Shop: Main Store
Date: 2026-05-16
Orders: 8 POS orders (5 cash-only, 2 card-only, 1 split payment)

Result: 2 Invoices Created
  - Cash Invoice (INV-001): 150.00 AED
  - Card Invoice (INV-002): 280.45 AED
```

---

## Automatic Daily Sync

### Configuration

The daily sync runs automatically at midnight, shortly after order sync.

**Schedule:** Daily at 00:10 AM
**Cron Job Name:** `NetSuite: Sync EOD Invoices`
**Mode:** Syncs only yesterday's invoices

### Sync Sequence

```
00:05 → Order Sync runs (creates Sales Orders)
        ↓
00:10 → Invoice Sync runs (creates Invoices)
```

**Why separate timing?**
- Ensures Sales Orders are created first
- Maintains proper NetSuite workflow
- 5-minute buffer for order sync completion

### How It Works

1. **Trigger:** Runs at 00:10 every day
2. **Target Date:** Yesterday (previous day)
3. **Action:** Creates consolidated Invoices for yesterday only
4. **Condition:** Only runs if `config_integration_mode == 'scheduled'`

---

## Consolidated Invoice Structure

### Grouping Logic

**Invoices are grouped by:**
1. **Warehouse/Shop** - Each shop gets separate invoices
2. **Payment Method** - Each payment method gets a separate invoice
3. **Date** - Invoices are created per day

**Result:** One invoice per **(warehouse, payment_method, date)** combination

**Example:**
```
Shop A on May 20:
  - Cash Invoice → Customer: Cash Customer
  - Credit Card Invoice → Customer: Credit Customer
```

### Split-Payment Handling

**When a single order has multiple payment methods** (e.g., 60 AED cash + 40 AED card):
- Order is **split proportionally** across payment invoices
- Cash invoice gets 60% of line items
- Card invoice gets 40% of line items
- No data loss - all payments tracked correctly

### NetSuite Invoice Fields

| Field | Value | Description |
|---|---|---|
| `recordType` | `invoice` | Record type |
| `entity` | Payment-specific customer | Cash Customer / Credit Customer (based on payment method) |
| `subsidiary` | From warehouse mapping | NetSuite subsidiary |
| `department` | From warehouse mapping | NetSuite department |
| `location` | From warehouse mapping | NetSuite location |
| `tranDate` | Invoice date | Date of the orders (YYYY-MM-DD) |
| `paymentMethod` | NetSuite payment method ID | Payment method reference |
| `memo` | "Consolidated Invoice - [Shop] - [Date]" | Description |
| `custbody_odoo_invoice_ids` | Array of invoice IDs | Tracking field |
| `custbody_odoo_invoice_count` | Number of invoices | Count |
| `custbody_payment_type` | Payment method ID | Payment type tracking |
| `items[]` | Aggregated line items | Product details (proportional for split payments) |

### Line Item Aggregation

Products are aggregated across all invoice portions for each payment method.

**For split-payment orders**, quantities and amounts are calculated proportionally.

**Example - Simple Aggregation (no split payments):**
```json
{
  "items": [
    {"item": "1009", "quantity": 5, "rate": 11.36, "amount": 56.80},
    {"item": "1005", "quantity": 3, "rate": 7.53, "amount": 22.59}
  ]
}
```

**Example - With Split Payment:**
```
Order: 100 AED (60 AED cash + 40 AED card)
  - Product A: 10 qty @ 10 AED = 100 AED

Cash Invoice (60%):
  - Product A: 6.0 qty @ 10 AED = 60 AED

Card Invoice (40%):
  - Product A: 4.0 qty @ 10 AED = 40 AED
```

### Customer Entity Mapping

**Different payment methods use different NetSuite customer entities:**

| Payment Method | NetSuite Customer Entity |
|----------------|-------------------------|
| Cash | Customer ID 1 (Cash Customer) |
| Credit Card | Customer ID 2 (Credit Customer) |
| Mobile/Other | Customer ID 3 (Mobile Customer) |

**Why?** Client requirement - reconciliation reports need to distinguish between cash and credit transactions.

**Configurable:** Customer mapping can be configured in `netsuite_config` (future enhancement).

---

## Prerequisites

### 1. Products Must Have NetSuite IDs

Same requirement as Order Sync - all products need NetSuite IDs.

**Error if missing:**
```
Cannot sync invoices: 1 product(s) missing NetSuite IDs:

   • Corner Desk Left Sit (FURN_1118)

Please add NetSuite ID manually:
Inventory → Products → Edit → Set 'NetSuite ID' field
```

### 2. Warehouse Subsidiary Mapping

Same as Order Sync - warehouses must be mapped.

### 3. Payment Method Mapping

Payment methods should be mapped to NetSuite payment method IDs.

**Configure at:** NetSuite → Configurations → Payment Method Mapping
*(Optional - if not mapped, payment method name is used)*

---

## Invoice Status Tracking

### Odoo POS Order Fields

| Field | Description | Values |
|---|---|---|
| `x_netsuite_invoice_id` | NetSuite Invoice ID | e.g., "36063" |
| `x_netsuite_invoice_sync_date` | Timestamp of invoice sync | DateTime |

**Note:** Invoice sync updates different fields than Order sync to track both separately.

### Dual Tracking

Each POS order tracks both:
- **Sales Order** → `netsuite_id`, `netsuite_tran_id`
- **Invoice** → `x_netsuite_invoice_id`, `x_netsuite_invoice_sync_date`

```
POS Order
    ↓
Order Sync → netsuite_id = "31943", netsuite_tran_id = "SO-578238"
    ↓
Invoice Sync → x_netsuite_invoice_id = "36063"
```

---

## Sync Logs

All invoice sync operations are logged separately from order sync.

### Viewing Sync Logs

Navigate to: **NetSuite → Sync → Logs**

Filter by:
- **Record Type:** EOD Invoice
- **Status:** Success / Failed / Partial
- **Date:** Today / This Week / Custom Range

### Log Details

Each log entry contains:
- **Reference:** Sync timestamp with "(+00:00)" timezone
- **Record Type:** `eod_invoice`
- **Status:** `success`, `failed`, or `partial`
- **Request URL:** NetSuite invoice creation endpoint
- **Request Method:** `POST`
- **Response Code:** HTTP status (200 = success)
- **Execution Time:** Milliseconds
- **Response Payload:** Full sync results including invoice IDs
- **Notes:** Summary (e.g., "Shops: 2/3, Orders: 18, Failed: 1")

---

## Integration Mode Behavior

**The consolidation logic depends on the integration mode:**

| Mode | Consolidation | Behavior |
|------|---------------|----------|
| **Real-time** | ❌ Disabled | 1:1 order to invoice mapping (no consolidation) |
| **Scheduled** | ✅ Enabled | Consolidated invoices (grouped by warehouse + payment + date) |
| **Manual** | ✅ Enabled | Consolidated invoices (grouped by warehouse + payment + date) |

**Why?** Client requirement - real-time mode for immediate sync, scheduled/manual for batch processing.

## Differences from Order Sync

| Aspect | Order Sync | Invoice Sync |
|---|---|---|
| **NetSuite Record** | Sales Order | Invoice |
| **Grouping** | By shop + date | By shop + payment + date |
| **Customer Entity** | Default customer | Payment-specific customer |
| **Includes Payments** | No | Yes (via customer + payment method field) |
| **Split Payments** | First payment only | Proportional splitting |
| **Cron Time** | 00:05 | 00:10 |
| **Sync Mode** | All unsynced dates (manual) | Specific date only |
| **Fields Updated** | `netsuite_id`, `netsuite_tran_id` | `netsuite_id`, `netsuite_tran_id`, `netsuite_sync_status` |
| **Record Type Log** | `eod_order` | `eod_invoice` |

---

## Troubleshooting

### Error: "Products missing NetSuite IDs"

**Same solution as Order Sync:**
1. Add NetSuite IDs to products manually
2. Or sync products from NetSuite first

### Error: "No NetSuite subsidiary mapping found"

**Same solution as Order Sync:**
1. Configure subsidiary mappings for warehouses

### Invoice Sync Failed but Order Sync Succeeded

**Cause:** Invoice sync runs separately - can fail independently.

**Solution:**
1. Check invoice sync log for specific error
2. Fix the issue (e.g., payment method mapping)
3. Retry invoice sync manually
4. Order sync data is preserved

### Payment Method Not Found

**Cause:** Payment method mapping missing in NetSuite.

**Solution:**
1. Go to: NetSuite → Configurations → Payment Method Mapping
2. Create mapping for Odoo payment method → NetSuite payment method
3. Or use generic payment method ID
4. Retry sync

---

## Best Practices

### 1. Sync After Order Sync

Always ensure Order Sync completes before Invoice Sync:
- Manual: Run Order Sync first, then Invoice Sync
- Automatic: Cron handles sequencing (00:05 then 00:10)

### 2. Payment Method Mapping

- Map all POS payment methods before go-live
- Test payment aggregation with sample data
- Verify NetSuite payment method IDs are correct

### 3. Daily Reconciliation

- Review invoice sync logs daily
- Compare NetSuite invoice totals with POS reports
- Ensure payment breakdowns match

### 4. Testing Workflow

**Test sequence:**
1. Create test POS orders with payments
2. Run Order Sync manually → verify Sales Orders created
3. Run Invoice Sync manually → verify Invoices created
4. Check NetSuite for both records
5. Verify payment breakdown matches

---

## Summary

**Complete financial picture** - Invoices with payment breakdowns
**Matches Order Sync pattern** - One invoice per shop per day
**Payment reconciliation** - Aggregated by payment method
**Automatic daily sync** - Runs after order sync
**Full audit trail** - Every invoice logged with details
**Production-ready** - Comprehensive error handling and validation
---

**Last Updated:** May 17, 2026
**Version:** 1.0