const express = require('express');
const router = express.Router();
const { handleGetConfig } = require('../handlers/config');
const { handleCreateSalesOrder, handleGetStatus } = require('../handlers/sales-order');
const { handleCreateCustomer } = require('../handlers/customer');
const { handleCreatePayment } = require('../handlers/payment');
const { handleCreateEODInvoice } = require('../handlers/eod-invoice');

/**
 * Main NetSuite RESTlet endpoint (matches real NetSuite URL pattern)
 * POST /app/site/hosting/restlet.nl
 */
router.post('/', (req, res) => {
  try {
    const { action } = req.query;
    const payload = req.body;

    console.log('\n=== Incoming NetSuite RESTlet Request ===');
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
      case 'getConfig':
        return handleGetConfig(req, res);
      case 'createEODInvoice':
        return handleCreateEODInvoice(req, res, payload);
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

/**
 * GET support for config
 */
router.get('/', (req, res) => {
  const { action } = req.query;

  if (action === 'getConfig') {
    return handleGetConfig(req, res);
  }

  res.status(400).json({
    success: false,
    error: 'GET method only supports getConfig action'
  });
});

module.exports = router;
