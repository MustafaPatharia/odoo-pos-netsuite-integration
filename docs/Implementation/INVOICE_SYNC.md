# EOD Invoice Sync - Odoo to NetSuite

## Overview

The End-of-Day (EOD) Invoice Sync feature consolidates all POS orders from each shop for each day and creates **ONE Invoice per shop per day** in NetSuite. This matches the consolidated Sales Order pattern and provides complete financial reconciliation.

**Sync Methods:**
- **Manual Sync** - Sync invoices for a specific date on-demand
- **Automatic Sync** - Runs daily at midnight (00:10)

---

## Manual EOD Invoice Sync

### How to Trigger Manual Sync

1. Navigate to: **NetSuite → Operations → EOD Invoice Summary**

2. Click the **"EOD Invoice Summary"** button

3. Odoo will:
   - Find all paid/invoiced orders for yesterday (default)
   - Group by shop
   - Create one consolidated Invoice per shop
   - Display results notification

### What Happens During Sync

1. **Validate** all products have NetSuite IDs
2. **Fetch** all orders for target date with status: `paid`, `done`, or `invoiced`
3. **Group** orders by warehouse (shop)
4. **Aggregate** line items by product (sum quantities)
5. **Aggregate** payments by payment method
6. **Create** ONE Invoice in NetSuite per shop
7. **Update** Odoo orders with NetSuite invoice ID
8. **Log** sync results

**Example:**
```
Shop: Main Store
Date: 2026-05-16
Orders: 8 POS orders
Payments: Cash (150.00), Card (280.45), Mobile (65.50)
Result: 1 Invoice (INV-463716) with aggregated items and payments
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

### NetSuite Invoice Fields

| Field | Value | Description |
|---|---|---|
| `recordType` | `invoice` | Record type |
| `entity` | Default customer ID | Generic POS customer |
| `subsidiary` | From warehouse mapping | NetSuite subsidiary |
| `department` | From warehouse mapping | NetSuite department |
| `location` | From warehouse mapping | NetSuite location |
| `tranDate` | Invoice date | Date of the orders (YYYY-MM-DD) |
| `memo` | "Consolidated POS Invoice - [Shop] - [Date]" | Description |
| `custbody_pos_shop` | Warehouse name | Custom field |
| `custbody_pos_date` | Invoice date | Custom field |
| `custbody_pos_order_count` | Number of orders | Custom field |
| `items[]` | Aggregated line items | Product details |
| `payments[]` | Aggregated payments | Payment method breakdown |

### Line Item Aggregation

Same as Order Sync - products are aggregated across all orders for the day.

**Example:**
```json
{
  "items": [
    {"item": "1009", "quantity": 5, "rate": 11.36, "amount": 56.80},
    {"item": "1005", "quantity": 3, "rate": 7.53, "amount": 22.59}
  ]
}
```

### Payment Aggregation

Payments are summed by payment method across all orders.

**Before (8 orders):**
```
Order 1: Cash (15.00), Card (35.00)
Order 2: Card (45.50)
Order 3: Cash (25.00)
Order 4: Mobile Pay (20.00)
Order 5: Cash (30.00), Card (15.00)
...
```

**After (1 consolidated invoice):**
```json
{
  "payments": [
    {"paymentMethod": "1", "amount": 150.00},  // Cash
    {"paymentMethod": "2", "amount": 280.45},  // Card
    {"paymentMethod": "3", "amount": 65.50}    // Mobile Pay
  ]
}
```

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

## Differences from Order Sync

| Aspect | Order Sync | Invoice Sync |
|---|---|---|
| **NetSuite Record** | Sales Order | Invoice |
| **Grouping** | By shop + date | By shop only (for specific date) |
| **Includes Payments** | No | Yes |
| **Cron Time** | 00:05 | 00:10 |
| **Sync Mode** | All unsynced dates (manual) | Specific date only |
| **Fields Updated** | `netsuite_id`, `netsuite_tran_id` | `x_netsuite_invoice_id` |
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

✅ **Complete financial picture** - Invoices with payment breakdowns
✅ **Matches Order Sync pattern** - One invoice per shop per day
✅ **Payment reconciliation** - Aggregated by payment method
✅ **Automatic daily sync** - Runs after order sync
✅ **Full audit trail** - Every invoice logged with details
✅ **Production-ready** - Comprehensive error handling and validation
---

**Last Updated:** May 17, 2026  
**Version:** 1.0