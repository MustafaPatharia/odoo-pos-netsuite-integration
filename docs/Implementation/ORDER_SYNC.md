# EOD Order Sync - Odoo to NetSuite

## Overview

The End-of-Day (EOD) Order Sync feature consolidates all POS orders from each shop for each day and creates **ONE Sales Order per shop per day** in NetSuite. This reduces NetSuite transaction volume while maintaining complete order data.

**Sync Methods:**
- **Manual Sync** - Sync all past unsynced orders on-demand
- **Automatic Sync** - Runs daily at midnight (00:05)

---

## Manual EOD Order Sync

### How to Trigger Manual Sync

1. Navigate to: **NetSuite → Operations → Sync Orders**

2. Click the **"Sync Orders"** button

3. Odoo will:
   - Find all unsynced POS orders (excluding today)
   - Group by shop and date
   - Create one consolidated Sales Order per group
   - Display results notification

### What Happens During Sync

1. **Validate** all products have NetSuite IDs
2. **Fetch** all past orders with status: `paid`, `done`, or `invoiced`
3. **Group** orders by warehouse (shop) and date
4. **Aggregate** line items by product (sum quantities)
5. **Create** ONE Sales Order in NetSuite per shop per date
6. **Update** all Odoo orders with NetSuite ID and sync status
7. **Log** sync results

**Example:**
```
Shop: Main Store
Date: 2026-05-16
Orders: 5 POS orders with 15 total line items
Result: 1 Sales Order (SO-578238) with 8 aggregated line items
```

---

## Automatic Daily Sync

### Configuration

The daily sync runs automatically at midnight.

**Schedule:** Daily at 00:05 AM
**Cron Job Name:** `NetSuite: Sync EOD Orders`
**Mode:** Syncs only yesterday's orders

### How It Works

1. **Trigger:** Runs at 00:05 every day
2. **Target Date:** Yesterday (previous day)
3. **Action:** Creates consolidated Sales Orders for yesterday only
4. **Condition:** Only runs if `config_integration_mode == 'scheduled'`

---

## Consolidated Order Structure

### NetSuite Sales Order Fields

| Field | Value | Description |
|---|---|---|
| `entity` | Default customer ID | Generic POS customer |
| `subsidiary` | From warehouse mapping | NetSuite subsidiary |
| `department` | From warehouse mapping | NetSuite department |
| `location` | From warehouse mapping | NetSuite location |
| `tranDate` | Order date | Date of the orders (YYYY-MM-DD) |
| `memo` | "Consolidated POS Order - [Shop] - [Date]" | Description |
| `custbody_pos_shop` | Warehouse name | Custom field |
| `custbody_pos_date` | Order date | Custom field |
| `custbody_pos_order_count` | Number of orders | Custom field |
| `items[]` | Aggregated line items | Product details |

### Line Item Aggregation

**Before (5 orders):**
```
Order 1: Product A (qty: 2)
Order 2: Product A (qty: 1), Product B (qty: 3)
Order 3: Product B (qty: 2)
Order 4: Product C (qty: 1)
Order 5: Product A (qty: 3)
```

**After (1 consolidated order):**
```
Line 1: Product A (qty: 6, rate: 11.36, amount: 68.16)
Line 2: Product B (qty: 5, rate: 7.53, amount: 37.65)
Line 3: Product C (qty: 1, rate: 13.90, amount: 13.90)
```

### Calculation Logic

For each product across all orders:
- **Quantity** = Sum of all quantities
- **Amount** = Sum of all amounts (tax-inclusive)
- **Rate** = Total amount ÷ Total quantity (average unit price)

**Formula:** `rate × quantity = amount` (within rounding precision)

---

## Prerequisites

### 1. Products Must Have NetSuite IDs

All products in POS orders **must** have a NetSuite ID before syncing.

**Options:**
- **Option A:** Sync products from NetSuite first (NetSuite → Operations → Fetch Products)
- **Option B:** Manually set NetSuite ID (Inventory → Products → Edit → Set "NetSuite ID" field)

