/**
 * NetSuite Mock Server v2.0
 * Supports REST API endpoints for Odoo POS Integration
 *
 * Endpoints:
 * - GET  /health - Health check
 * - GET  /app/site/hosting/restlet.nl?action=getConfig - Get configuration
 * - GET  /api/items - Get products/items
 * - GET  /services/rest/record/v1/inventoryItem - NetSuite REST API format
 * - POST /api/salesorder - Create consolidated sales order
 * - POST /api/invoice - Create consolidated invoice
 * - GET  /api/debug/* - Inspect mock data
 */

const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Request logging
app.use((req, res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    console.log('Headers:', req.headers);
    if (req.body && Object.keys(req.body).length > 0) {
        console.log('Body:', JSON.stringify(req.body, null, 2));
    }
    next();
});

// ============================================
// Mock Data Storage
// ============================================
let mockProducts = [
    {
        id: '1001',
        itemid: 'ITEM-001',
        displayname: 'Coffee - Espresso',
        description: 'Premium espresso blend',
        baseprice: 3.50,
        cost: 1.20,
        isinactive: false
    },
    {
        id: '1002',
        itemid: 'ITEM-002',
        displayname: 'Coffee - Latte',
        description: 'Classic latte',
        baseprice: 4.50,
        cost: 1.50,
        isinactive: false
    },
    {
        id: '1003',
        itemid: 'ITEM-003',
        displayname: 'Pastry - Croissant',
        description: 'Butter croissant',
        baseprice: 2.50,
        cost: 0.80,
        isinactive: false
    },
    {
        id: '1004',
        itemid: 'ITEM-004',
        displayname: 'Sandwich - Club',
        description: 'Classic club sandwich',
        baseprice: 8.50,
        cost: 3.20,
        isinactive: false
    },
    {
        id: '1005',
        itemid: 'ITEM-005',
        displayname: 'Juice - Orange',
        description: 'Fresh orange juice',
        baseprice: 3.00,
        cost: 0.90,
        isinactive: false
    }
];

let mockOrders = [];
let mockInvoices = [];
let orderIdCounter = 5000;
let invoiceIdCounter = 8000;

// ============================================
// Health Check
// ============================================
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        service: 'NetSuite Mock Server',
        version: '2.0',
        stats: {
            products: mockProducts.length,
            orders: mockOrders.length,
            invoices: mockInvoices.length
        }
    });
});

// ============================================
// Configuration API
// ============================================
app.get('/app/site/hosting/restlet.nl', (req, res) => {
    const action = req.query.action;

    if (action === 'getConfig') {
        const config = {
            configuration: {
                integration_mode: 'scheduled',
                realtime_settings: {
                    enabled: false,
                    sync_on_order_confirmed: false,
                    sync_on_invoice_validated: false,
                    immediate_payment_sync: false
                },
                scheduled_settings: {
                    enabled: true,
                    order_sync_time: '00:00',
                    invoice_sync_time: '00:00',
                    product_sync_frequency: 'hourly',
                    product_sync_hour_interval: 1
                },
                manual_execution: {
                    enabled: true,
                    allow_retry_failed: true,
                    allow_test_connection: true
                },
                retry_policy: {
                    enabled: true,
                    max_retries: 3,
                    initial_delay_minutes: 5,
                    use_exponential_backoff: true,
                    backoff_multiplier: 2
                },
                batch_processing: {
                    order_batch_size: 100,
                    invoice_batch_size: 100,
                    product_batch_size: 50
                },
                notification: {
                    send_email_on_failure: true,
                    send_email_on_success: false,
                    notification_recipients: ['admin@example.com']
                },
                logging: {
                    enable_debug_logging: false,
                    log_retention_days: 90,
                    log_request_payload: true,
                    log_response_payload: true
                },
                api_settings: {
                    connection_timeout_seconds: 30,
                    request_timeout_seconds: 120,
                    api_rate_limit_per_minute: 60
                },
                consolidation_rules: {
                    consolidate_orders_per_shop_per_day: true,
                    consolidate_invoices_per_shop_per_day: true,
                    aggregate_line_items: true,
                    group_by_product: true
                }
            },
            metadata: {
                config_version: '1.0',
                last_updated_by: 'NetSuite System',
                last_updated_at: new Date().toISOString(),
                netsuite_environment: 'sandbox'
            }
        };

        return res.json(config);
    }

    res.status(400).json({
        success: false,
        error: { message: 'Unknown action parameter' }
    });
});

// ============================================
// Product/Item APIs
// ============================================

