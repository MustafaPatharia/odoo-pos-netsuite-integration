const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');
const { logSync } = require('../utils/logger');

/**
 * Handle End-of-Day Invoice Creation
 */
function handleCreateEODInvoice(req, res, payload) {
  try {
    const { tranDate, externalId, shop, orders, totalAmount, orderCount } = payload;

    console.log('\n=== End-of-Day Invoice Creation ===');
    console.log('Business Date:', tranDate);
    console.log('Shop:', shop);
    console.log('Order Count:', orderCount);
    console.log('Total Amount:', totalAmount);

    // Validate required fields
    if (!tranDate || !externalId || !orders || !Array.isArray(orders)) {
      logSync('CREATE_EOD_INVOICE', 'failed', payload, 'Missing required fields');
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: tranDate, externalId, and orders are required'
      });
    }

    // Generate NetSuite IDs
    const internalId = uuidv4();
    const tranId = `INV-EOD-${tranDate.replace(/-/g, '')}`;

    // Create EOD invoice record
    const eodInvoice = {
      internalId: internalId,
      tranId: tranId,
      externalId: externalId,
      type: 'invoice',
      subType: 'end_of_day',
      tranDate: tranDate,
      shop: shop,
      orderCount: orderCount,
      orders: orders,
      totalAmount: totalAmount,
      status: 'Posted',
      createdDate: new Date().toISOString(),
      memo: `End-of-Day consolidated invoice for ${shop} on ${tranDate} (${orderCount} orders)`
    };

    // Store in database
    mockDatabase.salesOrders.set(internalId, eodInvoice);

    // Log successful creation
    logSync('CREATE_EOD_INVOICE', 'success', payload);

    console.log('✓ EOD Invoice created:', tranId);
    console.log('Internal ID:', internalId);

    // Return success response
    res.json({
      success: true,
      internalId: internalId,
      tranId: tranId,
      externalId: externalId,
      type: 'invoice',
      status: 'Posted',
      totalAmount: totalAmount,
      orderCount: orderCount,
      message: `End-of-Day invoice created successfully for ${orderCount} orders`
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
