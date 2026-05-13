# Quick Start Guide - Odoo POS ↔ NetSuite Integration

**Version**: 2.0
**Date**: May 13, 2026

---

## 🚀 Step-by-Step Setup & Testing

### Prerequisites

- Docker & Docker Compose installed
- Node.js 16+ installed
- Git installed

---

## Step 1: Start the Mock NetSuite Server

```bash
cd mock-netsuite-server
npm install
npm start
```

**Expected Output**:
```
🚀 NetSuite Mock Server v2.0 Started
📡 Port: 3000
🌐 Base URL: http://localhost:3000
```

**Test Health Check**:
```bash
curl http://localhost:3000/health
```

---

## Step 2: Start Odoo

```bash
cd ..
./start.sh
```

**Or manually**:
```bash
docker-compose up -d
```

**Access Odoo**:
- URL: http://localhost:8069
- Database: Create new or use existing
- Install module: `netsuite_pos_integration`

---

## Step 3: Configure NetSuite Integration

### 3.1 Set Credentials

1. Go to **NetSuite → Configuration**
2. Open the configuration record
3. Set:
   - **API URL**: `http://host.docker.internal:3000`
   - **Account ID**: `test_account`
   - **Consumer Key**: (leave blank for mock)
   - **Active**: ✅ True

### 3.2 Fetch Configuration from NetSuite

Click **"Fetch Config from NetSuite"** button

**Expected**: Green notification "Successfully fetched configuration from NetSuite"

**Verify**: Scroll down to see computed fields populated:
- Integration Mode: `scheduled`
- Hourly Sync Enabled: ✅
- Max Retries: `3`
- etc.

---

## Step 4: Create Shop/Subsidiary Mapping

1. Go to **NetSuite → Shop/Subsidiary Mapping**
2. Click **Create**
3. Fill in:
   - **Odoo Warehouse/Shop**: Select "WH" (or create test warehouse)
   - **NetSuite Subsidiary ID**: `1`
   - **NetSuite Subsidiary Name**: `Main Subsidiary`
4. **Save**

---

## Step 5: Test Product Sync

### Method 1: Manual Sync (Recommended for First Test)

1. Go to **Products → Products**
2. Click **Action** dropdown (top-right)
3. Select **"Sync All Products from NetSuite"**
4. Wait 2-3 seconds
5. **Expected**: Notification showing "Created: 5, Updated: 0, Failed: 0"

### Method 2: Run Cron Manually

1. Enable **Developer Mode**: Settings → Activate Developer Mode
2. Go to **Settings → Technical → Automation → Scheduled Actions**
3. Find **"NetSuite: Fetch Products Hourly"**
4. Click **"Run Manually"**
5. Refresh Products page

**Verify**:
- 5 new products created:
  - Coffee - Espresso
  - Coffee - Latte
  - Pastry - Croissant
  - Sandwich - Club
  - Juice - Orange
- Each has:
  - NetSuite ID (e.g., `1001`)
  - Default Code (e.g., `ITEM-001`)
  - List Price
  - NetSuite Sync Status: `synced`

---

## Step 6: Create Test POS Orders

### 6.1 Create POS Session

1. Go to **Point of Sale → Dashboard**
2. Click **"New Session"**
3. Select **default POS config**
4. Click **"Open Session"**

### 6.2 Create Orders

1. In POS interface, add products:
   - Coffee - Espresso × 2
   - Pastry - Croissant × 1
2. Click **Payment**
3. Select **Cash**
4. Click **Validate**
5. Repeat 3-4 times with different products

### 6.3 Close Session

1. Click **Close** button
2. Click **"Close Session"**
3. Go back to Odoo backend

---

## Step 7: Verify Orders Created

1. Go to **Point of Sale → Orders → Orders**
2. **Verify**:
   - 3-4 orders visible
   - **NetSuite Status**: `not_synced` (default)
   - **Date**: Today's date

---

## Step 8: Test Consolidated Order Sync

### Manual Trigger (Simulating Midnight Sync)

1. Go to **Settings → Technical → Scheduled Actions**
2. Find **"NetSuite: Sync Consolidated Orders Daily"**
3. Click **"Run Manually"**

**Expected Behavior**:
- Since target date is "yesterday", and your orders are "today", they **won't sync yet**
- This is correct per SOW (midnight sync targets N-1)

### Force Sync for Today (Testing Only)

**Option A**: Change order dates to yesterday manually
1. Enable Developer Mode
2. Edit each order
3. Change `date_order` to yesterday
4. Re-run cron

**Option B**: Use Odoo shell (advanced)
```python
# Connect to Odoo shell
from datetime import datetime, timedelta
target_date = datetime.now().date()  # Today instead of yesterday
result = env['netsuite.consolidated.sync'].sync_consolidated_orders(target_date=target_date)
print(result)
```

---

## Step 9: Verify in Mock NetSuite Server

### Check Created Orders

```bash
curl http://localhost:3000/api/debug/orders
```

**Expected JSON Response**:
```json
{
  "orders": [
    {
      "id": "5000",
      "tranId": "SO-1715678901234",
      "tranDate": "2026-05-13",
      "subsidiary": "1",
      "memo": "Consolidated POS Order - WH - 2026-05-13",
      "items": [
        { "item": "1001", "quantity": 6, "rate": 3.50, "amount": 21.00 },
        { "item": "1003", "quantity": 3, "rate": 2.50, "amount": 7.50 }
      ],
      "createdAt": "2026-05-13T12:34:56.789Z",
      "status": "Pending Fulfillment"
    }
  ],
  "count": 1
}
```

