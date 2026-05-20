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
    if (!orderData.entity || !orderData.item) {
      logSync('CREATE_SALES_ORDER', 'failed', orderData, 'Missing required fields');
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: entity and item are required'
      });
    }

    // Extract entity ID (handle both formats: "1" or {"id": "1"})
    const entityId = typeof orderData.entity === 'object' ? orderData.entity.id : orderData.entity;

    // Extract items (handle both formats: items[] or item.items[])
    const items = orderData.item?.items || orderData.items || [];

    if (!Array.isArray(items) || items.length === 0) {
      logSync('CREATE_SALES_ORDER', 'failed', orderData, 'No items provided');
      return res.status(400).json({
        success: false,
        error: 'At least one item is required'
      });
    }

    // Generate NetSuite internal ID
    const internalId = Math.floor(10000 + Math.random() * 90000).toString();
    const tranId = `SO-${Date.now().toString().slice(-6)}`;
    const tranDate = orderData.tranDate || new Date().toISOString().split('T')[0];

    // Create sales order record - STORE AS-IS (preserve Odoo's structure)
    const salesOrder = {
      ...orderData,  // Keep all original fields from Odoo
      id: internalId,
      internalId: internalId,
      tranId: tranId,
      status: orderData.status || 'Pending Fulfillment',
      externalId: orderData.externalId || `ODOO-SO-${internalId}`,
      createdDate: new Date().toISOString(),
      lastModifiedDate: new Date().toISOString()
    };

    // Add debug info - what Odoo sent and what NetSuite responded
    const responsePayload = {
      success: true,
      id: internalId,
      internalId: internalId,
      tranId: tranId,
      externalId: salesOrder.externalId,
      type: 'salesorder',
      status: salesOrder.status,
      message: 'Sales Order created successfully'
    };

    salesOrder.debug = {
      request: orderData,      // What Odoo sent
      response: responsePayload  // What NetSuite returned
    };

    // Store in mock database
    mockDatabase.salesOrders.set(internalId, salesOrder);

    // Save to JSON file (if available from app.locals)
    if (req.app && req.app.locals && req.app.locals.saveToFile) {
      req.app.locals.saveToFile('order', tranDate, salesOrder);
    }

    // Log successful sync
    logSync('CREATE_SALES_ORDER', 'success', salesOrder);

    // Return NetSuite-like response
    res.status(201).json(responsePayload);

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
