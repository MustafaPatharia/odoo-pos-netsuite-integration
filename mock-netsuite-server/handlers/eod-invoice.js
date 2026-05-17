const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');
const { logSync } = require('../utils/logger');

/**
 * Handle End-of-Day Invoice Creation
 */
function handleCreateEODInvoice(req, res, payload) {
  try {
    console.log('\n=== Invoice Creation ===');
    console.log('Payload:', JSON.stringify(payload, null, 2));

    // Validate required fields
    if (!payload.entity || !payload.items || !Array.isArray(payload.items)) {
      logSync('CREATE_INVOICE', 'failed', payload, 'Missing required fields');
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: entity and items are required'
      });
    }

    // Generate NetSuite internal ID
    const internalId = Math.floor(10000 + Math.random() * 90000).toString();
    const tranId = `INV-${Date.now().toString().slice(-6)}`;
    const tranDate = payload.tranDate || new Date().toISOString().split('T')[0];

    // Create invoice record
    const invoice = {
      id: internalId,
      tranId: tranId,
      recordType: payload.recordType || 'invoice',
      entity: payload.entity,
      tranDate: tranDate,
      subsidiary: payload.subsidiary,
      department: payload.department,
      location: payload.location,
      currency: payload.currency || 'AED',
      status: payload.status || 'Open',
      items: payload.items.map((item, index) => ({
        line: index + 1,
        item: item.item,
        quantity: item.quantity || 1,
        rate: item.rate || 0,
        amount: item.amount || ((item.quantity || 1) * (item.rate || 0))
      })),
      payments: payload.payments || [],
      subTotal: payload.items.reduce((sum, item) =>
        sum + (item.amount || ((item.quantity || 1) * (item.rate || 0))), 0),
      total: payload.items.reduce((sum, item) =>
        sum + (item.amount || ((item.quantity || 1) * (item.rate || 0))), 0),
      memo: payload.memo || '',
      custbody_pos_shop: payload.custbody_pos_shop,
      custbody_pos_date: payload.custbody_pos_date,
      custbody_pos_order_count: payload.custbody_pos_order_count,
      externalId: payload.externalId || `ODOO-INV-${internalId}`,
      createdDate: new Date().toISOString(),
      lastModifiedDate: new Date().toISOString(),
      originalRequest: payload
    };

    // Store in database
    mockDatabase.salesOrders.set(internalId, invoice);

    // Save to JSON file (if available from app.locals)
    if (req.app && req.app.locals && req.app.locals.saveToFile) {
      req.app.locals.saveToFile('invoice', tranDate, invoice);
    }

    // Log successful sync
    logSync('CREATE_INVOICE', 'success', invoice);

    // Log successful creation
    logSync('CREATE_EOD_INVOICE', 'success', payload);

    console.log('✓ EOD Invoice created:', tranId);
    console.log('Internal ID:', internalId);

    // Return success response
    res.json({
      success: true,
      id: internalId,
      internalId: internalId,
      tranId: tranId,
      externalId: invoice.externalId,
      type: 'invoice',
      status: invoice.status,
      message: 'End-of-Day invoice created successfully'
    });

  } catch (error) {
    logSync('CREATE_EOD_INVOICE', 'error', payload, error.message);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

module.exports = { handleCreateEODInvoice };
