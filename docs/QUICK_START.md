# Quick Start Guide - Odoo POS ↔ NetSuite Integration

**Last Updated**: May 20, 2026  
**Module Version**: 17.0.1.0.0

---

## 🎯 Overview

This guide walks you through **setting up, configuring, and testing** the Odoo-NetSuite POS integration from scratch.

**Time to Complete**: ~15 minutes  
**Difficulty**: Beginner-friendly

---

## 📋 Prerequisites

Before starting, ensure you have:

- ✅ **Docker** and **Docker Compose** installed
- ✅ **Node.js 16+** installed (for mock server)
- ✅ **Git** installed
- ✅ **Terminal** access (bash/zsh)
- ✅ Basic understanding of Odoo and POS systems

---

## 🚀 Part 1: Environment Setup

### Step 1.1: Clone the Repository

```bash
git clone https://github.com/MustafaPatharia/odoo-pos-netsuite-integration.git
cd odoo-pos-netsuite-integration
```

### Step 1.2: Start Mock NetSuite Server

**Why?** The mock server simulates NetSuite RESTlet APIs for development/testing.

```bash
cd mock-netsuite-server
npm install
npm start
```

**Expected Output:**
```
🚀 NetSuite Mock Server v2.0 Started
📡 Port: 3000
🌐 Base URL: http://localhost:3000
✅ RESTlet endpoints ready
```

**Verify Health Check:**
```bash
curl http://localhost:3000/health
```

**Expected Response:**
```json
{"status":"healthy","message":"NetSuite Mock Server is running"}
```

**Keep this terminal open** - leave the mock server running.

### Step 1.3: Start Odoo with Docker

**Open a new terminal** in the project root directory:

```bash
cd ..  # Back to project root
docker-compose up -d
```

**Services Started:**
- **Odoo Web**: `http://localhost:8069`
- **PostgreSQL**: `localhost:5432`
- **Network**: `odoo_netsuite_network`

**Wait ~30 seconds** for services to fully initialize.

**Verify Odoo is Running:**
```bash
curl -I http://localhost:8069
```

---

## ⚙️ Part 2: Odoo Configuration

### Step 2.1: Create/Access Database

1. Open browser → **http://localhost:8069**
2. **If first time:**
   - Click **"Create Database"**
   - **Master Password**: `admin`
   - **Database Name**: `odoo_netsuite`
   - **Email**: `admin@example.com`
   - **Password**: `admin`
   - **Language**: English
   - **Country**: (your country)
   - Click **"Create Database"**
3. **If database exists:** Login with `admin / admin`

### Step 2.2: Install NetSuite Integration Module

1. Go to **Apps** (top menu)
2. **Remove** the "Apps" filter (click the ❌ on filter)
3. Search: **"NetSuite POS Integration"**
4. Click **"Install"** button
5. Wait for installation to complete (~30 seconds)
6. You should see **"Module installed successfully"** notification

### Step 2.3: Verify Installation

Check that new menu items appear:
- **NetSuite** (top menu) with sub-menus:
  - Configuration
  - Shop Mappings
  - Product Mappings
  - Sync Logs
  - Sync Queue
  - Operations

---

## 🔌 Part 3: NetSuite Integration Configuration

### Step 3.1: Configure Connection

1. Navigate to **NetSuite → Configuration**
2. You should see one configuration record - **click to open it**
3. Fill in the following:

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | NetSuite Integration | (default) |
| **Active** | ✅ Checked | Enable integration |
| **API URL** | `http://host.docker.internal:3000` | Points to mock server |
| **Account ID** | `test_account` | Mock server default |
| **Consumer Key** | (leave blank) | Not required for mock |
| **Consumer Secret** | (leave blank) | Not required for mock |
| **Token ID** | (leave blank) | Not required for mock |
| **Token Secret** | (leave blank) | Not required for mock |

4. Click **"Save"**

**Important:** Use `host.docker.internal` instead of `localhost` because Odoo runs inside Docker and needs to access the host machine.

### Step 3.2: Fetch Configuration from NetSuite

**This is crucial** - it loads all business logic settings from NetSuite into Odoo.

1. On the configuration page, click button: **"Fetch Config from NetSuite"**
2. Wait ~2 seconds
3. **Expected:** Green success notification: "Successfully fetched configuration from NetSuite"

**Scroll down** to verify computed fields are populated:

| Field | Expected Value |
|-------|----------------|
| **Integration Mode** | Scheduled |
| **Hourly Sync Enabled** | ✅ Yes |
| **End of Day Sync Time** | 23:59 |
| **Max Retries** | 3 |
| **Retry Delay** | 5 minutes |
| **Send Email on Failure** | ✅ Yes |

### Step 3.3: Test Connection

1. Click button: **"Test Connection"**
2. **Expected:** Green notification: "Connection successful! NetSuite is reachable."
3. **If error:** Check mock server is still running, verify API URL

---

## 🏪 Part 4: Shop/Subsidiary Mapping

**Why?** Each Odoo warehouse/shop needs to map to a NetSuite subsidiary.

