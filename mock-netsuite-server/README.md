# Mock NetSuite Server

Mock implementation of NetSuite RESTlet API for testing Odoo integration.

## Features

- Sales Order creation/update
- Customer management
- Payment processing
- Batch operations
- Sync logging
- Health monitoring

## API Endpoints

### Health Check
\`\`\`
GET /health
\`\`\`

### Sales Orders
\`\`\`
POST /api/salesorder
GET /api/salesorder/:id
PUT /api/salesorder/:id
\`\`\`

### Customers
\`\`\`
POST /api/customer
\`\`\`

### Payments
\`\`\`
POST /api/payment
\`\`\`

### Batch Operations
\`\`\`
POST /api/batch
\`\`\`

### Sync Logs
\`\`\`
GET /api/sync-logs?limit=100&operation=CREATE_SALES_ORDER
\`\`\`

### Reset (Testing)
\`\`\`
POST /api/reset
\`\`\`

## Running Locally

\`\`\`bash
npm install
npm start
\`\`\`

Server runs on port 3000 by default.

## Docker

Built automatically with docker-compose:
\`\`\`bash
docker-compose up mock-netsuite
\`\`\`

## Example Usage

\`\`\`bash
# Create sales order
curl -X POST http://localhost:3000/api/salesorder \\
  -H "Content-Type: application/json" \\
  -d '{
    "entity": "1",
    "items": [{"item": "Product", "quantity": 1, "rate": 100}]
  }'

# View logs
curl http://localhost:3000/api/sync-logs
\`\`\`