// Get all products (NetSuite REST API format)
app.get('/api/items', (req, res) => {
    const limit = parseInt(req.query.limit) || 100;
    const ids = req.query.ids ? req.query.ids.split(',') : null;

    let filteredProducts = mockProducts;

    if (ids) {
        filteredProducts = mockProducts.filter(p => ids.includes(p.id));
    }

    const paginatedProducts = filteredProducts.slice(0, limit);

    console.log(`Returning ${paginatedProducts.length} products`);

    res.json({
        success: true,
        items: paginatedProducts,
        count: paginatedProducts.length,
        total: filteredProducts.length
    });
});

// NetSuite REST Record API format
app.get('/services/rest/record/v1/inventoryItem', (req, res) => {
    const limit = parseInt(req.query.limit) || 100;

    const paginatedProducts = mockProducts.slice(0, limit);

    res.json({
        items: paginatedProducts,
        count: paginatedProducts.length,
        hasMore: mockProducts.length > limit
    });
});

// ============================================
// Sales Order API (Consolidated)
// ============================================
app.post('/api/salesorder', (req, res) => {
    console.log('✅ Creating consolidated sales order');
    console.log('Payload:', JSON.stringify(req.body, null, 2));

    const order = {
        id: String(orderIdCounter++),
        tranId: `SO-${Date.now()}`,
        ...req.body,
        createdAt: new Date().toISOString(),
        status: 'Pending Fulfillment'
    };

    mockOrders.push(order);

    console.log(`✅ Order created: ${order.tranId} (ID: ${order.id})`);

    res.json({
        success: true,
        id: order.id,
        tranId: order.tranId,
        message: 'Consolidated sales order created successfully',
        recordType: 'salesorder'
    });
});

// ============================================
// Invoice API (Consolidated)
// ============================================
app.post('/api/invoice', (req, res) => {
    console.log('✅ Creating consolidated invoice');
    console.log('Payload:', JSON.stringify(req.body, null, 2));

    const invoice = {
        id: String(invoiceIdCounter++),
        tranId: `INV-${Date.now()}`,
        ...req.body,
        createdAt: new Date().toISOString(),
        status: 'Open'
    };

    mockInvoices.push(invoice);

    console.log(`✅ Invoice created: ${invoice.tranId} (ID: ${invoice.id})`);

    res.json({
        success: true,
        id: invoice.id,
        tranId: invoice.tranId,
        message: 'Consolidated invoice created successfully',
        recordType: 'invoice'
    });
});

// ============================================
// Mock Data Inspection (for debugging)
// ============================================
app.get('/api/debug/orders', (req, res) => {
    res.json({
        orders: mockOrders,
        count: mockOrders.length
    });
});

app.get('/api/debug/invoices', (req, res) => {
    res.json({
        invoices: mockInvoices,
        count: mockInvoices.length
    });
});

app.get('/api/debug/products', (req, res) => {
    res.json({
        products: mockProducts,
        count: mockProducts.length
    });
});

app.delete('/api/debug/reset', (req, res) => {
    mockOrders = [];
    mockInvoices = [];
    orderIdCounter = 5000;
    invoiceIdCounter = 8000;

    res.json({
        success: true,
        message: 'All mock data reset successfully'
    });
});

// ============================================
// Error Handler
// ============================================
app.use((err, req, res, next) => {
    console.error('❌ Error:', err);
    res.status(500).json({
        success: false,
        error: {
            code: 'INTERNAL_ERROR',
            message: err.message || 'Internal server error'
        }
    });
});

// ============================================
// Start Server
// ============================================
app.listen(PORT, () => {
    console.log('='.repeat(70));
    console.log('🚀 NetSuite Mock Server v2.0 Started');
    console.log('='.repeat(70));
    console.log(`📡 Port: ${PORT}`);
    console.log(`🌐 Base URL: http://localhost:${PORT}`);
    console.log('');
    console.log('📋 Available Endpoints:');
    console.log('  ✓ GET  /health');
    console.log('  ✓ GET  /app/site/hosting/restlet.nl?action=getConfig');
    console.log('  ✓ GET  /api/items?limit=100');
    console.log('  ✓ GET  /services/rest/record/v1/inventoryItem?limit=100');
    console.log('  ✓ POST /api/salesorder');
    console.log('  ✓ POST /api/invoice');
    console.log('  ✓ GET  /api/debug/orders');
    console.log('  ✓ GET  /api/debug/invoices');
    console.log('  ✓ GET  /api/debug/products');
    console.log('  ✓ DELETE /api/debug/reset');
    console.log('='.repeat(70));
    console.log('');
    console.log(`📊 Loaded ${mockProducts.length} sample products`);
    console.log('');
});
