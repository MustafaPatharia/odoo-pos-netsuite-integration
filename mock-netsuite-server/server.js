const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const morgan = require('morgan');
const mockDatabase = require('./data/mock-database');

// Import routes
const restletRoutes = require('./routes/restlet');
const restApiRoutes = require('./routes/rest-api');
const adminRoutes = require('./routes/admin');

const app = express();
const PORT = process.env.PORT || 3000;

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

  // Generate random prices and costs for each item (for testing sync updates)
  const itemsWithRandomPrices = paginatedItems.map(item => {
    const randomPrice = (Math.random() * 15 + 2).toFixed(2); // Random price between $2-$17
    const randomCost = (parseFloat(randomPrice) * (Math.random() * 0.5 + 0.3)).toFixed(2); // Cost is 30-80% of price
    
    return {
      ...item,
      baseprice: parseFloat(randomPrice),
      cost: parseFloat(randomCost),
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
app.listen(PORT, () => {
  console.log('\n==============================================');
  console.log('🚀 Mock NetSuite Server Started');
  console.log('==============================================');
  console.log(`📍 Server: http://localhost:${PORT}`);
  console.log(`🏥 Health: http://localhost:${PORT}/health`);
  console.log('\n📦 RESTlet API:');
  console.log(`   http://localhost:${PORT}/app/site/hosting/restlet.nl`);
  console.log('\n🔍 REST Record Browser API:');
  console.log(`   http://localhost:${PORT}/services/rest/record/v1/subsidiary`);
  console.log(`   http://localhost:${PORT}/services/rest/record/v1/department`);
  console.log(`   http://localhost:${PORT}/services/rest/record/v1/location`);
  console.log(`   http://localhost:${PORT}/services/rest/record/v1/paymentmethod`);
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
  console.log('==============================================\n');
});

module.exports = app;
