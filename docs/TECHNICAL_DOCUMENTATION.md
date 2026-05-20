# Technical Documentation
## Odoo POS ↔ Oracle NetSuite Integration

**Last Updated**: May 20, 2026
**Module Version**: 17.0.1.0.0
**Odoo Version**: 17.0
**Classification**: Technical Design Specification

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Odoo Implementation](#3-odoo-implementation)
4. [NetSuite API Endpoints](#4-netsuite-api-endpoints)
5. [Data Flows](#5-data-flows)
6. [Configuration Management](#6-configuration-management)
7. [Security & Authentication](#7-security--authentication)
8. [Error Handling & Logging](#8-error-handling--logging)
9. [Deployment Guide](#9-deployment-guide)

---

## 1. Executive Summary

### 1.1 Project Overview

The **Odoo POS ↔ NetSuite Integration** establishes a production-ready synchronization solution between Odoo Point of Sale and Oracle NetSuite ERP. The integration implements a **client-server architecture** where Odoo acts as a lightweight client and NetSuite controls all business logic.

### 1.2 Business Objectives

- **Eliminate Manual Data Entry**: Automatic synchronization of POS orders to NetSuite
- **Consolidated Financial Reporting**: One invoice per shop per day in NetSuite
- **Data Consistency**: Synchronized product catalog across both systems
- **Operational Efficiency**: Reduced API calls, faster processing
- **Flexibility**: NetSuite-controlled configuration for rapid changes

### 1.3 Key Features

✅ **Consolidated End-of-Day Invoicing**
- One invoice per shop per day in NetSuite
- Aggregated line items (sum quantities by product)
- Automatic daily sync at configurable time (default 23:59)

✅ **Hourly Product Synchronization**
- NetSuite → Odoo product catalog sync
- Automatic updates every hour
- Manual sync option available

✅ **NetSuite-Controlled Configuration**
- All business logic defined in NetSuite
- Dynamic configuration fetch via API
- No code deployment needed for config changes

✅ **Queue-Based Processing**
- Background job processing
- Automatic retry logic
- Non-blocking user interface

✅ **Comprehensive Audit Trail**
- Detailed sync logs
- Request/response payload logging (configurable)
- Performance metrics tracking

### 1.4 Integration Scope

#### Master Data Synchronization

| Data Type | Direction | Frequency | Method |
|-----------|-----------|-----------|--------|
| **Products/Items** | NetSuite → Odoo | Hourly (automatic) | REST API |
| **Payment Methods** | NetSuite → Odoo | On-demand (manual) | REST API |
| **Shop/Subsidiary Mappings** | Manual Setup | One-time | Odoo UI |

#### Transactional Data Synchronization

| Data Type | Direction | Frequency | Method |
|-----------|-----------|-----------|--------|
| **Consolidated Invoices** | Odoo → NetSuite | Daily EOD (automatic) | REST API |
| **POS Orders** | Odoo → NetSuite | Manual batch sync | REST API |

### 1.5 Technical Stack

**Odoo Platform:**
- Odoo 17.0 Community/Enterprise
- Python 3.10+
- PostgreSQL 14+
- Python `requests` library for HTTP communication

**NetSuite Platform:**
- Oracle NetSuite (SuiteScript 2.0)
- RESTlet endpoints
- OAuth 1.0 authentication
- SuiteQL for data queries

---

## 2. System Architecture

### 2.1 Architectural Pattern

**Client-Server Architecture with Configuration-as-Data**

```
┌─────────────────────────────────────────────────────────────┐
│                      ODOO (Client)                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ POS Orders │→│ Sync Queue │→│ API Client │─────┐       │
│  └────────────┘  └────────────┘  └────────────┘      │       │
│                                                        │       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐      │       │
│  │  Products  │←│ Product    │←│  Config    │      │       │
│  └────────────┘  │  Sync      │  │  Model     │      │       │
│                  └────────────┘  └────────────┘      │       │
└───────────────────────────────────────────────────────┼───────┘
                                                         │
                                                  HTTPS/REST
                                                         │
┌────────────────────────────────────────────────────────┼───────┐
│                   NETSUITE (Server)                    │       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐      │       │
│  │  RESTlet   │←─┤  Business  │  │   Config   │      │       │
│  │ Endpoints  │  │   Logic    │  │   Record   │      │       │
│  └────────────┘  └────────────┘  └────────────┘      │       │
│       ↓                ↓                                │       │
│  ┌────────────────────────────────────────────┐       │       │
│  │      NetSuite Records (Invoices, etc.)     │       │       │
│  └────────────────────────────────────────────┘       │       │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Diagram

**Odoo Components:**

```
netsuite_pos_integration/
│
├── models/
│   ├── netsuite_config.py              # Configuration model (credentials + fetched config)
│   ├── netsuite_api_client.py          # HTTP client for NetSuite API
│   ├── netsuite_consolidated_sync.py   # Order/invoice consolidation service
│   ├── netsuite_product_sync.py        # Product synchronization service
│   ├── netsuite_sync_queue.py          # Background job queue
│   ├── netsuite_sync_log.py            # Audit logging
│   ├── netsuite_mappings.py            # Shop/subsidiary mappings
│   ├── pos_order.py                    # Extended POS order model
│   └── account_move.py                 # Extended invoice model
│
├── views/
│   ├── netsuite_config_views.xml       # Configuration UI
│   ├── netsuite_sync_log_views.xml     # Sync logs UI
│   ├── netsuite_sync_queue_views.xml   # Queue management UI
│   ├── pos_order_views.xml             # Extended POS order views
│   └── product_views.xml               # Product views with NetSuite fields
│
├── data/
│   └── netsuite_cron_data.xml          # Scheduled jobs (hourly, EOD)
│
└── security/
    ├── netsuite_security.xml           # Security groups
    └── ir.model.access.csv             # Access control rules
```

### 2.3 Technology Stack Details

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Odoo Core** | Python | 3.10+ | Application framework |
| **Database** | PostgreSQL | 14+ | Data persistence |
| **HTTP Client** | Python `requests` | 2.28+ | API communication |
| **NetSuite** | SuiteScript 2.0 | - | Server-side business logic |
| **Authentication** | OAuth 1.0 | - | NetSuite API auth |

---

## 3. Odoo Implementation

### 3.1 Module Structure

**Module Manifest** (`__manifest__.py`):

```python
{
    'name': 'NetSuite POS Integration',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'depends': ['base', 'point_of_sale', 'sale', 'account'],
    'data': [
        'security/netsuite_security.xml',
        'security/ir.model.access.csv',
        'data/netsuite_cron_data.xml',
        'views/netsuite_config_views.xml',
        'views/netsuite_sync_log_views.xml',
        'views/netsuite_sync_queue_views.xml',
        'views/pos_order_views.xml',
        'views/product_views.xml',
        'views/netsuite_menu.xml',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': True,
}
```

### 3.2 Configuration Model

**File:** `models/netsuite_config.py`

**Purpose:** Store NetSuite credentials and display fetched configuration

**Key Fields:**

```python
class NetSuiteConfig(models.Model):
    _name = 'netsuite.config'
    _description = 'NetSuite Configuration'

    # === CREDENTIALS (Stored Locally) ===
    name = fields.Char(default='NetSuite Integration')
    active = fields.Boolean(default=True)
    api_url = fields.Char(help='NetSuite base URL')
    account_id = fields.Char()
    consumer_key = fields.Char()
    consumer_secret = fields.Char()
    token_id = fields.Char()
    token_secret = fields.Char()

    # === FETCHED FROM NETSUITE (Read-Only) ===
    netsuite_config = fields.Text(
        string='NetSuite Configuration JSON',
        readonly=True,
        help='Raw configuration fetched from NetSuite'
    )
    last_config_fetch = fields.Datetime(readonly=True)

    # === COMPUTED FIELDS (From netsuite_config JSON) ===
    config_integration_mode = fields.Selection([
        ('realtime', 'Real-Time'),
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual Only')
    ], compute='_compute_config_fields', store=False)

    config_hourly_sync_enabled = fields.Boolean(
        compute='_compute_config_fields', store=False
    )
    config_end_of_day_sync_time = fields.Char(
        compute='_compute_config_fields', store=False
    )
    config_max_retries = fields.Integer(
        compute='_compute_config_fields', store=False
    )
    # ... 40+ more computed fields ...
```

**Key Methods:**

```python
def fetch_netsuite_config(self):
    """Fetch configuration from NetSuite API"""
    api_client = self.env['netsuite.api.client']
    config_data = api_client.make_request(
        action='getConfig',
        payload={}
    )

    self.write({
        'netsuite_config': json.dumps(config_data),
        'last_config_fetch': fields.Datetime.now()
    })

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'message': 'Successfully fetched configuration from NetSuite',
            'type': 'success',
        }
    }

def test_connection(self):
    """Test NetSuite API connectivity"""
    try:
        api_client = self.env['netsuite.api.client']
        response = api_client.make_request(
            action='testConnection',
            payload={}
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Connection successful! NetSuite is reachable.',
                'type': 'success',
            }
        }
    except Exception as e:
        raise UserError(f'Connection failed: {str(e)}')

@api.model
def get_active_config(self):
    """Retrieve active configuration (singleton pattern)"""
    config = self.search([('active', '=', True)], limit=1)
    if not config:
        raise UserError('No active NetSuite configuration found')
    return config
```

### 3.3 API Client

**File:** `models/netsuite_api_client.py`

**Purpose:** HTTP communication layer with NetSuite

**Key Methods:**

```python
class NetSuiteApiClient(models.AbstractModel):
    _name = 'netsuite.api.client'
    _description = 'NetSuite API Client'

    @api.model
    def make_request(self, action, payload, config=None):
        """
        Generic API request method

        Args:
            action (str): API action (getConfig, createInvoice, etc.)
            payload (dict): Request payload
            config (record): NetSuite config record (optional)

        Returns:
            dict: API response data
        """
        if not config:
            config = self.env['netsuite.config'].get_active_config()

        url = f"{config.api_url}/app/site/hosting/restlet.nl?action={action}"

        headers = self._build_headers(config)

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.config_timeout_seconds or 30
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.Timeout:
            raise UserError('NetSuite request timed out')
        except requests.exceptions.ConnectionError:
            raise UserError('Cannot connect to NetSuite')
        except requests.exceptions.HTTPError as e:
            raise UserError(f'NetSuite returned error: {e.response.text}')

    def _build_headers(self, config):
        """Build HTTP headers with OAuth 1.0 authentication"""
        # For production NetSuite, implement full OAuth 1.0 signature
        return {
            'Content-Type': 'application/json',
            'Authorization': f'OAuth realm="{config.account_id}"'
            # ... full OAuth 1.0 signature generation ...
        }
```

### 3.4 Consolidated Sync Service

**File:** `models/netsuite_consolidated_sync.py`

**Purpose:** Core business logic for syncing orders/invoices to NetSuite

**Key Features:**
- Groups orders by warehouse and date
- Aggregates line items by product (sums quantities)
- Creates one consolidated invoice per group
- Handles both manual and scheduled sync

**Main Method:**

```python
@api.model
def sync_consolidated_orders(self, target_date=None, warehouse_ids=None,
                               sync_all_dates=True, sync_mode='manual'):
    """
    Sync consolidated orders to NetSuite

    Args:
        target_date (date): Specific date to sync
        warehouse_ids (list): Warehouse IDs to filter
        sync_all_dates (bool): If True, sync all past unsynced orders
        sync_mode (str): 'manual' or 'scheduled'

    Returns:
        dict: Sync results (success_count, error_count, etc.)
    """
    config = self.env['netsuite.config'].get_active_config()

    # Step 1: Find eligible orders
    orders = self._find_eligible_orders(
        target_date, warehouse_ids, sync_all_dates
    )

    if not orders:
        return {'success': True, 'message': 'No orders to sync'}

    # Step 2: Group by warehouse and date
    grouped_orders = self._group_orders(orders)

    # Step 3: Process each group
    results = {
        'total_groups': len(grouped_orders),
        'success_count': 0,
        'error_count': 0,
        'invoice_refs': []
    }

    for (warehouse_id, order_date), order_list in grouped_orders.items():
        try:
            # Consolidate orders into one invoice
            payload = self._prepare_consolidated_payload(
                order_list, warehouse_id, order_date
            )

            # Send to NetSuite
            api_client = self.env['netsuite.api.client']
            response = api_client.make_request(
                action='createInvoice',
                payload=payload,
                config=config
            )

            # Update orders
            invoice_ref = response.get('invoiceId')
            order_list.write({
                'netsuite_sync_status': 'synced',
                'netsuite_invoice_ref': invoice_ref,
                'netsuite_last_sync': fields.Datetime.now()
            })

            # Log success
            self._create_sync_log(
                order_list, payload, response, 'success'
            )

            results['success_count'] += 1
            results['invoice_refs'].append(invoice_ref)

        except Exception as e:
            # Log failure
            self._create_sync_log(
                order_list, payload, None, 'failed', error=str(e)
            )
            results['error_count'] += 1

    return results

def _prepare_consolidated_payload(self, orders, warehouse_id, order_date):
    """
    Build consolidated invoice payload

    Consolidation Logic:
    - Sum quantities for same product across all orders
    - Use earliest order time as reference
    - Include all order references in memo
    """
    # Get shop mapping
    mapping = self.env['netsuite.subsidiary.mapping'].search([
        ('warehouse_id', '=', warehouse_id)
    ], limit=1)

    if not mapping:
        raise UserError(f'No NetSuite mapping found for warehouse ID {warehouse_id}')

    # Aggregate line items
    aggregated_lines = {}
    for order in orders:
        for line in order.lines:
            product_id = line.product_id.id
            if product_id not in aggregated_lines:
                aggregated_lines[product_id] = {
                    'product': line.product_id,
                    'quantity': 0,
                    'price': line.price_unit,
                    'netsuite_item_id': line.product_id.netsuite_id
                }
            aggregated_lines[product_id]['quantity'] += line.qty

    # Build payload
    payload = {
        'subsidiary_id': mapping.netsuite_subsidiary_id,
        'trandate': order_date.strftime('%Y-%m-%d'),
        'memo': f"Consolidated POS orders: {', '.join(orders.mapped('name'))}",
        'lines': [
            {
                'item_id': data['netsuite_item_id'],
                'quantity': data['quantity'],
                'rate': data['price']
            }
            for data in aggregated_lines.values()
        ]
    }

    return payload
```

### 3.5 Product Sync Service

**File:** `models/netsuite_product_sync.py`

**Purpose:** Sync products from NetSuite to Odoo

```python
class NetSuiteProductSync(models.AbstractModel):
    _name = 'netsuite.product.sync'
    _description = 'NetSuite Product Sync Service'

    @api.model
    def sync_products_from_netsuite(self):
        """Fetch products from NetSuite and create/update in Odoo"""
        config = self.env['netsuite.config'].get_active_config()

        # Fetch products from NetSuite
        api_client = self.env['netsuite.api.client']
        response = api_client.make_request(
            action='syncItems',
            payload={}
        )

        products_data = response.get('items', [])

        results = {
            'created': 0,
            'updated': 0,
            'failed': 0
        }

        for item_data in products_data:
            try:
                product = self._create_or_update_product(item_data)
                if product.id:
                    results['updated' if product.id else 'created'] += 1
            except Exception as e:
                _logger.error(f"Failed to sync product {item_data.get('itemid')}: {str(e)}")
                results['failed'] += 1

        return results

    def _create_or_update_product(self, item_data):
        """Create or update product from NetSuite data"""
        Product = self.env['product.template']

        # Search by NetSuite ID
        netsuite_id = item_data.get('internalid')
        product = Product.search([
            ('netsuite_id', '=', netsuite_id)
        ], limit=1)

        vals = {
            'name': item_data.get('itemid'),
            'default_code': item_data.get('itemid'),
            'list_price': float(item_data.get('baseprice', 0)),
            'netsuite_id': netsuite_id,
            'netsuite_sync_status': 'synced',
            'netsuite_last_sync': fields.Datetime.now()
        }

        if product:
            product.write(vals)
        else:
            product = Product.create(vals)

        return product
```

### 3.6 Extended POS Order Model

**File:** `models/pos_order.py`

**Purpose:** Add NetSuite sync fields to POS orders

```python
class PosOrder(models.Model):
    _inherit = 'pos.order'

    netsuite_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ], string='NetSuite Sync Status', default='not_synced')

    netsuite_invoice_ref = fields.Char(
        string='NetSuite Invoice Reference',
        readonly=True
    )

    netsuite_last_sync = fields.Datetime(
        string='Last Sync Attempt',
        readonly=True
    )

    netsuite_error_message = fields.Text(
        string='Sync Error Message',
        readonly=True
    )

    def action_sync_to_netsuite(self):
        """Manual sync action for selected orders"""
        # Validate orders are from previous dates (not today)
        today = fields.Date.today()
        today_orders = self.filtered(lambda o: o.date_order.date() == today)

        if today_orders:
            raise UserError(
                "Cannot manually sync orders from today. "
                "Use end-of-day automatic sync."
            )

        # Trigger sync
        sync_service = self.env['netsuite.consolidated.sync']
        results = sync_service.sync_consolidated_orders(
            warehouse_ids=self.mapped('session_id.config_id.warehouse_id').ids,
            sync_all_dates=True,
            sync_mode='manual'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f"Sync initiated for {len(self)} order(s) "
                           f"grouped into {results['total_groups']} invoice(s)",
                'type': 'success',
            }
        }
```

### 3.7 Sync Queue Model

**File:** `models/netsuite_sync_queue.py`

**Purpose:** Queue-based background job processing with retry logic

```python
class NetSuiteSyncQueue(models.Model):
    _name = 'netsuite.sync.queue'
    _description = 'NetSuite Sync Queue'
    _order = 'create_date desc'

    model_name = fields.Char(required=True)
    record_ids = fields.Text(help='JSON array of record IDs')
    operation = fields.Selection([
        ('sync_order', 'Sync Order'),
        ('sync_invoice', 'Sync Invoice'),
        ('sync_product', 'Sync Product')
    ], required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], default='draft')

    retry_count = fields.Integer(default=0)
    max_retries = fields.Integer(default=3)
    next_retry = fields.Datetime()
    error_message = fields.Text()

    def process_queue_job(self):
        """Process a single queue job with retry logic"""
        config = self.env['netsuite.config'].get_active_config()

        try:
            self.state = 'processing'

            # Get records to process
            record_ids = json.loads(self.record_ids)
            records = self.env[self.model_name].browse(record_ids)

            # Execute operation
            if self.operation == 'sync_order':
                self._sync_orders(records)
            elif self.operation == 'sync_product':
                self._sync_products(records)

            self.state = 'done'

        except Exception as e:
            self.retry_count += 1

            if self.retry_count < config.config_max_retries:
                self.state = 'pending'
                self.next_retry = fields.Datetime.now() + timedelta(
                    minutes=config.config_retry_delay_minutes
                )
                self.error_message = str(e)
            else:
                self.state = 'failed'
                self.error_message = f"Failed after {self.retry_count} attempts: {str(e)}"
```

### 3.8 Sync Log Model

**File:** `models/netsuite_sync_log.py`

**Purpose:** Comprehensive audit trail

```python
class NetSuiteSyncLog(models.Model):
    _name = 'netsuite.sync.log'
    _description = 'NetSuite Sync Log'
    _order = 'create_date desc'

    reference = fields.Char(required=True)
    operation = fields.Selection([
        ('sync_consolidated_orders', 'Sync Consolidated Orders'),
        ('sync_consolidated_invoices', 'Sync Consolidated Invoices'),
        ('sync_products', 'Sync Products'),
        ('fetch_config', 'Fetch Configuration')
    ], required=True)

    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ], required=True)

    request_payload = fields.Text()
    response_payload = fields.Text()
    execution_time_ms = fields.Integer()
    error_details = fields.Text()

    record_count = fields.Integer()
    success_count = fields.Integer()
    failed_count = fields.Integer()
