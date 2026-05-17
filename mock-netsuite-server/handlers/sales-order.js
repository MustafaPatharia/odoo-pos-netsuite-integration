const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');
const { logSync } = require('../utils/logger');

/**
 * Handle Sales Order Creation
 */
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

/**
 * Handle Status Check
 */
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

module.exports = { handleCreateSalesOrder, handleGetStatus };