**Error if missing:**
```
Cannot sync orders: 1 product(s) missing NetSuite IDs:

   • Corner Desk Left Sit (FURN_1118)

Please add NetSuite ID manually:
Inventory → Products → Edit → Set 'NetSuite ID' field
```

### 2. Warehouse Subsidiary Mapping

Each warehouse must be mapped to NetSuite subsidiary/department/location.

**Configure at:** NetSuite → Configurations → Subsidiary Mapping

---

## Order Status Tracking

### Odoo POS Order Fields

| Field | Description | Values |
|---|---|---|
| `netsuite_sync_status` | Sync status | `not_synced`, `synced`, `failed` |
| `netsuite_id` | NetSuite Sales Order ID | e.g., "31943" |
| `netsuite_tran_id` | NetSuite Transaction ID | e.g., "SO-578238" |
| `netsuite_sync_date` | Timestamp of sync | DateTime |
| `netsuite_error` | Error message if failed | Text |

### Status Flow

```
POS Order Created
    ↓
[not_synced] ← Initial status
    ↓
EOD Sync Triggered
    ↓
[synced] ✅ Success → netsuite_id populated
    or
[failed] ❌ Error → netsuite_error populated
```

---

## Sync Logs

All sync operations are logged for audit and troubleshooting.

### Viewing Sync Logs

Navigate to: **NetSuite → Sync → Logs**

Filter by:
- **Record Type:** EOD Order
- **Status:** Success / Failed / Partial
- **Date:** Today / This Week / Custom Range

### Log Details

Each log entry contains:
- **Configuration:** Which NetSuite config was used
- **Reference:** Sync timestamp
- **Record Type:** `eod_order`
- **Status:** `success`, `failed`, or `partial`
- **Request URL:** NetSuite API endpoint
- **Request Method:** `POST`
- **Response Code:** HTTP status (200 = success)
- **Execution Time:** Milliseconds
- **Response Payload:** Full sync results JSON
- **Notes:** Summary (e.g., "Synced: 3/5 (shop+date), Orders: 15, Failed: 2")

---

## Troubleshooting

### Error: "Products missing NetSuite IDs"

**Cause:** One or more products in orders don't have NetSuite ID set.

**Solution:**
1. Note the product names from error message
2. Go to: Inventory → Products
3. Search for each product
4. Click Edit
5. Go to NetSuite tab
6. Set "NetSuite ID" field (get from NetSuite)
7. Save
8. Retry sync

### Error: "No NetSuite subsidiary mapping found"

**Cause:** Warehouse is not mapped to NetSuite subsidiary.

**Solution:**
1. Go to: NetSuite → Configurations → Subsidiary Mapping
2. Create mapping for the warehouse
3. Set subsidiary, department, and location IDs
4. Save
5. Retry sync

### Partial Success

**Cause:** Some shops synced successfully, others failed.

**Solution:**
1. Check sync log for error details
2. Fix issues for failed shops
3. Retry sync (will only sync failed shops)

---

## Best Practices

### 1. Sync Products First

Before using EOD Order Sync:
- Run product sync to populate NetSuite IDs
- Verify all POS products have NetSuite IDs

### 2. Daily Sync Schedule

- **Manual sync:** Use for initial backfill or troubleshooting
- **Automatic sync:** Enable for ongoing daily operations
- **Timing:** Midnight sync captures complete day's data

### 3. Monitor Sync Logs

- Check logs daily for failures
- Address errors promptly
- Review execution times for performance

### 4. Warehouse Mapping

- Complete subsidiary mappings before go-live
- Test with one warehouse first
- Verify NetSuite data accuracy

---

## Summary

✅ **Reduces NetSuite transactions** - One order per shop per day instead of hundreds
✅ **Maintains complete data** - All line items aggregated with accurate quantities
✅ **Automatic daily sync** - Set it and forget it
✅ **Full audit trail** - Every sync logged with details
✅ **Production-ready** - Comprehensive error handling and validation
---

**Last Updated:** May 17, 2026
**Version:** 1.0