# Postman Configuration Guide

## 📮 How to Test Configuration POST API

### Step 1: Create New Request in Postman

1. **Method**: `POST`
2. **URL**: `http://localhost:8069/api/netsuite/config/update`

---

### Step 2: Set Headers

Add the following header:

| Key | Value |
|-----|-------|
| `Content-Type` | `application/json` |

---

### Step 3: Set Request Body

1. Go to **Body** tab
2. Select **raw**
3. Select **JSON** from dropdown
4. Paste the payload from `POSTMAN_CONFIG_SAMPLE.json`

Or copy this directly:

```json
{
  "db": "odoo_netsuite",
  "login": "admin",
  "password": "admin",
  "configuration": {
    "integration_mode": "scheduled",
    "realtime_settings": {
      "enabled": false,
      "sync_on_order_confirmed": false,
      "sync_on_invoice_validated": false,
      "immediate_payment_sync": false
    },
    "scheduled_settings": {
      "enabled": true,
      "order_sync_time": "00:00",
      "invoice_sync_time": "00:00",
      "product_sync_frequency": "hourly",
      "product_sync_hour_interval": 1
    },
    "manual_execution": {
      "enabled": true,
      "allow_retry_failed": true,
      "allow_test_connection": true
    },
    "retry_policy": {
      "enabled": true,
      "max_retries": 3,
      "initial_delay_minutes": 5,
      "use_exponential_backoff": true,
      "backoff_multiplier": 2
    },
    "batch_processing": {
      "order_batch_size": 100,
      "invoice_batch_size": 100,
      "product_batch_size": 50
    },
    "notification": {
      "send_email_on_failure": true,
      "send_email_on_success": false,
      "notification_recipients": [
        "admin@example.com",
        "integration@example.com"
      ]
    },
    "logging": {
      "enable_debug_logging": false,
      "log_retention_days": 90,
      "log_request_payload": true,
      "log_response_payload": true
    },
    "api_settings": {
      "connection_timeout_seconds": 30,
      "request_timeout_seconds": 120,
      "api_rate_limit_per_minute": 60
    },
    "consolidation_rules": {
      "consolidate_orders_per_shop_per_day": true,
      "consolidate_invoices_per_shop_per_day": true,
      "aggregate_line_items": true,
      "group_by_product": true
    }
  },
  "metadata": {
    "config_version": "1.0",
    "last_updated_by": "NetSuite Admin",
    "last_updated_at": "2026-05-13T19:30:00Z",
    "netsuite_environment": "sandbox"
  }
}
```

---

### Step 4: Important - Update Credentials

**⚠️ IMPORTANT**: Replace these values with your actual Odoo credentials:

- `"db": "odoo_netsuite"` → Your actual database name
- `"login": "admin"` → Your Odoo username
- `"password": "admin"` → Your Odoo password

To find your database name:
1. Login to Odoo
2. Look at the URL: `http://localhost:8069/web?db=YOUR_DB_NAME`
3. Or go to: Settings → Technical → Database Structure → Databases

---

### Step 5: Send Request

Click **Send** button

---

## ✅ Expected Success Response

```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": 1,
  "applied_at": "2026-05-13T19:30:00.123456"
}
```

---

## ❌ Possible Error Responses

### Error 1: Authentication Failed

```json
{
  "success": false,
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid credentials"
  }
}
```

**Fix**: Check your `db`, `login`, and `password` values.

---

### Error 2: Missing Required Fields

```json
{
  "success": false,
  "error": {
    "code": "MISSING_REQUIRED_FIELDS",
    "message": "Missing required fields: db, login, password, or configuration"
  }
}
```

**Fix**: Ensure all required fields are present in the payload.

---

