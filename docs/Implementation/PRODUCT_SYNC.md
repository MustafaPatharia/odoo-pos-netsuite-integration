# Product Sync - NetSuite to Odoo

## Overview

Syncs inventory items from NetSuite to Odoo's product catalog.

**Sync Methods:**
- **Manual**: Click button to sync anytime
- **Automatic**: Runs every hour

---

## Manual Sync

1. Go to **NetSuite → Operations → Fetch Products**
2. Click **"Fetch Products from NetSuite"**
3. View notification with results (Created: X, Updated: Y, Failed: Z)

**Process:**
1. Connects to NetSuite API
2. Fetches all inventory items
3. Matches products by `x_netsuite_id`
4. Creates new or updates existing products
5. Updates stock levels
6. Logs sync results

---

## Automatic Hourly Sync

**Schedule:** Every 1 hour (runs at :00 minutes)  
**Cron Job:** `NetSuite: Fetch Products Hourly`  
**Condition:** Only in `scheduled` integration mode

**Check Status:**  
Settings → Technical → Automation → Scheduled Actions → Search "NetSuite: Fetch Products"

---

## Field Mapping

| NetSuite Field | Odoo Field | Type | Description |
|---|---|---|---|
| `id` | `x_netsuite_id` | String | NetSuite internal ID |
| `itemid` | `default_code` | String | Item SKU/Reference |
| `displayname` | `name` | String | Product name |
| `description` | `description` | Text | Product description |
| `baseprice` | `list_price` | Float | Sales price |
| `cost` | `standard_price` | Float | Cost price |
| `isinactive` | `active` | Boolean | Active (inverted) |
| `quantityavailable` | Stock | Float | Available quantity |

**Custom Fields Added:**
- `x_netsuite_id` - NetSuite internal ID
- `x_netsuite_last_sync` - Last sync timestamp

---

## Sync Logs

**View:** NetSuite → Sync → Logs → Filter by `Product`

**Log Fields:**
- Reference: Product Sync YYYY-MM-DD HH:MM:SS
- Status: success/failed/partial
- Response Code: HTTP status
- Execution Time: milliseconds
- Notes: Created: X, Updated: Y, Failed: Z

---

## Troubleshooting

**No products synced:**  
→ Check API URL in NetSuite → Configurations  
→ Verify NetSuite server is accessible  
→ Check sync logs for errors

**Sync failed:**  
→ View NetSuite → Sync → Logs  
→ Check error message  
→ Common issues: connection timeout, 401 unauthorized, 404 not found

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
