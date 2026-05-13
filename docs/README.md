# Odoo POS - NetSuite Integration

Sync Odoo Point of Sale orders with NetSuite ERP automatically.

## Overview

This module creates **one consolidated invoice per shop per day** in NetSuite instead of syncing individual orders. All business logic and configuration are managed by NetSuite - Odoo only stores credentials.

### Key Features
- ✅ End-of-day consolidated invoicing (one invoice per shop)
- ✅ Hourly product/item synchronization
- ✅ Automated cron jobs (hourly items, daily invoices)
- ✅ Manual batch sync from UI
- ✅ Complete audit logging
- ✅ Mock NetSuite server for testing

## Architecture

**Simple Client-Server Pattern:**
- **Odoo (Client)**: Stores only NetSuite credentials, fetches configuration from NetSuite
- **NetSuite (Server)**: Contains all business logic, retry policies, and sync rules
- **Mock Server**: Simulates NetSuite RESTlets for development/testing

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## Quick Start

### 1. Start the System

```bash
git clone https://github.com/MustafaPatharia/odoo-pos-netsuite-integration.git
cd odoo-pos-netsuite-integration
docker-compose up -d
```

Services:
- **Odoo**: http://localhost:8069 (admin / admin)
- **Mock NetSuite**: http://localhost:3000
- **PostgreSQL**: localhost:5432

### 2. Install Module

1. Log into Odoo → Apps
2. Search "NetSuite POS Integration"
3. Click **Install**

### 3. Configure

1. Go to **NetSuite → Configuration**
2. Set **API URL**: `http://host.docker.internal:3000` (uses mock server)
3. Add NetSuite credentials (or use defaults for testing)
4. Click **Fetch Config from NetSuite** (loads settings from NetSuite)
5. Click **Test Connection**

## How It Works

### End-of-Day Sync
1. POS orders accumulate throughout the day
2. At 23:59 (configurable), cron creates **one consolidated invoice per shop**
3. Invoice sent to NetSuite with all orders for that shop that day

### Manual Batch Sync
1. Go to **Point of Sale → Orders**
2. Select orders from previous days (not today)
3. **Action → Sync to NetSuite**
4. Creates one invoice per (shop, date) combination

### Hourly Item Sync
- Automatically syncs product/item changes every hour
- Keeps product catalog in sync

## Configuration

All business logic is controlled by NetSuite configuration (fetched via "Fetch Config"):
- Retry policy (enabled, max retries, delay)
- Batch size
- Email notifications
- Sync schedules
- Timeout settings
- Debug logging

Odoo only stores credentials; NetSuite controls the rules.

## Monitoring

- **NetSuite → Sync Logs**: View all sync attempts (success/failed)
- **Point of Sale → Orders**: Check NetSuite sync status column
- **Mock Server Console**: See incoming requests during testing

## Development

### Mock Server Testing

```bash
cd mock-netsuite-server
npm install
npm start

# Test endpoints
curl http://localhost:3000/health
curl http://localhost:3000/admin/orders
```

### Module Development

```bash
# Upgrade module after changes
docker exec odoo_app odoo --stop-after-init -u netsuite_pos_integration -d odoo_netsuite --no-http

# View logs
docker logs -f odoo_app
```

## Files

| File | Purpose |
|------|---------|
| `README.md` | Quick start guide (this file) |
| `ARCHITECTURE.md` | Detailed technical architecture |
| `SETUP_GUIDE.md` | Comprehensive setup instructions |
| `addons/netsuite_pos_integration/` | Odoo module code |
| `mock-netsuite-server/` | Mock NetSuite RESTlet server |

## Support

- **GitHub Issues**: https://github.com/MustafaPatharia/odoo-pos-netsuite-integration/issues
- **Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) and [SETUP_GUIDE.md](SETUP_GUIDE.md)

## License

LGPL-3