**Explanation**:
- **1 consolidated order** created (not 3-4 individual orders)
- Line items aggregated by product
- All orders from that shop/day merged

---

## Step 10: Test Configuration Update via API

### Using curl

```bash
curl -X POST http://localhost:8069/api/netsuite/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "db": "odoo_db_name",
    "login": "admin",
    "password": "admin",
    "configuration": {
      "integration_mode": "scheduled",
      "retry_policy": {
        "enabled": true,
        "max_retries": 5,
        "initial_delay_minutes": 10,
        "use_exponential_backoff": true,
        "backoff_multiplier": 2
      },
      "scheduled_settings": {
        "enabled": true,
        "order_sync_time": "00:00",
        "invoice_sync_time": "00:00",
        "product_sync_frequency": "hourly"
      },
      "consolidation_rules": {
        "consolidate_orders_per_shop_per_day": true,
        "consolidate_invoices_per_shop_per_day": true
      }
    },
    "metadata": {
      "config_version": "1.0",
      "last_updated_by": "NetSuite Admin",
      "netsuite_environment": "sandbox"
    }
  }'
```

**Replace**:
- `odoo_db_name` with your actual database name
- `admin` / `admin` with your Odoo credentials

**Expected Response**:
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": 1,
  "applied_at": "2026-05-13T12:34:56.789Z"
}
```

### Verify in Odoo

1. Go to **NetSuite → Configuration**
2. Refresh page
3. Check **"Max Retries"** field = `5` (changed from 3)

---

## Step 11: View Sync Logs

1. Go to **NetSuite → Sync Logs**
2. **See**:
   - `product_import` logs (from product sync)
   - `consolidated_order` logs (if you ran order sync)
   - Request/response payloads
   - Execution times
   - Error messages (if any)

**Filter by**:
- Sync Type
- Status (success/failed)
- Date range

---

## 🧪 Advanced Testing Scenarios

### Scenario 1: Test Exponential Backoff Retry

1. **Stop mock server** (simulate NetSuite down)
2. Try to sync products
3. **Expected**: Error logged
4. **Start mock server**
5. Check if retry happens automatically

### Scenario 2: Test Multiple Shops

1. Create second warehouse: **Shop B**
2. Create subsidiary mapping for Shop B → Subsidiary 2
3. Create POS orders in different shops
4. Run midnight sync
5. **Verify**: 2 consolidated orders created (one per shop)

### Scenario 3: Test Invoice Sync

1. Use same orders from order sync test
2. Go to **Scheduled Actions**
3. Find **"NetSuite: Sync Consolidated Invoices Daily"**
4. Run manually
5. Check: `curl http://localhost:3000/api/debug/invoices`
6. **Expected**: 1 invoice created with payment data

---

## 🐛 Troubleshooting

### Problem: "No active NetSuite configuration found"

**Solution**:
1. Check NetSuite → Configuration
2. Make sure **Active** = ✅
3. Click **Test Connection**

---

### Problem: Products not syncing

**Check**:
1. Mock server is running (`http://localhost:3000/health`)
2. API URL in config = `http://host.docker.internal:3000`
3. Configuration has `hourly_sync_enabled = True`
4. Check sync logs for errors

---

### Problem: Orders not syncing

**Check**:
1. Order date is **yesterday** (not today)
2. Order state = `paid` or `done`
3. NetSuite sync status = `not_synced` or `failed`
4. Subsidiary mapping exists for the warehouse
5. Check cron logs: Settings → Technical → Scheduled Actions → ir_cron_netsuite_order_sync

---

### Problem: API returns "Authentication failed"

**Check**:
1. Database name is correct
2. User credentials are correct
3. User has access rights to `netsuite.config` model

---

## 📊 Monitoring in Production

### Daily Checklist

- [ ] Check sync logs for failures
- [ ] Verify cron jobs ran successfully
- [ ] Review error notifications (if email enabled)
- [ ] Spot-check NetSuite for orders/invoices
- [ ] Monitor log retention (auto-cleanup enabled)

### Weekly Checklist

- [ ] Review retry statistics
- [ ] Check product sync accuracy
- [ ] Validate subsidiary mappings
- [ ] Test manual sync buttons

---

## 🎓 What's Next?

### Phase 2 (Future)

1. **NetSuite Reporting Dashboard** (SOW requirement)
   - Create dashboard with charts
   - Success/failure metrics
   - Daily transaction volumes

2. **Real-Time Sync Mode**
   - Enable `integration_mode: realtime`
   - Trigger on order confirmation

3. **Payment Method Master Data Sync**
   - Fetch payment methods from NetSuite
   - Auto-create mappings

4. **Advanced Error Recovery**
   - Email notifications on failure
   - Slack/Teams webhooks
   - Automatic retry escalation

---

## ✅ Success Criteria

You've successfully set up the integration if:

✅ Mock server running and accessible
✅ Odoo configuration fetched from NetSuite
✅ 5 products synced from NetSuite
✅ Shop/subsidiary mapping created
✅ POS orders created successfully
✅ Consolidated order sent to NetSuite (visible in debug endpoint)
✅ Sync logs show success status
✅ Cron jobs scheduled and active

**You're ready to go! 🎉**

---

## 📞 Support

**Issues or Questions?**

1. Check [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) for detailed architecture
2. Review [STATEMENT_OF_WORK.md](./STATEMENT_OF_WORK.md) for requirements
3. Inspect sync logs in Odoo for error details
4. Check mock server console for API call logs

**Happy Integrating!** 🚀
