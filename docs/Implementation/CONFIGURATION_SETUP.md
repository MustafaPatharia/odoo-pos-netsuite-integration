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
- `"realtime"` - Immediate 1:1 sync when events occur (no consolidation)
- `"scheduled"` - Sync at scheduled times (respects consolidation flag)
- `"manual"` - Manual sync only (respects consolidation flag)


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

### `consolidation_rules`
**Type:** `object`

| Property | Type | Valid Values | Default | Notes |
|----------|------|--------------|---------|-------|
| `consolidate_orders` | boolean | `true` \| `false` | `true` | N:1 if true, 1:1 if false. Must be false in realtime mode. |
| `consolidate_invoices` | boolean | `true` \| `false` | `true` | N:1 if true, 1:1 if false. Must be false in realtime mode. |

**Behavior:**
- `true`: Consolidate multiple records into one (N:1)
- `false`: Send each record individually (1:1)
- **Realtime mode**: Must be `false` (validation enforced)
- **Scheduled/Manual modes**: Can be `true` or `false`

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

### Scheduled Mode (Consolidated Sync at EOD)
```bash
curl -X POST http://localhost:8069/api/netsuite/config/update \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
  "configuration": {
    "integration_mode": "scheduled",
    "scheduled_settings": {
      "enabled": true,
      "order_sync_time": "00:00",
      "invoice_sync_time": "00:00",
      "product_sync_frequency": "hourly",
      "product_sync_hour_interval": 1
    },
    "consolidation_rules": {
      "consolidate_orders": true,
      "consolidate_invoices": true
    },
    "retry_policy": {
      "enabled": true,
      "max_retries": 3,
      "initial_delay_minutes": 5,
      "use_exponential_backoff": true,
      "backoff_multiplier": 2
    },
    "logging": {
      "enable_debug_logging": false,
      "log_retention_days": 90,
      "log_request_payload": true,
      "log_response_payload": true
    }
  }
}'
```

### Real-Time Mode (Immediate 1:1 Sync)
```bash
curl -X POST http://localhost:8069/api/netsuite/config/update \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
  "configuration": {
    "integration_mode": "realtime",
    "consolidation_rules": {
      "consolidate_orders": false,
      "consolidate_invoices": false
    },
    "retry_policy": {
      "enabled": true,
      "max_retries": 3,
      "initial_delay_minutes": 5,
      "use_exponential_backoff": true,
      "backoff_multiplier": 2
    }
  }
}'
```

**Note:** In realtime mode, both orders and invoices sync immediately (1:1) when created/confirmed. No need to set granular flags.

---

## Validation Rules

- `retry_policy.max_retries`: `0` to `10`
- `logging.log_retention_days`: `7` to `365`
- `scheduled_settings.order_sync_time`: `HH:MM` format (00:00 - 23:59)
- `scheduled_settings.invoice_sync_time`: `HH:MM` format (00:00 - 23:59)
- `notification.notification_recipients`: Array of valid email addresses
- **Real-time mode constraint**: `consolidate_orders` and `consolidate_invoices` must be `false`

**Deprecated Fields (Kept for Backward Compatibility):**
- `realtime_settings.sync_on_order_confirmed` - Not used in sync logic
- `realtime_settings.sync_on_invoice_validated` - Not used in sync logic
- `realtime_settings.enabled` - Use `integration_mode` instead

---

## Notes

1. **Pre-requisite:** NetSuite configuration with credentials must exist in Odoo before calling this API
2. **API Key:** Generate in Odoo: Settings → Users → Technical Settings → API Keys
3. **Idempotent:** Multiple calls with same payload update configuration each time
4. **Storage:** Configuration stored as JSON in `netsuite.config.netsuite_config` field

### Sync Behavior by Mode

**Realtime Mode (`integration_mode: "realtime"`):**
- Orders sync immediately when state changes to paid/done/invoiced (1:1)
- Invoices sync immediately when posted (1:1)
- `consolidate_orders` and `consolidate_invoices` must be `false`

**Scheduled Mode (`integration_mode: "scheduled"`):**
- Orders sync at configured `order_sync_time` (EOD)
- Invoices sync at configured `invoice_sync_time` (EOD)
- Supports consolidation (N:1) if enabled

**Manual Mode (`integration_mode: "manual"`):**
- No automatic sync
- User must trigger sync manually from Odoo UI
