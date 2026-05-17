const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');
const { logSync } = require('../utils/logger');

/**
 * Handle Payment Creation
 */
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

module.exports = { handleCreatePayment };
