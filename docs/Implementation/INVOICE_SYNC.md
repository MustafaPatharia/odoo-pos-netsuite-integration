# Invoice Sync - Odoo to NetSuite

## Overview

Syncs POS invoices to NetSuite with **payment method separation** and **split-payment handling**.

**Key Features:**
- Separate invoices for each payment method (Cash, Credit, etc.)
- Proportional splitting for orders with multiple payments
- Different customer entities per payment type
- Configurable consolidation (can be enabled/disabled)

**Sync Methods:**
- **Manual**: Trigger from Odoo UI anytime
- **Automatic**: Daily at 00:10 AM (scheduled mode only)

---

## Split-Payment Example

**Scenario**: Customer pays 60 AED cash + 40 AED credit card for 100 AED order

**Odoo Order:**
```
Products:
  - Product A: 10 qty @ 5 AED = 50 AED
  - Product B: 5 qty @ 10 AED = 50 AED
Payments:
  - Cash: 60 AED (60%)
  - Credit: 40 AED (40%)
```

**NetSuite Invoices:**

Cash Invoice (60%):
- Product A: 6.0 qty @ 5 AED = 30 AED
- Product B: 3.0 qty @ 10 AED = 30 AED
- **Total: 60 AED**

Credit Invoice (40%):
- Product A: 4.0 qty @ 5 AED = 20 AED
- Product B: 2.0 qty @ 10 AED = 20 AED
- **Total: 40 AED**

**Result**: Perfect reconciliation with no data loss.

---

## Manual Sync

**Steps:**
1. Go to **NetSuite → Operations → Sync Invoices**
2. Click **"Sync Invoices"**
3. System syncs yesterday's invoices by default

**Process:**
1. Validates all products have NetSuite IDs
2. Fetches unsynced invoices for target date
3. Calculates payment proportions (for split payments)
4. Groups by (warehouse, payment_method)
5. Aggregates line items proportionally
6. Creates NetSuite invoices
7. Updates Odoo with NetSuite IDs
8. Logs results

---

## Automatic Sync

**Schedule:** Daily at 00:10 AM
**Condition:** Only in `scheduled` integration mode
**Target:** Yesterday's invoices only

**Timing:**
```
00:05 → Orders sync
00:10 → Invoices sync (ensures orders created first)
```

---

## Grouping Logic

Invoices are grouped by:
1. **Warehouse** - Each shop separate
2. **Payment Method** - Each payment type separate
3. **Date** - Per day

**Result:** One invoice per (warehouse, payment_method, date) combination

**Example:**
```
Shop A on May 20:
  ├─ Cash Invoice → Customer: Cash Customer
  └─ Credit Invoice → Customer: Credit Customer
```

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
---

## NetSuite Invoice Fields

| Field | Value | Source |
|---|---|---|
| `entity` | Customer ID (1=Cash, 2=Credit, 3=Mobile) | Payment-specific |
| `subsidiary` | NetSuite subsidiary ID | Warehouse mapping |
| `department` | NetSuite department ID | Warehouse mapping |
| `location` | NetSuite location ID | Warehouse mapping |
| `tranDate` | Invoice date (YYYY-MM-DD) | Order date |
| `paymentMethod` | NetSuite payment method ID | Payment mapping |
| `memo` | "Invoice - [Shop] - [Date]" | Auto-generated |
| `custbody_odoo_invoice_ids` | Array of invoice IDs | Tracking |
| `custbody_odoo_invoice_count` | Count | Tracking |
| `custbody_payment_type` | Payment method ID | Tracking |
| `items[]` | Aggregated line items | Proportional calc |

**Line Item Calculation:**
```javascript
quantity = sum of (original_qty × proportion)
amount = sum of (original_amount × proportion)
rate = amount ÷ quantity
```

---

## Prerequisites

1. **Products with NetSuite IDs** - Sync products first or add manually
2. **Warehouse Mapping** - Configure subsidiary/department/location mappings
3. **Payment Method Mapping** (optional) - Maps Odoo → NetSuite payment methods

**Configure at:** NetSuite → Configurations

---

## Sync Status Tracking

**Fields on POS Order:**
- `x_netsuite_invoice_id` - NetSuite invoice ID
- `x_netsuite_invoice_sync_date` - Sync timestamp

**Separate from Order Sync:**
- Order sync: `netsuite_id`, `netsuite_tran_id` (Sales Order)
- Invoice sync: `x_netsuite_invoice_id` (Invoice)

Both can be tracked independently.

---

## Sync Logs

**View:** NetSuite → Sync → Logs
**Filter:** Record Type = `eod_invoice`

**Key Fields:**
- Status: success/failed/partial
- Response Code: HTTP status
- Execution Time: milliseconds
- Notes: Summary (shops synced, orders processed, failures)

---

## Troubleshooting

**Products missing NetSuite IDs:**
→ Sync products first or add IDs manually

**No subsidiary mapping:**
→ Configure warehouse mappings (NetSuite → Configurations)

**Invoice sync failed, order sync succeeded:**
→ Check invoice sync log, fix issue, retry manually

**Payment method not found:**
→ Add payment method mapping (NetSuite → Configurations)
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