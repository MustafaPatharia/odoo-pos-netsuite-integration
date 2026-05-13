# NetSuite Integration Architecture

## ✅ Simplified Enterprise Architecture

### Design Principles

**Odoo is a DUMB CLIENT** - Only stores credentials and sends data
**NetSuite is the BRAIN** - Controls all business logic, retry policies, schedules, etc.

---

## 🏗️ Component Responsibilities

### ODOO (Client Side)

**Stores:**
- Account ID
- OAuth Credentials (Consumer Key/Secret, Token ID/Secret)
- API URL

**Does:**
1. **Fetches configuration** from NetSuite via GET API
2. **Runs TWO fixed cron jobs:**
   - **Hourly**: Sync items/products
   - **End of Day**: Sync ALL invoices in ONE batch
3. **Sends data** to NetSuite
4. **Logs responses** for audit trail
5. **Shows UI views** of sync status

**Does NOT:**
- Make decisions about retry logic
- Decide when to sync
- Store complex configuration
- Implement business rules

---

### NetSuite (Server Side)

**Controls:**
- Retry logic (how many times, when)
- Email notifications
- Sync schedules (can override Odoo's default)
- Batch sizes
- Error handling policies
- Everything else!

**Provides:**
- Configuration API endpoint (`/app/site/hosting/restlet.nl?action=getConfig`)
- Data reception endpoints
- Business logic execution
- Success/failure responses

---

## 📋 Two Fixed Sync Patterns

### 1. HOURLY ITEM SYNC

**Cron Schedule:** Every hour
**Purpose:** Sync products/items catalog
**Payload:** All modified items since last sync

```python
# Runs hourly
def sync_items_hourly():
    config = get_netsuite_config()
    items = get_modified_items_since_last_sync()
    send_to_netsuite(items)
```

### 2. END OF DAY INVOICE SYNC

**Cron Schedule:** Daily at 11:59 PM
**Purpose:** Sync all finalized invoices from the entire day
**Payload:** ONE batch containing ALL invoices

```python
# Runs at end of day
def sync_end_of_day_invoices():
    config = get_netsuite_config()
    invoices = get_all_paid_invoices_for_today()
    send_to_netsuite_as_single_batch(invoices)
```

**Important:** This sends all invoices in ONE request, not per-record!

---

## 🔄 API Flow

###GET Configuration from NetSuite

```
Odoo                              NetSuite
  │                                  │
  ├──── GET /restlet.nl?action=getConfig ───→ │
  │                                  │
  │ ←─── Return Configuration JSON ──┤
  │                                  │
  ├─ Store in netsuite_config field  │
  │                                  │
```

**Configuration Response Example:**
```json
{
  "retry_enabled": true,
  "max_retries": 3,
  "retry_delay_minutes": 5,
  "send_email_on_failure": true,
  "batch_size": 100,
  "hourly_sync_enabled": true,
  "end_of_day_sync_time": "23:59"
}
```

### POST Data to NetSuite

```
Odoo                              NetSuite
  │                                  │
  ├─ POST /restlet.nl?action=sync ──→ │
  │   Payload: { invoices: [...] }   │
  │                                  │
  │                                  ├─ Validates
  │                                  ├─ Processes
  │                                  ├─ Applies retry logic
  │                                  ├─ Sends email if needed
  │                                  │
  │ ←─── Success/Failure Response ───┤
  │                                  │
  ├─ Log result                      │
  │                                  │
```

---

## 📊 Data Models

### Odoo: netsuite.config

```python
{
    'name': 'NetSuite Integration',
    'api_url': 'http://localhost:3000',
    'account_id': 'TSTDRV123456',
    'consumer_key': '***',
    'consumer_secret': '***',
    'token_id': '***',
    'token_secret': '***',
    'netsuite_config': '{"retry_enabled": true, ...}',  # Fetched from NetSuite
    'last_config_fetch': '2024-01-15 10:00:00'
}
```

### Odoo: Sync Logs (Audit Only)

```python
{
    'reference': 'POS/2024/001',
    'status': 'success',
    'operation': 'sync_invoice',
    'request_payload': '{...}',
    'response_payload': '{...}',
    'execution_time_ms': 250
}
```

---

## 🎯 Key Points

1. **No complex business logic in Odoo** - Just send and log
2. **NetSuite controls everything** - Retry, email, schedules
3. **Two fixed jobs** - Hourly items, end of day invoices
4. **One API call for config** - GET configuration from NetSuite
5. **Clean separation** - Client vs Server responsibilities
6. **Audit trail** - Odoo logs everything but doesn't decide

---

## 🚀 Benefits

✅ **Simple Odoo code** - Easy to maintain
✅ **Centralized control** - All logic in NetSuite
✅ **Flexible** - Change retry logic without updating Odoo
✅ **Scalable** - Batch processing at end of day
✅ **Auditable** - Complete logs in Odoo
✅ **Testable** - Mock NetSuite server can simulate responses

---

## 🔧 Configuration in Odoo UI

Odoo admin only needs to configure:

```
NetSuite Configuration
━━━━━━━━━━━━━━━━━━━━
API URL: http://localhost:3000
Account ID: TSTDRV123456
Consumer Key: ********
Consumer Secret: ********
Token ID: ********
Token Secret: ********

[Test Connection] [Fetch Configuration]

NetSuite Configuration (Read-only):
{
  "retry_enabled": true,
  "max_retries": 3,
  ...
}
```

**That's it!** Everything else is controlled by NetSuite.