```

### 3.9 Cron Jobs

**File:** `data/netsuite_cron_data.xml`

```xml
<odoo>
    <!-- Hourly Product Sync -->
    <record id="cron_netsuite_fetch_products" model="ir.cron">
        <field name="name">NetSuite: Fetch Products Hourly</field>
        <field name="model_id" ref="model_netsuite_product_sync"/>
        <field name="state">code</field>
        <field name="code">model.sync_products_from_netsuite()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">hours</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>

    <!-- End of Day Order Sync -->
    <record id="cron_netsuite_eod_sync" model="ir.cron">
        <field name="name">NetSuite: End of Day Order Sync</field>
        <field name="model_id" ref="model_netsuite_consolidated_sync"/>
        <field name="state">code</field>
        <field name="code">model.sync_consolidated_orders(sync_all_dates=False, sync_mode='scheduled')</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="nextcall" eval="(DateTime.now() + timedelta(days=1)).replace(hour=23, minute=59)"/>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>
</odoo>
```

---

## 4. NetSuite API Endpoints

Odoo communicates with NetSuite through the following RESTlet API endpoints:

### 4.1 Configuration API

**Purpose:** Fetch all integration settings from NetSuite

**Endpoint:** `POST /app/site/hosting/restlet.nl?action=getConfig`

**Used By:** `netsuite.config.fetch_netsuite_config()` method

**Frequency:** On-demand (manual button click) or scheduled

### 4.2 Product Synchronization API

**Purpose:** Fetch product/item catalog from NetSuite

**Endpoint:** `POST /app/site/hosting/restlet.nl?action=syncItems`

**Used By:** `netsuite.product.sync.sync_products_from_netsuite()` method

**Frequency:** Hourly (automatic cron job) or on-demand

### 4.3 Invoice Creation API

**Purpose:** Post consolidated invoices to NetSuite

**Endpoint:** `POST /app/site/hosting/restlet.nl?action=createInvoice`

**Used By:** `netsuite.consolidated.sync.sync_consolidated_orders()` method

**Frequency:** Daily at end-of-day (23:59) or manual batch sync

---

## 5. Data Flows

### 5.1 End-of-Day Sync Flow

**Sequence Diagram:**

```
User/Cron → Odoo Sync Service → Odoo API Client → NetSuite → Database
    │             │                    │              │           │
    ├─ Trigger ──>│                    │              │           │
    │             ├─ Find orders       │              │           │
    │             ├─ Group by shop     │              │           │
    │             ├─ Aggregate lines   │              │           │
    │             ├─ Build payload ──>│              │           │
    │             │                    ├─ POST ──────>│           │
    │             │                    │              ├─ Create ─>│
    │             │                    │              ├<─ ID ─────┤
    │             │                    │<─ Response ──┤           │
    │             │<─ Result ──────────┤              │           │
    │             ├─ Update status     │              │           │
    │             ├─ Log result        │              │           │
    │<─ Done ─────┤                    │              │           │
