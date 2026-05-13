# NetSuite Configuration JSON Schema

Based on SOW Section 4.6 - Dynamic Configuration Data Model

## Configuration Payload (NetSuite → Odoo)

```json
{
  "configuration": {
    "integration_mode": "realtime|scheduled|manual",
    "realtime_settings": {
      "enabled": true,
      "sync_on_order_confirmed": true,
      "sync_on_invoice_validated": true,
      "immediate_payment_sync": true
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
      "notification_recipients": ["admin@example.com", "integration@example.com"]
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
    "last_updated_by": "NetSuite System",
    "last_updated_at": "2026-05-13T10:30:00Z",
    "netsuite_environment": "production|sandbox"
  }
}
```

## API Endpoint Specification

### POST `/api/netsuite/config/update`

**Authentication**: Odoo Database + API Key (standard Odoo REST API)

**Headers**:
```http
Content-Type: application/json
db: odoo_database_name
login: api_user_login
password: api_user_password_or_key
```

**Request Body**: Full configuration JSON as shown above

**Response**:
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "config_id": 1,
  "applied_at": "2026-05-13T10:30:00Z"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid integration_mode value"
  }
}
```

## Configuration Fields Mapping

| SOW Field | JSON Path | Default | Description |
|-----------|-----------|---------|-------------|
| Integration Mode | `configuration.integration_mode` | `scheduled` | realtime, scheduled, or manual |
| Scheduled Frequency | `configuration.scheduled_settings.product_sync_frequency` | `hourly` | hourly, daily, or disabled |
| Manual Execution Enabled | `configuration.manual_execution.enabled` | `true` | Allow manual sync buttons |
| API Endpoint | Stored in `netsuite.config.api_url` | - | NetSuite base URL |
| Active Status | `netsuite.config.active` | `true` | Enable/disable integration |
| Notification Recipients | `configuration.notification.notification_recipients` | `[]` | Email list |
| Last Sync Timestamp | `netsuite.config.last_config_fetch` | - | Auto-updated |

## Validation Rules

1. `integration_mode` MUST be one of: `realtime`, `scheduled`, `manual`
2. `sync_time` MUST be in HH:MM format (24-hour)
3. `max_retries` MUST be between 0 and 10
4. `notification_recipients` MUST be valid email addresses
5. `log_retention_days` MUST be >= 7 and <= 365
6. If `realtime_settings.enabled = true`, then `integration_mode` should be `realtime`
7. If `scheduled_settings.enabled = true`, then `integration_mode` should be `scheduled`

## Migration from Old Config

Old fields → New fields:
- `retry_enabled` → `configuration.retry_policy.enabled`
- `max_retries` → `configuration.retry_policy.max_retries`
- `retry_delay_minutes` → `configuration.retry_policy.initial_delay_minutes`
- `hourly_sync_enabled` → `configuration.scheduled_settings.enabled`
- `end_of_day_sync_time` → `configuration.scheduled_settings.order_sync_time`
- `batch_size` → `configuration.batch_processing.order_batch_size`
