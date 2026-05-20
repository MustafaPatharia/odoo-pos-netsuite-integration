const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const morgan = require('morgan');
const fs = require('fs');
const path = require('path');
const mockDatabase = require('./data/mock-database');

// Import routes
const restletRoutes = require('./routes/restlet');
const restApiRoutes = require('./routes/rest-api');
const adminRoutes = require('./routes/admin');

const app = express();
const PORT = process.env.PORT || 3000;

// Create storage directories for JSON file persistence
const STORAGE_DIR = path.join(__dirname, 'storage');
const ORDERS_DIR = path.join(STORAGE_DIR, 'orders');
const INVOICES_DIR = path.join(STORAGE_DIR, 'invoices');

[STORAGE_DIR, ORDERS_DIR, INVOICES_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`📁 Created directory: ${dir}`);
  }
});

// Helper function to save data to JSON file
function saveToFile(type, date, data) {
  try {
    const dir = type === 'order' ? ORDERS_DIR : INVOICES_DIR;
    const filename = `${date}.json`;
    const filepath = path.join(dir, filename);

    // Read existing data if file exists
    let existingData = [];
    if (fs.existsSync(filepath)) {
      const content = fs.readFileSync(filepath, 'utf8');
      existingData = JSON.parse(content);
    }

    // Append new data
    existingData.push({
      ...data,
      savedAt: new Date().toISOString()
    });

    // Write back to file
    fs.writeFileSync(filepath, JSON.stringify(existingData, null, 2));
    console.log(`✓ Saved ${type} to: ${filepath}`);

    return filepath;
  } catch (error) {
    console.error(`✗ Error saving ${type} to file:`, error);
    return null;
  }
}

// Make saveToFile available globally for routes
app.locals.saveToFile = saveToFile;

// Middleware
app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));
app.use(bodyParser.urlencoded({ extended: true }));
app.use(morgan('dev'));

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
      syncLogs: mockDatabase.syncLogs.length,
      subsidiaries: mockDatabase.subsidiaries.size,
      departments: mockDatabase.departments.size,
      locations: mockDatabase.locations.size,
      paymentMethods: mockDatabase.paymentMethods.size
    },
    endpoints: {
      restlet: '/app/site/hosting/restlet.nl',
      rest_api: '/services/rest/record/v1/{recordType}',
      admin: ['/admin/orders', '/admin/customers', '/admin/logs', '/admin/master-data']
    }
  });
});

// Mount routes
app.use('/app/site/hosting/restlet.nl', restletRoutes);
app.use('/services/rest/record/v1', restApiRoutes);
app.use('/admin', adminRoutes);

// Simple API endpoint for products (convenience endpoint)
app.get('/api/items', (req, res) => {
  const limit = req.query.limit ? parseInt(req.query.limit) : null; // No limit = fetch all
  const offset = parseInt(req.query.offset) || 0;
  const ids = req.query.ids ? req.query.ids.split(',') : null;

  console.log(`\n=== GET /api/items (limit: ${limit || 'ALL'}, offset: ${offset}) ===`);
  console.log('⚡ Generating RANDOM prices and costs for testing...');

  let allItems = Array.from(mockDatabase.items.values());

  // Filter by IDs if provided
  if (ids && ids.length > 0) {
    allItems = allItems.filter(item => ids.includes(item.id));
  }

  // Apply pagination (if no limit, return all items)
  const paginatedItems = limit ? allItems.slice(offset, offset + limit) : allItems.slice(offset);

  // Generate random prices, costs, and quantities for each item (for testing sync updates)
  const itemsWithRandomPrices = paginatedItems.map(item => {
    const randomPrice = (Math.random() * 15 + 2).toFixed(2); // Random price between $2-$17
    const randomCost = (parseFloat(randomPrice) * (Math.random() * 0.5 + 0.3)).toFixed(2); // Cost is 30-80% of price
    const randomQty = Math.floor(Math.random() * 100) + 10; // Random qty between 10-110

    return {
      ...item,
      baseprice: parseFloat(randomPrice),
      cost: parseFloat(randomCost),
      quantityavailable: randomQty,
      quantityonhand: randomQty,
      // Optionally randomize other fields
      isinactive: Math.random() > 0.95 ? true : false, // 5% chance inactive
      description: `${item.description} (Updated: ${new Date().toLocaleTimeString()})`
    };
  });

  console.log(`✓ Returning ${itemsWithRandomPrices.length} items with RANDOMIZED prices`);
  itemsWithRandomPrices.slice(0, 3).forEach(item => {
    console.log(`  - ${item.displayname}: $${item.baseprice} (cost: $${item.cost})`);
  });

  res.json({
    success: true,
    items: itemsWithRandomPrices,
    count: itemsWithRandomPrices.length,
    total: allItems.length,
    hasMore: (offset + itemsWithRandomPrices.length) < allItems.length
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log('\n' + '='.repeat(60));
  console.log('🚀 Mock NetSuite Server Started');
  console.log('='.repeat(60));
  console.log(`📍 Server: http://localhost:${PORT}`);
  console.log(`🏥 Health: http://localhost:${PORT}/health`);
  console.log('\n📦 RESTlet API (Legacy):');
  console.log(`   http://localhost:${PORT}/app/site/hosting/restlet.nl`);
  console.log('\n🔍 NetSuite Standard REST API:');
  console.log(`   POST   ${PORT}/services/rest/record/v1/salesorder`);
  console.log(`   POST   ${PORT}/services/rest/record/v1/invoice`);
  console.log(`   GET    ${PORT}/services/rest/record/v1/subsidiary`);
  console.log(`   GET    ${PORT}/services/rest/record/v1/department`);
  console.log(`   GET    ${PORT}/services/rest/record/v1/location`);
  console.log(`   GET    ${PORT}/services/rest/record/v1/paymentmethod`);
  console.log(`   GET    ${PORT}/services/rest/record/v1/inventoryItem`);
  console.log('\n📊 Admin Endpoints:');
  console.log(`   Orders:       http://localhost:${PORT}/admin/orders`);
  console.log(`   Customers:    http://localhost:${PORT}/admin/customers`);
  console.log(`   Logs:         http://localhost:${PORT}/admin/logs`);
  console.log(`   Master Data:  http://localhost:${PORT}/admin/master-data`);
  console.log('\n📚 Master Data Loaded:');
  console.log(`   Subsidiaries: ${mockDatabase.subsidiaries.size}`);
  console.log(`   Departments:  ${mockDatabase.departments.size}`);
  console.log(`   Locations:    ${mockDatabase.locations.size}`);
  console.log(`   Payment Methods: ${mockDatabase.paymentMethods.size}`);
  console.log('\n💾 JSON Storage:');
  console.log(`   Orders:   ${ORDERS_DIR}`);
  console.log(`   Invoices: ${INVOICES_DIR}`);
  console.log('='.repeat(60) + '\n');
});

module.exports = app;
