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
    if (!payload.entity || !payload.item) {
      logSync('CREATE_INVOICE', 'failed', payload, 'Missing required fields');
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: entity and item are required'
      });
    }

    // Extract entity ID (handle both formats: "1" or {"id": "1"})
    const entityId = typeof payload.entity === 'object' ? payload.entity.id : payload.entity;

    // Extract items (handle both formats: items[] or item.items[])
    const items = payload.item?.items || payload.items || [];

    if (!Array.isArray(items) || items.length === 0) {
      logSync('CREATE_INVOICE', 'failed', payload, 'No items provided');
      return res.status(400).json({
        success: false,
        error: 'At least one item is required'
      });
    }

    // Generate NetSuite internal ID
    const internalId = Math.floor(10000 + Math.random() * 90000).toString();
    const tranId = `INV-${Date.now().toString().slice(-6)}`;
    const tranDate = payload.tranDate || new Date().toISOString().split('T')[0];

    // Create invoice record - STORE AS-IS (preserve Odoo's structure)
    const invoice = {
      ...payload,  // Keep all original fields from Odoo
      id: internalId,
      tranId: tranId,
      status: payload.status || 'Open',
      externalId: payload.externalId || `ODOO-INV-${internalId}`,
      createdDate: new Date().toISOString(),
      lastModifiedDate: new Date().toISOString()
    };

    // Add debug info - what Odoo sent and what NetSuite responded
    const responsePayload = {
      success: true,
      id: internalId,
      internalId: internalId,
      tranId: tranId,
      externalId: invoice.externalId,
      type: 'invoice',
      status: invoice.status,
      message: 'End-of-Day invoice created successfully'
    };

    invoice.debug = {
      request: payload,      // What Odoo sent
      response: responsePayload  // What NetSuite returned
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
    res.json(responsePayload);

  } catch (error) {
    logSync('CREATE_EOD_INVOICE', 'error', payload, error.message);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}

module.exports = { handleCreateEODInvoice };