### Error 3: Validation Error

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid integration_mode: invalid_value. Must be realtime, scheduled, or manual"
  }
}
```

**Fix**: Check that configuration values match the allowed options.

---

## 🎛️ Configuration Options Explained

### `integration_mode`
- `"realtime"` - Sync immediately when orders are created
- `"scheduled"` - Sync at specific times (midnight)
- `"manual"` - Only sync when user clicks buttons

**Recommended**: `"scheduled"` for most use cases

---

### `retry_policy`

```json
{
  "enabled": true,
  "max_retries": 3,
  "initial_delay_minutes": 5,
  "use_exponential_backoff": true,
  "backoff_multiplier": 2
}
```

**What it does**:
- Retry failed syncs automatically
- First retry after 5 minutes
- Second retry after 10 minutes (5 × 2)
- Third retry after 20 minutes (10 × 2)

---

### `scheduled_settings`

```json
{
  "enabled": true,
  "order_sync_time": "00:00",
  "invoice_sync_time": "00:00",
  "product_sync_frequency": "hourly"
}
```

**What it does**:
- `order_sync_time`: Daily time to sync orders (HH:MM format)
- `invoice_sync_time`: Daily time to sync invoices
- `product_sync_frequency`: How often to fetch products from NetSuite

---

### `batch_processing`

```json
{
  "order_batch_size": 100,
  "invoice_batch_size": 100,
  "product_batch_size": 50
}
```

**What it does**: Limits how many records to process at once to avoid timeouts.

---

### `notification`

```json
{
  "send_email_on_failure": true,
  "send_email_on_success": false,
  "notification_recipients": ["admin@example.com"]
}
```

**What it does**: Send email alerts when syncs fail (requires Odoo email configured).

---

### `logging`

```json
{
  "enable_debug_logging": false,
  "log_retention_days": 90,
  "log_request_payload": true,
  "log_response_payload": true
}
```

**What it does**:
- `log_retention_days`: Auto-delete logs older than this many days
- `log_request_payload`: Store what was sent to NetSuite
- `log_response_payload`: Store what NetSuite responded

---

### `consolidation_rules`

```json
{
  "consolidate_orders_per_shop_per_day": true,
  "consolidate_invoices_per_shop_per_day": true,
  "aggregate_line_items": true,
  "group_by_product": true
}
```

**What it does**: Create ONE order/invoice per shop per day instead of hundreds.

---

## 🧪 Test Different Scenarios

### Scenario 1: Enable Real-Time Sync

```json
{
  "configuration": {
    "integration_mode": "realtime",
    "realtime_settings": {
      "enabled": true,
      "sync_on_order_confirmed": true,
      "sync_on_invoice_validated": true
    }
  }
}
```

---

### Scenario 2: Disable Retry

```json
{
  "configuration": {
    "retry_policy": {
      "enabled": false,
      "max_retries": 0
    }
  }
}
```

---

### Scenario 3: Increase Log Retention

```json
{
  "configuration": {
    "logging": {
      "log_retention_days": 180
    }
  }
}
```

---

## 📊 Verify Configuration in Odoo

After sending the POST request:

1. Go to **NetSuite → Configuration** in Odoo
2. You should see all the fields populated with your values
3. Example:
   - **Integration Mode**: Scheduled
   - **Max Retries**: 3
   - **Order Sync Time**: 00:00
   - **Consolidate Orders**: Yes

---

## 🔄 Update Existing Configuration

To update configuration, just send another POST request with new values. It will update the existing record, not create a new one.

---

## 💡 Tips

1. **Test with curl first**:
   ```bash
   curl -X POST http://localhost:8069/api/netsuite/config/update \
     -H "Content-Type: application/json" \
     -d @POSTMAN_CONFIG_SAMPLE.json
   ```

2. **Use Postman Environment Variables**:
   - Create variables: `{{odoo_url}}`, `{{odoo_db}}`, `{{odoo_user}}`, `{{odoo_pass}}`
   - Use in payload: `"db": "{{odoo_db}}"`

3. **Save as Collection**:
   - Save this request in a Postman collection
   - Name it "NetSuite Config Update"
   - Share with team

---

## 🚨 Security Note

**Never commit credentials to Git!**

For production:
- Use environment variables
- Use API keys instead of passwords
- Implement IP whitelisting
- Use HTTPS only

---

## 📞 Troubleshooting

**Q: Getting 404 Not Found?**
- Ensure Odoo is running: `docker-compose ps`
- Check URL is correct: `http://localhost:8069/api/netsuite/config/update`
- Verify module is installed: Go to Apps → search "netsuite"

**Q: Getting 500 Internal Server Error?**
- Check Odoo logs: `docker logs odoo_app --tail 50`
- Verify JSON is valid: Use JSONLint.com
- Check database name is correct

**Q: Configuration not showing in Odoo UI?**
- Refresh browser (Ctrl+F5)
- Check "Last Config Fetch" timestamp updated
- Go to NetSuite → Configuration

---

**Happy Testing! 🚀**
