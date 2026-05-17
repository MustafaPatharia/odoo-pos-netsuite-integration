const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');
const { logSync } = require('../utils/logger');

/**
 * Handle Customer Creation
 */
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

module.exports = { handleCreateCustomer };
