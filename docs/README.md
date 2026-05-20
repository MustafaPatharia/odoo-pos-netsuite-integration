# Odoo POS - NetSuite Integration

Enterprise-grade integration between Odoo Point of Sale and Oracle NetSuite ERP.

## Overview

This module provides seamless synchronization between Odoo POS and NetSuite, supporting **consolidated daily invoicing**, **real-time product sync**, and **flexible configuration** managed through NetSuite.

### Key Features

- ✅ **Consolidated End-of-Day Invoicing** - One invoice per shop per day in NetSuite
- ✅ **Hourly Product Synchronization** - Automatic product catalog sync from NetSuite
- ✅ **NetSuite-Controlled Configuration** - All business logic managed in NetSuite
- ✅ **Manual Batch Operations** - Sync selected orders on-demand
- ✅ **Complete Audit Trail** - Detailed sync logs and status tracking
- ✅ **Queue-Based Processing** - Background job processing with retry logic
- ✅ **Mock NetSuite Server** - Full testing environment included

## Architecture

**Client-Server Design Pattern:**

- **Odoo (Client)**: Lightweight data sender - stores only credentials and executes sync operations
- **NetSuite (Server)**: Business logic controller - manages retry policies, schedules, and configuration
- **Mock Server**: Development/testing environment simulating NetSuite RESTlet APIs

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture diagrams and component details.

## Quick Start

### 1. Start the Environment

```bash
git clone https://github.com/MustafaPatharia/odoo-pos-netsuite-integration.git
cd odoo-pos-netsuite-integration
docker-compose up -d
```

**Services:**
- **Odoo Web UI**: http://localhost:8069 (admin / admin)
- **Mock NetSuite API**: http://localhost:3000
- **PostgreSQL Database**: localhost:5432

### 2. Install the Module

1. Log into Odoo → **Apps**
2. Search for **"NetSuite POS Integration"**
3. Click **Install**
4. Wait for installation to complete

### 3. Configure Integration

1. Navigate to **NetSuite → Configuration**
2. Set **API URL**: `http://host.docker.internal:3000` (for mock server)
3. Enter NetSuite credentials (or use defaults for testing)
4. Click **"Fetch Config from NetSuite"** - loads all settings from NetSuite
5. Click **"Test Connection"** - verify connectivity

See [Quick Start Guide](QUICK_START.md) for detailed step-by-step setup instructions.

## How It Works

### End-of-Day Consolidated Invoicing

1. **Throughout the Day**: POS orders are created and marked as paid in Odoo
2. **23:59 Daily** (configurable): Automated cron job triggers
3. **Consolidation**: System groups orders by shop and creates one invoice per shop
4. **NetSuite Sync**: Consolidated invoice sent to NetSuite with aggregated line items
5. **Status Update**: Orders marked as synced with NetSuite invoice reference

### Manual Batch Sync

1. Navigate to **Point of Sale → Orders**
2. Select multiple orders from **previous dates** (not today)
3. **Action → Sync Selected to NetSuite**
4. System creates one invoice per **(shop, date)** combination
5. View results in **NetSuite → Sync Logs**

### Hourly Product Sync

- **Automatic**: Runs every hour via cron job
- **Purpose**: Syncs product catalog from NetSuite to Odoo
- **Updates**: Product name, code, price, NetSuite ID mapping
- **Manual**: Also available via **Products → Action → Sync from NetSuite**

## Configuration Management

All business logic is **controlled by NetSuite** (not hardcoded in Odoo):

- ✅ Retry policies (enabled, max attempts, delay)
- ✅ Batch processing size
- ✅ Email notification settings
- ✅ Sync schedules and timing
- ✅ Timeout configurations
- ✅ Debug logging levels

**Odoo's Role**: Store credentials, fetch configuration, execute sync operations

**NetSuite's Role**: Define all business rules, retry logic, and integration behavior

## Monitoring & Troubleshooting

### Sync Logs
**NetSuite → Sync Logs**: View all sync attempts with timestamps, status, and error details

### Order Status
**Point of Sale → Orders**: Check **NetSuite Sync Status** column for each order

### Queue Status
**NetSuite → Sync Queue**: Monitor background jobs and retry attempts

### Mock Server Logs
View console output when using mock server for development/testing

## Development & Testing

### Mock Server Setup

```bash
cd mock-netsuite-server
npm install
npm start
```

**Test Health Check:**
```bash
curl http://localhost:3000/health
curl http://localhost:3000/admin/orders
```

**Mock API Endpoints:**
- `GET /health` - Health check
- `POST /app/site/hosting/restlet.nl?action=getConfig` - Get configuration
- `POST /app/site/hosting/restlet.nl?action=createInvoice` - Create consolidated invoice
- `POST /app/site/hosting/restlet.nl?action=syncItems` - Sync products
- `GET /admin/orders` - View stored orders (admin UI)

### Module Development

```bash
# Upgrade module after code changes
docker exec odoo_app odoo --stop-after-init -u netsuite_pos_integration -d odoo_netsuite --no-http

# Restart Odoo service
docker-compose restart odoo_app

# View live logs
docker logs -f odoo_app
```

### Creating Test Data

```bash
# Create test POS orders
python3 create_test_orders.py
```

## Documentation Structure

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Overview and quick start (this file) |
| [QUICK_START.md](QUICK_START.md) | Step-by-step setup and testing guide |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design patterns |
| [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) | Detailed technical specifications |
| [Implementation/](Implementation/) | Implementation guides for specific features |

## Module Files

| Path | Description |
|------|-------------|
| `addons/netsuite_pos_integration/` | Main Odoo module |
| `addons/netsuite_pos_integration/models/` | Data models and business logic |
| `addons/netsuite_pos_integration/views/` | UI views and menus |
| `addons/netsuite_pos_integration/security/` | Access control rules |
| `addons/netsuite_pos_integration/data/` | Cron jobs and initial data |
| `mock-netsuite-server/` | Mock NetSuite server for testing |
| `diagrams/` | System architecture diagrams (Mermaid) |

## Troubleshooting

### Connection Issues
- Verify mock server is running on port 3000
- Check API URL uses `host.docker.internal` (not `localhost`)
- Test connection with curl from within Docker container

### Sync Failures
- Check **NetSuite → Sync Logs** for error details
- Verify shop/subsidiary mapping exists
- Ensure orders are from previous dates (not today for manual sync)
- Review configuration settings fetched from NetSuite

### Product Sync Issues
- Verify NetSuite returns valid product data
- Check **Products → NetSuite Sync Status** field
- View sync logs for error details
- Manually trigger sync via **Action → Sync from NetSuite**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with mock server
5. Submit a pull request

## Support

- **GitHub Issues**: https://github.com/MustafaPatharia/odoo-pos-netsuite-integration/issues
- **Documentation**: See all docs in `docs/` folder
- **Architecture Diagrams**: See `diagrams/` folder

## License

LGPL-3
