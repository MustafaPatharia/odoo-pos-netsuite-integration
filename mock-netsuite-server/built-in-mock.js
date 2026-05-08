const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const morgan = require('morgan');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));
app.use(bodyParser.urlencoded({ extended: true }));
app.use(morgan('dev'));

// In-memory storage for mock NetSuite data
const mockDatabase = {
  salesOrders: new Map(),
  customers: new Map(),
  items: new Map(),
  payments: new Map(),
  syncLogs: []
};

// Initialize some mock data
mockDatabase.customers.set('1', {
  internalId: '1',
  entityId: 'CUST-001',
  companyName: 'Default Customer',
  email: 'customer@example.com',
  externalId: 'ODOO-CUST-001'
});

mockDatabase.items.set('1', {
  internalId: '1',
  itemId: 'PROD-001',
  displayName: 'Sample Product',
  basePrice: 100.00
});

// Helper function to log sync operations
function logSync(operation, status, data, error = null) {
  const log = {
    id: uuidv4(),
    timestamp: new Date().toISOString(),
    operation,
    status,
    data: JSON.stringify(data).substring(0, 500),
    error
  };
  mockDatabase.syncLogs.push(log);
  console.log(`[SYNC LOG] ${operation} - ${status}`, error || '');
  return log;
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'Mock NetSuite Server',
    version: '1.0.0'
  });
});

// NetSuite RESTlet endpoint - Sales Order Creation
app.post('/app/site/hosting/restlet.nl', (req, res) => {
  try {
    const { script, deploy, action } = req.query;
    const payload = req.body;

    console.log('\n=== Incoming NetSuite Request ===');
    console.log('Action:', action);
    console.log('Payload:', JSON.stringify(payload, null, 2));

    // Route based on action
    switch (action) {
      case 'createSalesOrder':
        return handleCreateSalesOrder(req, res, payload);
      case 'createCustomer':
        return handleCreateCustomer(req, res, payload);
      case 'createPayment':
        return handleCreatePayment(req, res, payload);
      case 'getStatus':
        return handleGetStatus(req, res, payload);
      default:
        return res.status(400).json({
          success: false,
          error: `Unknown action: ${action}`
        });
    }
  } catch (error) {
    console.error('Error processing request:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Handle Sales Order Creation
function handleCreateSalesOrder(req, res, payload) {
  try {
    // Validate required fields
    if (!payload.entity || !payload.items || !Array.isArray(payload.items)) {
      logSync('CREATE_SALES_ORDER', 'failed', payload, 'Missing required fields');
      return res.status(400).json({
        error: {
          code: 'INVALID_REQUEST',
          message: 'Missing required fields: entity and items are required'
        }
      });
    }

    // Generate NetSuite internal ID
    const internalId = uuidv4();
    const tranId = `SO-${Date.now()}`;

    // Create sales order record
    const salesOrder = {
      id: internalId,
      tranId: tranId,
      entity: orderData.entity,
      tranDate: orderData.tranDate || new Date().toISOString().split('T')[0],
      currency: orderData.currency || 'USD',
      status: orderData.status || 'Pending Fulfillment',
      items: orderData.items.map((item, index) => ({
        line: index + 1,
        item: item.item,
        quantity: item.quantity || 1,
        rate: item.rate || 0,
        amount: (item.quantity || 1) * (item.rate || 0),
        description: item.description || ''
      })),
      subTotal: orderData.items.reduce((sum, item) =>
        sum + ((item.quantity || 1) * (item.rate || 0)), 0),
      total: orderData.total || orderData.items.reduce((sum, item) =>
        sum + ((item.quantity || 1) * (item.rate || 0)), 0),
      memo: orderData.memo || '',
      externalId: orderData.externalId || `ODOO-${internalId}`,
      createdDate: new Date().toISOString(),
      lastModifiedDate: new Date().toISOString()
    };

    // Store in mock database
    mockDatabase.salesOrders.set(internalId, salesOrder);

    // Log successful sync
    logSync('CREATE_SALES_ORDER', 'success', salesOrder);

    // Return NetSuite-like response
    res.status(201).json({
      success: true,
      id: internalId,
      tranId: tranId,
      externalId: salesOrder.externalId,
      type: 'salesorder',
      links: [
        {
          rel: 'self',
          href: `/api/salesorder/${internalId}`
        }
      ]
    });

  } catch (error) {
    logSync('CREATE_SALES_ORDER', 'error', req.body, error.message);
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: error.message
      }
    });
  }
});

// Get Sales Order by ID
router.get('/salesorder/:id', (req, res) => {
  const { id } = req.params;

  const salesOrder = mockDatabase.salesOrders.get(id);

  if (!salesOrder) {
    return res.status(404).json({
      error: {
        code: 'RECORD_NOT_FOUND',
        message: `Sales Order with ID ${id} not found`
      }
    });
  }

  res.json(salesOrder);
});