### Step 4.1: Create Mapping

1. Go to **NetSuite → Shop/Subsidiary Mapping**
2. Click **"Create"** (top-left button)
3. Fill in:

| Field | Value |
|-------|-------|
| **Odoo Warehouse/Shop** | WH (or create test warehouse if doesn't exist) |
| **NetSuite Subsidiary ID** | `1` |
| **NetSuite Subsidiary Name** | `Main Subsidiary` |

4. Click **"Save"**

**Verify:**
- Record shows in the list view
- All fields are filled correctly

---

## 📦 Part 5: Product Synchronization

### Step 5.1: Manual Product Sync (First Time)

1. Go to **Products → Products**
2. Click **"Action"** dropdown (top-right, near "Print")
3. Select **"Sync All Products from NetSuite"**
4. Wait ~3 seconds
5. **Expected Notification:** "Product sync completed. Created: 5, Updated: 0, Failed: 0"

### Step 5.2: Verify Products Created

**Refresh the page** - you should see 5 new products:

| Product Name | Default Code | NetSuite ID | Price |
|--------------|--------------|-------------|-------|
| Coffee - Espresso | ITEM-001 | 1001 | $3.50 |
| Coffee - Latte | ITEM-002 | 1002 | $4.50 |
| Pastry - Croissant | ITEM-003 | 1003 | $2.50 |
| Sandwich - Club | ITEM-004 | 1004 | $7.50 |
| Juice - Orange | ITEM-005 | 1005 | $3.00 |

**Check Product Details:**
1. Open any product (e.g., "Coffee - Espresso")
2. You should see new fields:
   - **NetSuite ID**: `1001`
   - **NetSuite Sync Status**: `synced`
   - **Last Sync**: (timestamp)

### Step 5.3: Automatic Hourly Sync (Optional)

The system automatically syncs products every hour via cron job.

**To trigger manually:**
1. Enable **Developer Mode**: Settings → Activate Developer Mode
2. Go to **Settings → Technical → Automation → Scheduled Actions**
3. Search: **"NetSuite: Fetch Products Hourly"**
4. Click the record → Click **"Run Manually"**
5. Refresh Products page to see updates

---

## 🛒 Part 6: Create and Sync POS Orders

### Step 6.1: Create POS Config (If Needed)

1. Go to **Point of Sale → Configuration → Point of Sale**
2. **If no POS exists**, click **"Create"**:
   - **Name**: Shop 1
   - **Warehouse**: WH
   - **Available Payment Methods**: Cash, Bank
   - Click **"Save"**

### Step 6.2: Open POS Session

1. Go to **Point of Sale → Dashboard**
2. Find your POS config (e.g., "Shop 1")
3. Click **"New Session"**
4. Click **"Open Session"** button
5. Click **"Resume"** to open POS interface

### Step 6.3: Create Test Orders

**Create 3-4 orders with different products:**

**Order 1:**
1. Add: Coffee - Espresso × 2
2. Add: Pastry - Croissant × 1
3. Click **"Payment"**
4. Select **"Cash"**
5. Click **"Validate"**
6. Click **"New Order"**

**Order 2:**
1. Add: Coffee - Latte × 1
2. Add: Juice - Orange × 2
3. Click **"Payment"** → **"Cash"** → **"Validate"**
4. Click **"New Order"**

**Order 3:**
1. Add: Sandwich - Club × 1
2. Add: Coffee - Espresso × 1
3. Click **"Payment"** → **"Cash"** → **"Validate"**

### Step 6.4: Close POS Session

1. Click **"Close"** (top-left corner)
2. Review closing balances
3. Click **"Close Session"**
4. Confirm closing

### Step 6.5: Verify Orders in Backend

1. Go to **Point of Sale → Orders**
2. You should see 3 orders created
3. **Important fields** to check:
   - **State**: Paid / Done
   - **NetSuite Sync Status**: `Not Synced` (will change after EOD sync)
   - **Date**: Today's date

---

## 🌙 Part 7: End-of-Day Sync Testing

### Option A: Manual Batch Sync (Recommended for Testing)

**Note**: Manual sync only works for **previous dates**, not today.

**Workaround** - Manually change order dates:

1. **Enable Developer Mode** if not already
2. Go to **Point of Sale → Orders**
3. Open one order
4. Change **"Date"** field to **yesterday**
5. Click **"Save"**
6. Repeat for other orders
7. Go back to list view
8. **Select all 3 orders** (checkboxes)
9. **Action → Sync Selected to NetSuite**
10. Wait ~3 seconds

**Expected Result:**
- **Notification**: "Sync initiated for 3 order(s) grouped into 1 invoice(s)"
- **Sync Logs** created: NetSuite → Sync Logs (check status)

### Option B: Automated End-of-Day Cron

**Runs automatically at 23:59** (configured in NetSuite config).

**To trigger manually:**
1. Go to **Settings → Technical → Automation → Scheduled Actions**
2. Find: **"NetSuite: End of Day Order Sync"**
3. Click **"Run Manually"**
4. Check **NetSuite → Sync Logs** for results

### Step 7.3: Verify Sync Results

1. Go to **NetSuite → Sync Logs**
2. Find latest sync record
3. Check:
   - **Status**: `success` (green)
   - **Operation**: `sync_consolidated_orders`
   - **Reference**: Shows order count
   - **Response Payload**: (if enabled) Shows NetSuite response

4. Go to **Point of Sale → Orders**
5. Check synced orders:
   - **NetSuite Sync Status**: `Synced` (green badge)
   - **NetSuite Invoice Ref**: (NetSuite invoice ID)

### Step 7.4: View in Mock Server

Check mock server stored data:

```bash
curl http://localhost:3000/admin/orders
```

You should see consolidated invoice with all order line items aggregated.

---

## 📊 Part 8: Monitoring & Verification

### View Sync Logs

**NetSuite → Sync Logs** shows:
- All sync attempts (success/failure)
- Timestamps and duration
- Request/response payloads (if logging enabled)
- Error messages for failed syncs

**Filter by:**
- Operation type (order sync, product sync, etc.)
- Status (success, failed, pending)
- Date range

### View Queue Status

**NetSuite → Sync Queue** shows:
- Background jobs being processed
- Retry attempts for failed jobs
- Job status (draft, pending, processing, done, failed)
- Next retry timestamp

### Check Mock Server Data

```bash
# View all stored invoices
curl http://localhost:3000/admin/invoices

# View all stored orders
curl http://localhost:3000/admin/orders

# View mock server logs
# (check the terminal where mock server is running)
```

---

## ✅ Part 9: Success Checklist

Confirm all these are working:

- [ ] ✅ Mock server running on port 3000
- [ ] ✅ Odoo accessible at http://localhost:8069
- [ ] ✅ Module installed and visible in Apps
- [ ] ✅ NetSuite configuration created
- [ ] ✅ Configuration fetched from NetSuite (computed fields populated)
- [ ] ✅ Connection test successful
- [ ] ✅ Shop/subsidiary mapping created
- [ ] ✅ Products synced from NetSuite (5 products)
- [ ] ✅ POS orders created and marked as paid
- [ ] ✅ Manual sync completed successfully
- [ ] ✅ Sync logs show success status
- [ ] ✅ Orders marked as "Synced" in Odoo
- [ ] ✅ Mock server received consolidated invoice

---

## 🔧 Troubleshooting

### Connection Failed

**Error:** "Connection failed" when testing connection

**Solutions:**
1. Verify mock server is running: `curl http://localhost:3000/health`
2. Check API URL uses `host.docker.internal` (not `localhost`)
3. Restart mock server: `npm start`
4. Check Docker network: `docker network inspect odoo_netsuite_network`

### Products Not Syncing

**Error:** "Product sync failed" or no products created

**Solutions:**
1. Check mock server logs for errors
2. Verify mock server's `data/mock-database.js` has product data
3. Check Sync Logs for detailed error messages
4. Try manual sync again: **Products → Action → Sync from NetSuite**

### Orders Not Syncing

**Error:** "No orders found to sync" or sync fails

**Solutions:**
1. **Manual sync:** Ensure orders are from **previous dates** (not today)
2. Verify orders are in **"Paid"** state
3. Check shop/subsidiary mapping exists for the warehouse
4. Verify orders have `pos_reference` (linked to POS session)
5. Check **NetSuite → Sync Logs** for error details

### Fetch Config Failed

**Error:** "Failed to fetch configuration from NetSuite"

**Solutions:**
1. Verify API URL is correct and accessible
2. Check mock server's `/app/site/hosting/restlet.nl?action=getConfig` endpoint
3. Test with curl:
   ```bash
   curl -X POST "http://localhost:3000/app/site/hosting/restlet.nl?action=getConfig"
   ```
4. Check mock server console for errors

### Mock Server Issues

**Error:** Mock server crashes or port already in use

**Solutions:**
1. Check if port 3000 is already used: `lsof -i :3000`
2. Kill existing process: `kill -9 <PID>`
3. Change port in `mock-netsuite-server/server.js` (update Odoo API URL accordingly)
4. Reinstall dependencies:
   ```bash
   cd mock-netsuite-server
   rm -rf node_modules package-lock.json
   npm install
   npm start
   ```

---

## 📚 Next Steps

**Now that setup is complete:**

1. **Read Architecture Docs:** [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Explore Technical Details:** [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)
3. **Review Implementation Guides:** `docs/Implementation/` folder
4. **Customize Configuration:** Edit mock server to change retry logic, schedules, etc.
5. **Connect Real NetSuite:** Replace mock server URL with actual NetSuite API URL and credentials

---

## 🎉 Congratulations!

You've successfully set up the Odoo-NetSuite POS integration!

**Key Achievements:**
- ✅ Environment fully configured
- ✅ Products synchronized from NetSuite
- ✅ POS orders created and synced
- ✅ Consolidated invoicing working
- ✅ Audit logs captured

**Questions?** Check [ARCHITECTURE.md](ARCHITECTURE.md) or [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for deeper insights.

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
