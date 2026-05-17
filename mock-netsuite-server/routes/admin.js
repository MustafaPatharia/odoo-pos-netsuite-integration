const express = require('express');
const router = express.Router();
const mockDatabase = require('../data/mock-database');

/**
 * Admin: Get all orders
 */
router.get('/orders', (req, res) => {
  const orders = Array.from(mockDatabase.salesOrders.values());
  res.json({
    count: orders.length,
    orders: orders
  });
});

/**
 * Admin: Get all customers
 */
router.get('/customers', (req, res) => {
  const customers = Array.from(mockDatabase.customers.values());
  res.json({
    count: customers.length,
    customers: customers
  });
});

/**
 * Admin: Get sync logs
 */
router.get('/logs', (req, res) => {
  const limit = parseInt(req.query.limit) || 50;
  const logs = mockDatabase.syncLogs.slice(-limit);
  res.json({
    count: logs.length,
    logs: logs
  });
});

/**
 * Admin: Get all master data
 */
router.get('/master-data', (req, res) => {
  res.json({
    subsidiaries: Array.from(mockDatabase.subsidiaries.values()),
    departments: Array.from(mockDatabase.departments.values()),
    locations: Array.from(mockDatabase.locations.values()),
    paymentMethods: Array.from(mockDatabase.paymentMethods.values())
  });
});

/**
 * Admin: Reset database
 */
router.delete('/reset', (req, res) => {
  mockDatabase.salesOrders.clear();
  mockDatabase.customers.clear();
  mockDatabase.payments.clear();
  mockDatabase.syncLogs = [];

  // Re-initialize default customer
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

module.exports = router;
