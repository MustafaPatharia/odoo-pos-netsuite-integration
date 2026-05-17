# Mock NetSuite Storage

This directory contains JSON files capturing all requests sent from Odoo to the Mock NetSuite server.

## Directory Structure

```
storage/
├── orders/
│   ├── 2026-05-14.json
│   ├── 2026-05-15.json
│   └── 2026-05-16.json
└── invoices/
    ├── 2026-05-14.json
    ├── 2026-05-15.json
    └── 2026-05-16.json
```

## File Naming

- **Filename**: `YYYY-MM-DD.json` (transaction date from the payload)
- **Orders**: Stored in `storage/orders/`
- **Invoices**: Stored in `storage/invoices/`

## File Format

Each file contains an **array** of requests received for that date:

```json
[
  {
    "id": "12345",
    "tranId": "SO-123456",
    "recordType": "salesorder",
    "entity": "1",
    "tranDate": "2026-05-14",
    "subsidiary": 12,
    "department": 8,
    "location": 45,
    "items": [
      {
        "line": 1,
        "item": "ITEM-001",
        "quantity": 10,
        "rate": 25.50,
        "amount": 255.00
      }
    ],
    "memo": "Consolidated POS Order - Main Shop - 2026-05-14",
    "custbody_pos_shop": "Main Shop",
    "custbody_pos_date": "2026-05-14",
    "custbody_pos_order_count": 127,
    "total": 255.00,
    "createdDate": "2026-05-17T15:30:45.123Z",
    "originalRequest": { ... },
    "savedAt": "2026-05-17T15:30:45.456Z"
  }
]
```

## Generated IDs

- **id**: 5-digit random number (e.g., `12345`)
- **tranId**: `SO-XXXXXX` for orders, `INV-XXXXXX` for invoices (last 6 digits of timestamp)

## Usage for Debugging

### View All Orders for a Date

```bash
cat storage/orders/2026-05-14.json | jq
```

### Count Requests per Date

```bash
jq '. | length' storage/orders/2026-05-14.json
```

### Check NetSuite ID Assignments

```bash
jq '.[].id' storage/orders/2026-05-14.json
```

### Validate Payload Structure

```bash
jq '.[0]' storage/orders/2026-05-14.json
```

### Search for Specific Shop

```bash
jq '.[] | select(.custbody_pos_shop == "Main Shop")' storage/orders/*.json
```

## Notes

- Files are **appended** on each request (multiple requests same date = array grows)
- Each entry has `savedAt` timestamp showing when it was captured
- `originalRequest` contains the exact payload Odoo sent
- Files persist across server restarts
- Delete files manually to clear history
