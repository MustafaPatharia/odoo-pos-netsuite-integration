# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class NetSuiteProductSync(models.AbstractModel):
    """
    Service for syncing Products/Items from NetSuite to Odoo
    Uses NetSuite REST API: /services/rest/record/v1/inventoryItem
    """
    _name = 'netsuite.product.sync'
    _description = 'NetSuite Product Sync Service'

    @api.model
    def sync_products_from_netsuite(self, limit=None, product_ids=None, sync_mode='manual'):
        """
        Fetch products/items from NetSuite and create/update in Odoo

        Args:
            limit: Maximum number of products to fetch (for testing)
            product_ids: List of specific NetSuite item IDs to sync
            sync_mode: 'manual' (button click) or 'scheduled' (cron job)

        Returns:
            dict: {
                'success': True/False,
                'total_fetched': 10,
                'created': 5,
                'updated': 3,
                'failed': 2,
                'errors': [...]
            }
        """
        _logger.info('[NetSuite Product Sync] ========== SYNC STARTED ==========')
        _logger.info(f'[NetSuite Product Sync] Limit: {limit or "ALL"}, Product IDs: {product_ids or "ALL"}')

        config = self.env['netsuite.config'].get_active_config()

        if not config:
            _logger.error('[NetSuite Product Sync] No active NetSuite configuration found')
            raise UserError(_('No active NetSuite configuration found'))

        # Cron jobs should only run in 'scheduled' integration mode
        if sync_mode == 'scheduled' and config.config_integration_mode != 'scheduled':
            _logger.info(f'[NetSuite Product Sync Cron] Skipped - Integration mode is "{config.config_integration_mode}", expected "scheduled"')
            return {'success': True, 'skipped': True, 'reason': f'Integration mode is {config.config_integration_mode}, not scheduled'}

        _logger.info(f'[NetSuite Product Sync] Using config: {config.name} (API: {config.api_url})')

        # Log sync start
        # Use UTC time with offset indicator for consistency
        now_utc = fields.Datetime.now()
        timestamp_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')

        sync_log = self.env['netsuite.sync.log'].create({
            'config_id': config.id,
            'reference': f'Product Sync {timestamp_str} (+00:00)',
            'record_type': 'product',
            'record_id': 0,  # Bulk operation
            'status': 'processing',
            'sync_mode': sync_mode,
            'operation': 'fetch',
            'request_method': 'GET',  # Product fetch uses GET
        })

        results = {
            'success': False,
            'total_fetched': 0,
            'created': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        try:
            # Fetch products from NetSuite
            _logger.info('[NetSuite Product Sync] Fetching products from NetSuite...')
            try:
                products_data, fetch_metadata = self._fetch_products_from_netsuite(config, limit, product_ids)
            except Exception as fetch_error:
                # If fetch fails, try to extract metadata from the error context
                # This happens when the request fails (404, timeout, etc.)
                fetch_metadata = getattr(fetch_error, 'metadata', {
                    'url': config.api_url,
                    'params': {},
                    'response_code': None,
                    'execution_time_ms': 0
                })
                # Update sync log with whatever metadata we have
                error_msg = f'Product sync failed: {str(fetch_error)}'
                sync_log.write({
                    'request_url': fetch_metadata.get('url'),
                    'request_method': 'GET',
                    'request_payload': json.dumps(fetch_metadata.get('params', {})),
                    'response_code': fetch_metadata.get('response_code'),
                    'execution_time_ms': fetch_metadata.get('execution_time_ms'),
                    'status': 'failed',
                    'error_message': error_msg
                })

                _logger.error(f'[NetSuite Product Sync] ========== SYNC FAILED ==========')
                _logger.error(f'[NetSuite Product Sync] {error_msg}')

                results['errors'].append(error_msg)
                return results  # Return instead of re-raising

            # Update sync log with request details
            sync_log.write({
                'request_url': fetch_metadata.get('url'),
                'request_method': 'GET',
                'request_payload': json.dumps(fetch_metadata.get('params', {})),
                'response_code': fetch_metadata.get('response_code'),
                'execution_time_ms': fetch_metadata.get('execution_time_ms'),
            })

            if not products_data:
                _logger.warning('[NetSuite Product Sync] No products returned from NetSuite')
                sync_log.write({
                    'status': 'failed',
                    'error_message': 'No products returned from NetSuite'
                })
                results['errors'].append('No products returned from NetSuite')
                return results

            results['total_fetched'] = len(products_data)
            _logger.info(f'[NetSuite Product Sync] Fetched {len(products_data)} products from NetSuite')

            # Process each product
            ProductTemplate = self.env['product.template']
            StockQuant = self.env['stock.quant']

            for product_data in products_data:
                try:
                    # Extract product fields
                    netsuite_id = str(product_data.get('id'))
                    item_id = product_data.get('itemid')  # NetSuite item ID (SKU)
                    display_name = product_data.get('displayname')
                    description = product_data.get('description', '')
                    base_price = float(product_data.get('baseprice', 0.0))
                    cost_estimate = float(product_data.get('cost', 0.0))
                    is_inactive = product_data.get('isinactive', False)
                    quantity_available = float(product_data.get('quantityavailable', 0.0))

                    # Search for existing product by NetSuite ID
                    existing_product = ProductTemplate.search([
                        ('x_netsuite_id', '=', netsuite_id)
                    ], limit=1)

                    # Prepare product values
                    product_vals = {
                        'name': display_name or item_id,
                        'default_code': item_id,
                        'description': description,
                        'list_price': base_price,
                        'standard_price': cost_estimate,
                        'type': 'product',  # Storable product
                        'active': not is_inactive,
                        'available_in_pos': True,  # Make product available in POS
                        'x_netsuite_id': netsuite_id,
                        'x_netsuite_last_sync': fields.Datetime.now(),
                    }

                    if existing_product:
                        # Update existing product
                        existing_product.write(product_vals)
                        product = existing_product
                        results['updated'] += 1
                        _logger.info(f'[NetSuite Product Sync] ✓ Updated: {display_name} (ID: {netsuite_id}, Price: ${base_price}, Qty: {quantity_available})')
                    else:
                        # Create new product
                        product = ProductTemplate.create(product_vals)
                        results['created'] += 1
                        _logger.info(f'[NetSuite Product Sync] ✓ Created: {display_name} (ID: {netsuite_id}, Price: ${base_price}, Qty: {quantity_available})')

                    # Update stock quantity if product is storable
                    if product.type == 'product' and quantity_available is not None:
                        # Get the default warehouse location
                        warehouse = self.env['stock.warehouse'].search([
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)

                        if warehouse:
                            location = warehouse.lot_stock_id
                            product_product = product.product_variant_ids[:1]

                            if product_product:
                                # Update or create stock quant
                                StockQuant.with_context(inventory_mode=True)._update_available_quantity(
                                    product_product,
                                    location,
                                    quantity_available,
                                    lot_id=None,
                                    package_id=None,
                                    owner_id=None
                                )
                                _logger.info(f'[NetSuite Product Sync]   └─ Stock updated: {quantity_available} units in {location.name}')

                except Exception as e:
                    results['failed'] += 1
                    error_msg = f"Error syncing product {product_data.get('itemid', 'Unknown')}: {str(e)}"
                    results['errors'].append(error_msg)
                    _logger.error(f'[NetSuite Product Sync] ✗ {error_msg}')

            # Update sync log
            results['success'] = results['failed'] == 0

            _logger.info('[NetSuite Product Sync] ========== SYNC COMPLETED ==========')
            _logger.info(f'[NetSuite Product Sync] Results - Created: {results["created"]}, Updated: {results["updated"]}, Failed: {results["failed"]}')

            sync_log.write({
                'status': 'success' if results['success'] else 'partial',
                'error_message': '\n'.join(results['errors']) if results['errors'] else None,
                'response_payload': json.dumps(results, indent=2),
                'notes': f"Created: {results['created']}, Updated: {results['updated']}, Failed: {results['failed']}"
            })

            return results

        except Exception as e:
            error_msg = f'Product sync failed: {str(e)}'
            _logger.error(f'[NetSuite Product Sync] ========== SYNC FAILED ==========')
            _logger.error(f'[NetSuite Product Sync] {error_msg}', exc_info=True)

            # Try to get fetch metadata if error happened during fetch
            update_vals = {
                'status': 'failed',
                'error_message': error_msg
            }

            # Check if fetch was attempted and metadata exists
            if 'fetch_metadata' in locals():
                update_vals.update({
                    'request_url': fetch_metadata.get('url'),
                    'request_method': 'GET',
                    'request_payload': json.dumps(fetch_metadata.get('params', {})),
                    'response_code': fetch_metadata.get('response_code'),
                    'execution_time_ms': fetch_metadata.get('execution_time_ms'),
                })

            sync_log.write(update_vals)

            results['errors'].append(error_msg)
            return results

    def _fetch_products_from_netsuite(self, config, limit=None, product_ids=None):
        """
        Fetch products from NetSuite REST API

        Args:
            config: netsuite.config record
            limit: Max number of records to fetch
            product_ids: List of specific NetSuite IDs

        Returns:
            tuple: (products_list, metadata_dict)
                metadata contains: url, params, response_code, execution_time_ms
        """
        import time
        start_time = time.time()

        try:
            # For mock server - use simple GET endpoint
            # For real NetSuite - use REST Record API

            if 'localhost' in config.api_url or 'host.docker.internal' in config.api_url:
                # Mock server endpoint
                url = f"{config.api_url.rstrip('/')}/api/items"
                params = {}
                if limit:
                    params['limit'] = limit
                if product_ids:
                    params['ids'] = ','.join(str(id) for id in product_ids)
            else:
                # Real NetSuite REST API
                # /services/rest/record/v1/inventoryItem (no limit = fetch all)
                url = f"{config.api_url.rstrip('/')}/services/rest/record/v1/inventoryItem"
                params = {}
                if limit:
                    params['limit'] = limit
                if product_ids:
                    # For specific IDs, make multiple requests (NetSuite limitation)
                    # For now, we'll just fetch all and filter
                    pass

            headers = self._get_netsuite_headers(config)

            timeout = (30, 120)  # Connection timeout, Request timeout

            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()

            data = response.json()

            # Handle different response structures
            if isinstance(data, dict):
                # Mock server or wrapped response
                products = data.get('items', data.get('data', []))
            elif isinstance(data, list):
                # Direct array response
                products = data
            else:
                products = []

            execution_time_ms = int((time.time() - start_time) * 1000)

            metadata = {
                'url': url,
                'params': params,
                'response_code': response.status_code,
                'execution_time_ms': execution_time_ms
            }

            _logger.info(f'Fetched {len(products)} products from NetSuite')
            return products, metadata

        except requests.exceptions.Timeout as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                'url': url if 'url' in locals() else config.api_url,
                'params': params if 'params' in locals() else {},
                'response_code': None,
                'execution_time_ms': execution_time_ms,
                'error': str(e)
            }
            error = UserError(_('NetSuite API request timed out. Please try again.'))
            error.metadata = metadata  # Attach metadata to exception
            raise error
        except requests.exceptions.ConnectionError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                'url': url if 'url' in locals() else config.api_url,
                'params': params if 'params' in locals() else {},
                'response_code': None,
                'execution_time_ms': execution_time_ms,
                'error': str(e)
            }
            error = UserError(_('Could not connect to NetSuite API. Check your network connection.'))
            error.metadata = metadata  # Attach metadata to exception
            raise error
        except requests.exceptions.HTTPError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                'url': url if 'url' in locals() else config.api_url,
                'params': params if 'params' in locals() else {},
                'response_code': e.response.status_code if hasattr(e, 'response') else None,
                'execution_time_ms': execution_time_ms,
                'error': str(e)
            }
            error = UserError(_('NetSuite API error: %s') % str(e))
            error.metadata = metadata  # Attach metadata to exception
            raise error
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                'url': url if 'url' in locals() else config.api_url,
                'params': params if 'params' in locals() else {},
                'response_code': None,
                'execution_time_ms': execution_time_ms,
                'error': str(e)
            }
            error = UserError(_('Error fetching products from NetSuite: %s') % str(e))
            error.metadata = metadata  # Attach metadata to exception
            raise error

    def _get_netsuite_headers(self, config):
        """
        Generate HTTP headers for NetSuite REST API request

        Args:
            config: netsuite.config record

        Returns:
            dict: HTTP headers
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # For mock server - simple auth
        if 'localhost' in config.api_url or 'host.docker.internal' in config.api_url:
            headers['Authorization'] = f'Bearer mock-token'
            return headers

        # For real NetSuite - OAuth 1.0 (TBA)
        # In production, implement proper OAuth 1.0 signing here
        # For now, placeholder
        if config.consumer_key:
            headers['Authorization'] = f'OAuth realm="{config.account_id}"'
            # TODO: Add proper OAuth 1.0 signature

        return headers


class ProductTemplate(models.Model):
    """
    Extend product.template to add NetSuite sync fields
    """
    _inherit = 'product.template'

    x_netsuite_id = fields.Char(
        string='NetSuite ID',
        copy=False,
        help='NetSuite Internal ID (e.g., "12345"). Can be set manually or auto-populated when syncing from NetSuite. Required for EOD order/invoice sync.',
        index=True
    )

    x_netsuite_last_sync = fields.Datetime(
        string='Last Fetched',
        readonly=True,
        copy=False,
        help='Timestamp when product was last imported from NetSuite'
    )

    def action_sync_from_netsuite(self):
        """
        Manual sync button for products (fetch from NetSuite)
        """
        netsuite_ids = self.mapped('x_netsuite_id')
        netsuite_ids = [ns_id for ns_id in netsuite_ids if ns_id]

        if not netsuite_ids:
            raise UserError(_('No NetSuite IDs found for selected products'))

        result = self.env['netsuite.product.sync'].sync_products_from_netsuite(
            product_ids=netsuite_ids
        )

        if result['success']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Complete'),
                    'message': _(f"Updated {result['updated']} products from NetSuite"),
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Completed with Errors'),
                    'message': _(f"Updated {result['updated']}, Failed {result['failed']}"),
                    'type': 'warning',
                }
            }
