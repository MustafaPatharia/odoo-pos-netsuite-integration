# 🚀 Quick Setup Guide - Simplified Architecture

## ✅ What Changed

The integration is now **COMPLETELY SIMPLIFIED**:

### Before (Complex - WRONG ❌)
- Odoo stored retry logic, batch size, sync modes
- Complex configuration in Odoo
- Odoo made decisions about when/how to retry

### Now (Simple - CORRECT ✅)
- **Odoo = Dumb Client** (only stores credentials)
- **NetSuite = Brain** (controls everything)
- **Two Fixed Cron Jobs** (hourly items, end of day invoices)

---

## 📋 Setup Steps

### 1. Configure Odoo (ONLY Credentials)

Go to **Settings → NetSuite Configuration** and fill in:

```
API URL: http://localhost:3000
Account ID: TSTDRV123456
Consumer Key: test_key
Consumer Secret: test_secret
Token ID: test_token
Token Secret: test_token_secret
```

Click **[Fetch Configuration]** button → This gets ALL settings from NetSuite!

### 2. Verify Mock Server

Test the configuration endpoint:
```bash
curl "http://localhost:3000/app/site/hosting/restlet.nl?action=getConfig"
```

Should return:
```json
{
  "success": true,
  "configuration": {
    "retry_enabled": true,
    "max_retries": 3,
    "send_email_on_failure": true,
    "hourly_sync_enabled": true,
    "end_of_day_sync_time": "23:59",
    ...
  }
}
```

---

## 🔄 How It Works Now

### Hourly Item Sync
**When:** Every hour
**What:** Syncs all products/items
**How:** Automatic cron job

### End of Day Invoice Sync
**When:** Daily at 11:59 PM
**What:** ALL paid invoices from the entire day
**How:** Sent as ONE batch, not per-record

### Configuration Fetch
**When:** Manual button click or can be scheduled
**What:** Gets all business logic from NetSuite
**Result:** Stored in Odoo as JSON (read-only)

---

## 🎯 What Odoo Does

1. ✅ Store credentials
2. ✅ Fetch configuration from NetSuite
3. ✅ Run two fixed cron jobs
4. ✅ Send data to NetSuite
5. ✅ Log responses for audit

## 🎯 What NetSuite Controls

1. ✅ Retry logic (how many, when)
2. ✅ Email notifications
3. ✅ Batch sizes
4. ✅ Sync schedules
5. ✅ All business rules

---

## 📝 Testing

### Test Configuration Fetch
```bash
# From Odoo, click "Fetch Configuration" button
# Or call the API directly:
curl "http://localhost:3000/app/site/hosting/restlet.nl?action=getConfig"
```

### Test Invoice Sync
```python
# Create a POS order and mark as paid
# Wait for end of day cron (or trigger manually)
# Check sync logs in Odoo
```

### View Logs
Go to **NetSuite → Sync Logs** to see all API calls and responses

---

## 🔧 Customization

### Change Retry Logic
Edit mock server `/mock-netsuite-server/server.js`:
```javascript
function handleGetConfig(req, res) {
  const config = {
    max_retries: 5,  // ← Change this
    retry_delay_minutes: 10,  // ← Or this
    ...
  };
  res.json(config);
}
```

### Change Cron Schedule
From NetSuite configuration response:
```json
{
  "hourly_sync_enabled": false,  ← Disable hourly sync
  "end_of_day_sync_time": "22:00"  ← Change to 10 PM
}
```

---

## 🎉 Benefits

✅ **Super simple** - Odoo is just a data sender
✅ **Centralized control** - Change NetSuite config without touching Odoo
✅ **Two fixed patterns** - Hourly items + End of day invoices
✅ **Clean architecture** - Clear separation of responsibilities
✅ **Easy to test** - Mock server simulates everything

---

## 📚 Files Changed

1. **netsuite_config.py** - Simplified to ONLY store credentials
2. **netsuite_cron_data.xml** - Two fixed cron jobs
3. **mock-netsuite-server/server.js** - Added getConfig endpoint
4. **ARCHITECTURE.md** - Complete architecture documentation

---

## 🚀 Next Steps

1. Restart Odoo to load changes:
   ```bash
   docker-compose restart odoo
   ```

2. Upgrade the module in Odoo:
   - Go to Apps
   - Search "NetSuite"
   - Click "Upgrade"

3. Configure credentials in Odoo

4. Click "Fetch Configuration" to get settings from NetSuite

5. Test by creating a POS order!

---

**That's it! Simple, clean, and enterprise-grade!** 🎉
