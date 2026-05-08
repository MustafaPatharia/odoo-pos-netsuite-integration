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
    version: '1.0.0',
    stats: {
      salesOrders: mockDatabase.salesOrders.size,
      customers: mockDatabase.customers.size,
      syncLogs: mockDatabase.syncLogs.length
    }
  });
});

// Main NetSuite RESTlet endpoint (matches real NetSuite URL pattern)
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
    const orderData = payload;

    // Validate required fields
    if (!orderData.entity || !orderData.items || !Array.isArray(orderData.items)) {
      logSync('CREATE_SALES_ORDER', 'failed', orderData, 'Missing required fields');
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: entity and items are required'
      });
    }

    // Generate NetSuite internal ID
    const internalId = uuidv4();
    const tranId = `SO-${Date.now()}`;

    // Calculate totals
    const subTotal = orderData.items.reduce((sum, item) =>
      sum + ((item.quantity || 1) * (item.rate || 0)), 0);

    // Create sales order record
    const salesOrder = {
      internalId: internalId,
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
      subTotal: subTotal,
      total: orderData.total || subTotal,
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
      internalId: internalId,
      tranId: tranId,
      externalId: salesOrder.externalId,
      type: 'salesorder',
      status: salesOrder.status,
      message: 'Sales Order created successfully'
    });

  } catch (error) {
    logSync('CREATE_SALES_ORDER', 'error', payload, error.message);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

// Handle Customer Creation
function handleCreateCustomer(req, res, payload) {
  try {
    const customerId = uuidv4();
    const entityId = `CUST-${Date.now()}`;

    const customer = {
      internalId: customerId,
      entityId: entityId,
      companyName: payload.companyName || payload.name,
      email: payload.email,
      phone: payload.phone,
      externalId: payload.externalId || `ODOO-CUST-${customerId}`,
      createdDate: new Date().toISOString()
    };

    mockDatabase.customers.set(customerId, customer);
    logSync('CREATE_CUSTOMER', 'success', customer);

    res.status(201).json({
      success: true,
      internalId: customerId,
      entityId: entityId,
      externalId: customer.externalId,
      type: 'customer',
      message: 'Customer created successfully'
    });

  } catch (error) {
    logSync('CREATE_CUSTOMER', 'error', payload, error.message);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

// Handle Payment Creation
function handleCreatePayment(req, res, payload) {
  try {
    const paymentId = uuidv4();
    const tranId = `PMT-${Date.now()}`;

    const payment = {
      internalId: paymentId,
      tranId: tranId,
      customer: payload.customer,
      salesOrder: payload.salesOrder,
      amount: payload.amount,
      paymentMethod: payload.paymentMethod,
      memo: payload.memo,
      externalId: payload.externalId || `ODOO-PMT-${paymentId}`,
      createdDate: new Date().toISOString()
    };

    mockDatabase.payments.set(paymentId, payment);
    logSync('CREATE_PAYMENT', 'success', payment);

    res.status(201).json({
      success: true,
      internalId: paymentId,
      tranId: tranId,
      externalId: payment.externalId,
      type: 'payment',
      message: 'Payment recorded successfully'
    });

  } catch (error) {
    logSync('CREATE_PAYMENT', 'error', payload, error.message);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

// Handle Status Check
function handleGetStatus(req, res, payload) {
  try {
    const { internalId, externalId } = payload;

    let record = null;
    let type = null;

    // Search in sales orders
    if (internalId && mockDatabase.salesOrders.has(internalId)) {
      record = mockDatabase.salesOrders.get(internalId);
      type = 'salesorder';
    }

    // Search by external ID if not found
    if (!record && externalId) {
      for (const [id, order] of mockDatabase.salesOrders) {
        if (order.externalId === externalId) {
          record = order;
          type = 'salesorder';
          break;
        }
      }
    }

    if (!record) {
      return res.status(404).json({
        success: false,
        error: 'Record not found'
      });
    }

    res.json({
      success: true,
      type: type,
      status: record.status || 'Unknown',
      record: record
    });

  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

// Admin endpoints for debugging
app.get('/admin/orders', (req, res) => {
  const orders = Array.from(mockDatabase.salesOrders.values());
  res.json({
    count: orders.length,
    orders: orders
  });
});

app.get('/admin/customers', (req, res) => {
  const customers = Array.from(mockDatabase.customers.values());
  res.json({
    count: customers.length,
    customers: customers
  });
});

app.get('/admin/logs', (req, res) => {
  const limit = parseInt(req.query.limit) || 50;
  const logs = mockDatabase.syncLogs.slice(-limit);
  res.json({
    count: logs.length,
    logs: logs
  });
});

app.delete('/admin/reset', (req, res) => {
  mockDatabase.salesOrders.clear();
  mockDatabase.customers.clear();
  mockDatabase.payments.clear();
  mockDatabase.syncLogs = [];

  // Re-initialize default data
  mockDatabase.customers.set('1', {
    internalId: '1',
    entityId: 'CUST-001',
    companyName: 'Default Customer',
    email: 'customer@example.com',
    externalId: 'ODOO-CUST-001'
  });

  res.json({
    success: true,
    message: 'Mock database reset successfully'
  });
});

// Start server
app.listen(PORT, () => {
  console.log('\n==============================================');
  console.log('🚀 Mock NetSuite Server Started');
  console.log('==============================================');
  console.log(`📍 Server: http://localhost:${PORT}`);
  console.log(`🏥 Health: http://localhost:${PORT}/health`);
  console.log(`📊 Admin Orders: http://localhost:${PORT}/admin/orders`);
  console.log(`👥 Admin Customers: http://localhost:${PORT}/admin/customers`);
  console.log(`📝 Admin Logs: http://localhost:${PORT}/admin/logs`);
  console.log('==============================================\n');
});

module.exports = app;
