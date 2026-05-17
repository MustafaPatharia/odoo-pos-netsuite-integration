# Product Sync - NetSuite to Odoo

## Overview

The Product Sync feature automatically fetches inventory items from NetSuite and creates or updates them in Odoo's product catalog. This ensures your Odoo POS always has the latest product information from NetSuite.

**Sync Methods:**
- **Manual Sync** - Click a button to sync on-demand
- **Automatic Sync** - Runs every hour automatically

---

## Manual Product Sync

### How to Trigger Manual Sync

1. Navigate to: **NetSuite → Operations → Fetch Products**

![NetSuite Menu - Operations - Fetch Products](./images/Screenshot:%20NetSuite%20Menu%20-%20Operations%20-%20Fetch%20Products.jpg)

2. Click the **"Fetch Products from NetSuite"** button

![Screenshot: Fetch Products Button in Action View](./images/Screenshot:%20Fetch%20Products%20Button%20in%20Action%20View.jpg)

3. Odoo will fetch all products from NetSuite and display a notification with results

![Screenshot: Success Log List](./images/Screenshot:%20Success%20Log%20List.jpg)
![Screenshot: Success Log View](./images/Screenshot:%20Success%20Log%20View.jpg)

### What Happens During Sync

1. **Connect** to NetSuite API
2. **Fetch** all inventory items
3. **Match** products by NetSuite ID (`x_netsuite_id`)
4. **Create** new products if they don't exist
5. **Update** existing products with latest data
6. **Log** the sync results

---

## Automatic Hourly Sync

### Configuration

The hourly sync runs automatically in the background. No setup required!

**Schedule:** Every 1 hour
**Time:** Runs at :00 minutes (e.g., 09:00, 10:00, 11:00)
**Cron Job Name:** `NetSuite: Fetch Products Hourly`

### How to Check if Hourly Sync is Active

1. Go to: **Settings → Technical → Automation → Scheduled Actions**

   `[Screenshot: Settings - Technical Menu - Scheduled Actions]`

2. Search for: `NetSuite: Fetch Products`

   `[Screenshot: Scheduled Actions List - NetSuite Fetch Products Hourly]`

3. Verify:
   - **Active:** ✅ (checkbox is checked)
   - **Interval:** 1 Hours
   - **Next Execution:** Shows next run time

---

## Product Field Mapping

| NetSuite Field | Odoo Field | Description |
|---|---|---|
| `id` | `x_netsuite_id` | NetSuite internal ID (unique identifier) |
| `itemid` | `default_code` | Item SKU/Reference |
| `displayname` | `name` | Product name |
| `description` | `description` | Product description |
| `baseprice` | `list_price` | Sales price |
| `cost` | `standard_price` | Cost price |
| `isinactive` | `active` | Active status (inverted) |

### Custom Fields Created

Two custom fields are added to Odoo products to track NetSuite sync:

- **NetSuite ID** (`x_netsuite_id`) - Stores NetSuite internal ID
- **Last Fetched** (`x_netsuite_last_sync`) - Timestamp of last sync

   `[Screenshot: Product Form - NetSuite Tab showing NetSuite ID and Last Fetched]`

---

## Viewing Products

### Product List View

Navigate to: **NetSuite → Operations → Fetch Products**

The product list shows:
- Product name
- SKU (Internal Reference)
- Sales Price
- NetSuite ID (if synced)
- Last Fetched timestamp (if synced)

   `[Screenshot: Product List View with NetSuite columns]`

### Product Form View - NetSuite Tab

Open any product and navigate to the **NetSuite** tab to see:
- NetSuite ID
- Last Fetched timestamp

   `[Screenshot: Product Form - NetSuite Tab]`

---

## Sync Logs

### How to View Sync Logs

1. Navigate to: **NetSuite → Sync → Logs**

   `[Screenshot: NetSuite Menu - Sync - Logs]`

2. Filter by **Record Type:** `Product`

   `[Screenshot: Sync Logs - Filtered by Product]`

### Log Information

Each sync log entry shows:

| Field | Description |
|---|---|
| Reference | `Product Sync YYYY-MM-DD HH:MM:SS (+00:00)` |
| Status | Success / Failed / Partial |
| Request URL | NetSuite API endpoint called |
| Request Method | GET |
| Response Code | HTTP status (200 = success) |
| Execution Time | Time taken in milliseconds |
| Notes | Summary: "Created: X, Updated: Y, Failed: Z" |
| Response Payload | Detailed sync results (JSON) |
| Error Message | Error details if failed |

   `[Screenshot: Sync Log Detail View - Product Sync Success]`

---

## Troubleshooting

### No Products Synced (Created: 0, Updated: 0)

**Possible Causes:**
- NetSuite API URL is incorrect
- NetSuite server is down
- No items in NetSuite inventory

**Solution:**
1. Check NetSuite configuration: **NetSuite → Configurations → NetSuite Settings**
2. Verify **API URL** is correct
3. Check sync logs for error messages

   `[Screenshot: NetSuite Configuration - API URL field]`

### Sync Failed with Error

**Solution:**
1. Go to **NetSuite → Sync → Logs**
2. Open the failed sync log
3. Check **Error Message** field for details
4. Common errors:
   - Connection timeout → Check network/firewall
   - 401 Unauthorized → Check credentials
   - 404 Not Found → Check API URL

   `[Screenshot: Sync Log - Failed with Error Message]`

### Products Not Updating

**Possible Causes:**
- Product exists in Odoo but NetSuite ID is missing
- NetSuite ID mismatch

**Solution:**
1. Open the product in Odoo
2. Go to **NetSuite** tab
3. Verify **NetSuite ID** matches the NetSuite item ID
4. If missing, manually enter the NetSuite ID and run sync again

---

**Last Updated:** May 17, 2026
**Version:** 1.0
