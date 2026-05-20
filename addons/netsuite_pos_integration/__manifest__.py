# -*- coding: utf-8 -*-
{
    'name': 'NetSuite POS Integration',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Enterprise NetSuite integration for Odoo POS with real-time and batch sync',
    'description': """
NetSuite POS Integration
========================

Production-ready integration between Odoo POS and NetSuite ERP.

Features:
---------
* Configurable sync modes (real-time & batch)
* Automatic retry mechanism for failed syncs
* Comprehensive sync logging and audit trails
* Manual sync controls and recovery options
* Queue-based background processing
* Batch processing with configurable size
* Support for Sales Orders, Customers, and Payments
* Mock NetSuite server for testing
* Full error handling and recovery workflows

Technical Highlights:
--------------------
* Clean modular architecture
* Enterprise-grade error handling
* Scalable queue processing
* Configurable retry policies
* Detailed API logging
* Role-based permissions
* Cron-based schedulers
* RESTful API integration
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'point_of_sale',
        'sale',
        'account',
    ],
    'data': [
        # Security
        'security/netsuite_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/netsuite_cron_data.xml',

        # Views
        'views/netsuite_config_views.xml',
        'views/netsuite_mapping_views.xml',
        'views/netsuite_sync_queue_views.xml',
        'views/netsuite_sync_log_views.xml',
        'views/netsuite_operations_views.xml',
        'views/product_views.xml',
        'views/pos_order_views.xml',
        'views/invoice_views.xml',
        'views/netsuite_menu.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'netsuite_pos_integration/static/src/js/netsuite_sync.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['requests'],
    },
}
