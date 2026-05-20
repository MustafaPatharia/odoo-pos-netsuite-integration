# NetSuite Configuration Setup

## API Endpoint

**POST** `http://localhost:8069/api/netsuite/config/update`

Updates the NetSuite integration configuration in Odoo.

---

## Authentication

**Header Required:**
```
X-API-Key: <your_odoo_api_key>
Content-Type: application/json
```

---

## Request Body Structure

```json
{
  "configuration": { ... },
  "metadata": { ... }
}
```

---

## Configuration Properties

### `integration_mode`
**Type:** `string` | **Required:** Yes

**Valid Values:**
- `"realtime"` - Immediate sync when events occur
- `"scheduled"` - Sync at scheduled times
- `"manual"` - Manual sync only

---

### `realtime_settings`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `enabled` | boolean | `true` \| `false` | `false` |
| `sync_on_order_confirmed` | boolean | `true` \| `false` | `false` |
| `sync_on_invoice_validated` | boolean | `true` \| `false` | `false` |
| `immediate_payment_sync` | boolean | `true` \| `false` | `false` |

---

### `scheduled_settings`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `enabled` | boolean | `true` \| `false` | `true` |
| `order_sync_time` | string | `"HH:MM"` (00:00 - 23:59) | `"00:00"` |
| `invoice_sync_time` | string | `"HH:MM"` (00:00 - 23:59) | `"00:00"` |
| `product_sync_frequency` | string | `"hourly"` \| `"daily"` \| `"weekly"` | `"hourly"` |
| `product_sync_hour_interval` | integer | `1` to `24` | `1` |

---

### `manual_execution`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `enabled` | boolean | `true` \| `false` | `true` |
| `allow_retry_failed` | boolean | `true` \| `false` | `true` |
| `allow_test_connection` | boolean | `true` \| `false` | `true` |

---

### `retry_policy`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `enabled` | boolean | `true` \| `false` | `true` |
| `max_retries` | integer | `0` to `10` | `3` |
| `initial_delay_minutes` | integer | `1` to `60` | `5` |
| `use_exponential_backoff` | boolean | `true` \| `false` | `true` |
| `backoff_multiplier` | integer | `1` to `5` | `2` |

---

### `batch_processing`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `product_batch_size` | integer | `1` to `200` | `50` |

---

### `notification`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `send_email_on_failure` | boolean | `true` \| `false` | `true` |
| `send_email_on_success` | boolean | `true` \| `false` | `false` |
| `notification_recipients` | array[string] | Valid email addresses | `[]` |

---

### `logging`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `enable_debug_logging` | boolean | `true` \| `false` | `false` |
| `log_retention_days` | integer | `7` to `365` | `90` |
| `log_request_payload` | boolean | `true` \| `false` | `true` |
| `log_response_payload` | boolean | `true` \| `false` | `true` |

---

### `api_settings`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `connection_timeout_seconds` | integer | `5` to `120` | `30` |
| `request_timeout_seconds` | integer | `30` to `600` | `120` |
| `api_rate_limit_per_minute` | integer | `10` to `300` | `60` |

---

### `consolidation_rules`
**Type:** `object`

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `consolidate_orders_per_shop_per_day` | boolean | `true` \| `false` | `true` |
| `consolidate_invoices_per_shop_per_day` | boolean | `true` \| `false` | `true` |

---

## Metadata Properties

| Property | Type | Valid Values | Default |
|----------|------|--------------|---------|
| `config_version` | string | Any version string | `"1.0"` |
| `last_updated_by` | string | Any username/identifier | `"NetSuite System"` |
| `last_updated_at` | string | ISO 8601 datetime | Current timestamp |
| `netsuite_environment` | string | `"production"` \| `"sandbox"` | `"production"` |

---

## Response

### Success (200 OK)
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": 4,
  "applied_at": "2026-05-18T15:22:07"
}
```

### Errors

| Status | Code | Message |
|--------|------|---------|
| 401 | `MISSING_API_KEY` | Missing X-API-Key header |
| 401 | `INVALID_API_KEY` | Invalid or expired API key |
| 400 | `INVALID_JSON` | Invalid JSON payload |
| 400 | `MISSING_REQUIRED_FIELDS` | Missing required field: configuration |
| 400 | `VALIDATION_ERROR` | Validation error details |
| 404 | `NO_CONFIG_FOUND` | No active configuration found |
| 500 | `INTERNAL_ERROR` | Error details |

---

## Example Request

```bash
curl -X POST http://localhost:8069/api/netsuite/config/update \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
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
      "consolidate_invoices_per_shop_per_day": true
    }
  },
  "metadata": {
    "config_version": "1.0",
    "last_updated_by": "NetSuite Admin",
    "last_updated_at": "2026-05-18T15:22:07Z",
    "netsuite_environment": "sandbox"
  }
}'
```

---

## Validation Rules

- `retry_policy.max_retries`: `0` to `10`
- `logging.log_retention_days`: `7` to `365`
- `scheduled_settings.order_sync_time`: `HH:MM` format (00:00 - 23:59)
- `scheduled_settings.invoice_sync_time`: `HH:MM` format (00:00 - 23:59)
- `notification.notification_recipients`: Array of valid email addresses

---

## Notes

1. **Pre-requisite:** NetSuite configuration with credentials must exist in Odoo before calling this API
2. **API Key:** Generate in Odoo: Settings → Users → Technical Settings → API Keys
3. **Idempotent:** Multiple calls with same payload update configuration each time
4. **Storage:** Configuration stored as JSON in `netsuite.config.netsuite_config` field