// Update Sales Order
router.put('/salesorder/:id', (req, res) => {
  try {
    const { id } = req.params;
    const updateData = req.body;

    const existingOrder = mockDatabase.salesOrders.get(id);

    if (!existingOrder) {
      return res.status(404).json({
        error: {
          code: 'RECORD_NOT_FOUND',
          message: `Sales Order with ID ${id} not found`
        }
      });
    }

    // Update the order
    const updatedOrder = {
      ...existingOrder,
      ...updateData,
      lastModifiedDate: new Date().toISOString()
    };

    mockDatabase.salesOrders.set(id, updatedOrder);
    logSync('UPDATE_SALES_ORDER', 'success', updatedOrder);

    res.json({
      success: true,
      id: id,
      message: 'Sales Order updated successfully'
    });

  } catch (error) {
    logSync('UPDATE_SALES_ORDER', 'error', req.body, error.message);
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: error.message
      }
    });
  }
});

// Customer endpoints
router.post('/customer', (req, res) => {
  try {
    const customerData = req.body;
    const customerId = uuidv4();

    const customer = {
      id: customerId,
      ...customerData,
      externalId: customerData.externalId || `ODOO-CUST-${customerId}`,
      createdDate: new Date().toISOString()
    };

    mockDatabase.customers.set(customerId, customer);
    logSync('CREATE_CUSTOMER', 'success', customer);

    res.status(201).json({
      success: true,
      id: customerId,
      externalId: customer.externalId
    });

  } catch (error) {
    logSync('CREATE_CUSTOMER', 'error', req.body, error.message);
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: error.message
      }
    });
  }
});

// Payment endpoints
router.post('/payment', (req, res) => {
  try {
    const paymentData = req.body;
    const paymentId = uuidv4();

    const payment = {
      id: paymentId,
      ...paymentData,
      externalId: paymentData.externalId || `ODOO-PMT-${paymentId}`,
      createdDate: new Date().toISOString(),
      status: 'Deposited'
    };

    mockDatabase.payments.set(paymentId, payment);
    logSync('CREATE_PAYMENT', 'success', payment);

    res.status(201).json({
      success: true,
      id: paymentId,
      externalId: payment.externalId
    });

  } catch (error) {
    logSync('CREATE_PAYMENT', 'error', req.body, error.message);
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: error.message
      }
    });
  }
});

// Batch endpoint for multiple records
router.post('/batch', (req, res) => {
  try {
    const { operations } = req.body;

    if (!Array.isArray(operations)) {
      return res.status(400).json({
        error: {
          code: 'INVALID_REQUEST',
          message: 'operations must be an array'
        }
      });
    }

    const results = [];

    for (const operation of operations) {
      try {
        let result;

        switch (operation.type) {
          case 'salesorder':
            const orderId = uuidv4();
            const order = {
              id: orderId,
              ...operation.data,
              externalId: operation.data.externalId || `ODOO-${orderId}`,
              createdDate: new Date().toISOString()
            };
            mockDatabase.salesOrders.set(orderId, order);
            result = { success: true, id: orderId, externalId: order.externalId };
            break;

          default:
            result = {
              success: false,
              error: `Unknown operation type: ${operation.type}`
            };
        }

        results.push(result);

      } catch (error) {
        results.push({
          success: false,
          error: error.message
        });
      }
    }

    logSync('BATCH_OPERATION', 'completed', { total: operations.length, results });

    res.json({
      success: true,
      totalProcessed: operations.length,
      results: results
    });

  } catch (error) {
    logSync('BATCH_OPERATION', 'error', req.body, error.message);
    res.status(500).json({
      error: {
        code: 'INTERNAL_ERROR',
        message: error.message
      }
    });
  }
});

// Get sync logs
router.get('/sync-logs', (req, res) => {
  const { limit = 100, operation, status } = req.query;

  let logs = [...mockDatabase.syncLogs];

  if (operation) {
    logs = logs.filter(log => log.operation === operation);
  }

  if (status) {
    logs = logs.filter(log => log.status === status);
  }

  // Sort by timestamp descending and limit
  logs = logs
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, parseInt(limit));

  res.json({
    total: logs.length,
    logs: logs
  });
});

// Clear all data (for testing)
router.post('/reset', (req, res) => {
  mockDatabase.salesOrders.clear();
  mockDatabase.customers.clear();
  mockDatabase.items.clear();
  mockDatabase.payments.clear();
  mockDatabase.syncLogs = [];

  // Reinitialize default data
  mockDatabase.customers.set('1', {
    id: '1',
    name: 'Default Customer',
    email: 'customer@example.com',
    externalId: 'CUST-001'
  });

  res.json({
    success: true,
    message: 'Mock database reset successfully'
  });
});

module.exports = router;