```

### 5.2 Product Sync Flow

**Sequence Diagram:**

```
Cron → Odoo Product Sync → API Client → NetSuite → Odoo DB
  │           │                 │           │          │
  ├─ Hourly ─>│                 │           │          │
  │           ├─ Request ──────>│           │          │
  │           │                 ├─ GET ────>│          │
  │           │                 │<─ Items ──┤          │
  │           │<─ Products ─────┤           │          │
  │           ├─ For each item: │           │          │
  │           ├─ Search by NS ID│           │          │
  │           ├─ Create/Update ─┼───────────┼─────────>│
  │           ├─ Update status  │           │          │
  │<─ Done ───┤                 │           │          │
```

---

## 6. Configuration Management

### 6.1 Configuration Workflow

1. **Admin creates config** in Odoo (NetSuite → Configuration)
2. **Admin fills credentials** (API URL, OAuth keys)
3. **Admin clicks "Fetch Config from NetSuite"**
4. **Odoo calls NetSuite API** (getConfig action)
5. **NetSuite returns JSON** with all business logic settings
6. **Odoo stores JSON** in `netsuite_config` field
7. **Odoo computes** 50+ readonly fields from JSON
8. **Configuration used** by all sync operations

### 6.2 Configuration Fields Mapping

| NetSuite JSON Key | Odoo Computed Field | Type | Default |
|-------------------|---------------------|------|---------|
| `integration_mode` | `config_integration_mode` | Selection | scheduled |
| `hourly_sync_enabled` | `config_hourly_sync_enabled` | Boolean | True |
| `max_retries` | `config_max_retries` | Integer | 3 |
| `retry_delay_minutes` | `config_retry_delay_minutes` | Integer | 5 |
| `send_email_on_failure` | `config_send_email_on_failure` | Boolean | True |

---

## 7. Security & Authentication

### 7.1 OAuth 1.0 Authentication

**For Production NetSuite:**

```python
def _build_oauth_headers(self, config, url, method='POST'):
    oauth_params = {
        'oauth_consumer_key': config.consumer_key,
        'oauth_token': config.token_id,
        'oauth_signature_method': 'HMAC-SHA256',
        'oauth_timestamp': str(int(time.time())),
        'oauth_nonce': base64.b64encode(os.urandom(32)).decode('utf-8'),
        'oauth_version': '1.0'
    }

    # Build base string
    base_string = f"{method}&{quote(url, safe='')}&{quote(param_string, safe='')}"

    # Generate signature
    signing_key = f"{quote(config.consumer_secret, safe='')}&{quote(config.token_secret, safe='')}"
    signature = hmac.new(
        signing_key.encode(),
        base_string.encode(),
        hashlib.sha256
    ).digest()
    oauth_params['oauth_signature'] = base64.b64encode(signature).decode()

    # Build Authorization header
    auth_header = 'OAuth ' + ', '.join([
        f'{k}="{quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    ])

    return {'Authorization': auth_header}
```

### 7.2 Access Control

**Security Groups:**

```xml
<record id="group_netsuite_user" model="res.groups">
    <field name="name">NetSuite User</field>
    <field name="comment">Can view sync logs and status</field>
</record>

<record id="group_netsuite_manager" model="res.groups">
    <field name="name">NetSuite Manager</field>
    <field name="implied_ids" eval="[(4, ref('group_netsuite_user'))]"/>
    <field name="comment">Can configure and trigger syncs</field>
</record>
```

**Access Rights** (`ir.model.access.csv`):

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_netsuite_config_user,netsuite.config.user,model_netsuite_config,group_netsuite_user,1,0,0,0
access_netsuite_config_manager,netsuite.config.manager,model_netsuite_config,group_netsuite_manager,1,1,1,0
access_netsuite_sync_log_user,netsuite.sync.log.user,model_netsuite_sync_log,group_netsuite_user,1,0,0,0
```

---

## 8. Error Handling & Logging

### 8.1 Error Categories & Handling

| Error Type | Retry? | Notification | Action |
|------------|--------|--------------|--------|
| **Network Timeout** | Yes (3x) | On final failure | Log + Email |
| **500 Server Error** | Yes (3x) | On final failure | Log + Email |
| **401 Auth Error** | No | Immediate | Critical Alert |
| **400 Bad Request** | No | Immediate | Log + Email |
| **Invalid Data** | No | Immediate | Log + Mark Failed |

### 8.2 Logging Strategy

**Sync Log Fields:**

```python
sync_log = self.env['netsuite.sync.log'].create({
    'reference': f"EOD-{order_date}",
    'operation': 'sync_consolidated_orders',
    'status': 'success',
    'request_payload': json.dumps(payload) if config.log_request else None,
    'response_payload': json.dumps(response) if config.log_response else None,
    'execution_time_ms': duration_ms,
    'record_count': len(orders),
    'success_count': len(orders),
    'failed_count': 0
})
```

---

## 9. Deployment Guide

### 9.1 Production Deployment

**Prerequisites:**
- NetSuite account with RESTlet deployment
- OAuth 1.0 credentials generated
- Odoo 17.0 production instance

**Steps:**

1. **Deploy RESTlet to NetSuite**
   - Upload SuiteScript file
   - Deploy as RESTlet
   - Note deployment URL

2. **Install Odoo Module**
   ```bash
   # Copy module to addons
   cp -r netsuite_pos_integration /opt/odoo/addons/

   # Upgrade module
   odoo --update=netsuite_pos_integration -d production_db
   ```

3. **Configure in Odoo**
   - Navigate to NetSuite → Configuration
   - Enter production API URL
   - Add OAuth credentials
   - Fetch configuration
   - Test connection

4. **Setup Shop Mappings**
   - Create subsidiary mappings for all warehouses

5. **Enable Cron Jobs**
   - Verify cron jobs are active
   - Test manual execution first

---

---

## Conclusion

This Odoo module provides a **production-ready integration** with NetSuite ERP for Point of Sale systems. The implementation focuses on:

**Key Implementation Features:**
- **Modular Architecture**: Clean separation of concerns with dedicated models for sync, configuration, logging, and queue management
- **Consolidated Invoicing**: Reduces API calls by aggregating orders per shop per day
- **Queue-Based Processing**: Non-blocking background jobs with automatic retry
- **Comprehensive Audit Trail**: Full sync logs with configurable payload logging
- **NetSuite-Controlled Configuration**: Dynamic business logic changes without code deployment
- **Extensible Design**: Easy to add new sync operations or custom fields

**Odoo Module Components:**
- Configuration model with computed fields from NetSuite
- API client with OAuth 1.0 authentication
- Consolidated sync service for orders/invoices
- Product sync service for catalog updates
- Queue model for background processing
- Sync log model for audit trail
- Extended POS order and product models
- Automated cron jobs for scheduled sync

**For more details, see:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design patterns
- [QUICK_START.md](QUICK_START.md) - Setup and configuration guide
- `Implementation/` folder - Feature-specific implementation guides
