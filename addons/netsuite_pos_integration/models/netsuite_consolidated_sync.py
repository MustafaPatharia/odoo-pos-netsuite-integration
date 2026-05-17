# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta, time
from collections import defaultdict

_logger = logging.getLogger(__name__)


class NetSuiteConsolidatedSync(models.AbstractModel):
    """
    Service for syncing consolidated Orders and Invoices from Odoo to NetSuite

    Key Features:
    - ONE consolidated Sales Order per shop per day
    - ONE consolidated Invoice per shop per day
    - Aggregates all line items by product
    - Uses NetSuite REST API for posting
    """
    _name = 'netsuite.consolidated.sync'
    _description = 'NetSuite Consolidated Sync Service'

    @api.model
    def sync_consolidated_orders(self, target_date=None, warehouse_ids=None, sync_all_dates=True):
        """
        Sync consolidated orders to NetSuite (one per shop per day)

        Args:
            target_date: Specific date to sync (if None and sync_all_dates=False, uses yesterday)
            warehouse_ids: List of warehouse IDs to sync (default: all)
            sync_all_dates: If True, syncs ALL past unsynced orders grouped by date (manual mode)
                           If False, syncs only target_date (cron mode)

        Returns:
            dict: Sync results
        """
        _logger.info('[NetSuite EOD Orders] ========== SYNC STARTED ==========')

        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_orders:
            raise UserError(_('Consolidated order sync is disabled in configuration'))

        _logger.info(f'[NetSuite EOD Orders] Sync mode: {"ALL DATES" if sync_all_dates else "SINGLE DATE"}')
        _logger.info(f'[NetSuite EOD Orders] Using config: {config.name} (API: {config.api_url})')

        # Create sync log
        now_utc = fields.Datetime.now()
        timestamp_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        start_time = datetime.now()

        sync_log = self.env['netsuite.sync.log'].create({
            'config_id': config.id,
            'reference': f'EOD Orders Sync {timestamp_str} (+00:00)',
            'record_type': 'eod_order',
            'record_id': 0,  # Bulk operation
            'status': 'processing',
            'sync_mode': 'manual',
            'request_method': 'POST',
        })

        # Get orders based on sync mode
        if sync_all_dates:
            # Manual mode: Get ALL past unsynced orders (exclude today)
            pos_orders = self._get_all_unsynced_orders(warehouse_ids)
        else:
            # Cron mode: Get orders for specific date only
            if not target_date:
                target_date = (datetime.now() - timedelta(days=1)).date()
            elif isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            pos_orders = self._get_orders_for_date(target_date, warehouse_ids)

        if not pos_orders:
            _logger.info('[NetSuite EOD Orders] No orders found for target date')
            sync_log.write({
                'status': 'success',
                'notes': 'No orders to sync',
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
            })
            return {
                'success': True,
                'message': 'No orders to sync',
                'total_shops': 0,
                'total_orders': 0,
                'synced': 0,
                'failed': 0
            }

        # CRITICAL VALIDATION: Check if all products have NetSuite IDs
        _logger.info('[NetSuite EOD Orders] Validating products have NetSuite IDs...')
        validation_result = self._validate_products_have_netsuite_ids(pos_orders)
        if not validation_result['valid']:
            product_list = '\n'.join(['   • ' + p for p in validation_result['products_without_ids'][:10]])
            if len(validation_result['products_without_ids']) > 10:
                product_list += f"\n   ... and {len(validation_result['products_without_ids']) - 10} more"

            error_msg = _(
                f"Cannot sync orders: {len(validation_result['products_without_ids'])} product(s) missing NetSuite IDs:\n\n"
                f"{product_list}\n\n"
                "Please add NetSuite ID manually:\n"
                "Inventory → Products → Edit → Set 'NetSuite ID' field"
            )
            _logger.error(f'[NetSuite EOD Orders] Validation failed: {len(validation_result["products_without_ids"])} products missing NetSuite IDs')
            sync_log.write({
                'status': 'failed',
                'error_message': error_msg,
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
            })
            raise ValidationError(error_msg)

        # Group orders by warehouse/shop and date
        orders_by_shop_and_date = self._group_orders_by_shop(pos_orders)

        _logger.info(f'[NetSuite EOD Orders] Found {len(orders_by_shop_and_date)} shop+date combinations with {len(pos_orders)} total orders')

        results = {
            'success': True,
            'total_combinations': len(orders_by_shop_and_date),
            'total_orders': len(pos_orders),
            'synced': 0,
            'failed': 0,
            'errors': [],
            'sync_details': []
        }

        # Process each shop+date combination
        for (warehouse_id, order_date), shop_orders in orders_by_shop_and_date.items():
            try:
                warehouse = self.env['stock.warehouse'].browse(warehouse_id)
                shop_name = warehouse.name
                _logger.info(f'[NetSuite EOD Orders] Processing: {shop_name} | {order_date} | {len(shop_orders)} orders')

                shop_result = self._sync_consolidated_order_for_shop(
                    config, warehouse_id, shop_orders, order_date
                )
                results['synced'] += 1
                results['sync_details'].append({
                    'shop': shop_name,
                    'date': str(order_date),
                    'orders': len(shop_orders),
                    'status': 'success',
                    'netsuite_id': shop_result.get('netsuite_id')
                })
                _logger.info(f'[NetSuite EOD Orders] ✓ Successfully synced {shop_name} - {order_date}')
            except Exception as e:
                results['failed'] += 1
                error_msg = f'Failed to sync {warehouse.name} - {order_date}: {str(e)}'
                results['errors'].append(error_msg)
                results['sync_details'].append({
                    'shop': warehouse.name if warehouse_id else 'Unknown',
                    'date': str(order_date),
                    'orders': len(shop_orders),
                    'status': 'failed',
                    'error': str(e)
                })
                _logger.error(f'[NetSuite EOD Orders] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0

        # Update sync log with final results
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        sync_log.write({
            'status': 'success' if results['success'] else ('partial' if results['synced'] > 0 else 'failed'),
            'error_message': '\n'.join(results['errors']) if results['errors'] else None,
            'response_payload': json.dumps(results, indent=2),
            'notes': f"Synced: {results['synced']}/{results['total_combinations']}, Orders: {results['total_orders']}, Failed: {results['failed']}",
            'execution_time_ms': execution_time_ms,
        })

        _logger.info('[NetSuite EOD Orders] ========== SYNC COMPLETED ==========')
        _logger.info(f'[NetSuite EOD Orders] Results - Synced: {results["synced"]}/{results["total_combinations"]}, Orders: {results["total_orders"]}, Failed: {results["failed"]}')

        return results

    @api.model
    def sync_consolidated_invoices(self, target_date=None, warehouse_ids=None):
        """
        Sync consolidated invoices to NetSuite (one per shop per day)

        Args:
            target_date: Date to sync (default: yesterday)
            warehouse_ids: List of warehouse IDs to sync (default: all)

        Returns:
            dict: Sync results
        """
        _logger.info('[NetSuite EOD Invoices] ========== SYNC STARTED ==========')

        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_invoices:
            raise UserError(_('Consolidated invoice sync is disabled in configuration'))

        # Determine target date
        if not target_date:
            target_date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        _logger.info(f'[NetSuite EOD Invoices] Target date: {target_date}, Warehouses: {warehouse_ids or "ALL"}')
        _logger.info(f'[NetSuite EOD Invoices] Using config: {config.name} (API: {config.api_url})')

        # Create sync log
        now_utc = fields.Datetime.now()
        timestamp_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        start_time = datetime.now()

        sync_log = self.env['netsuite.sync.log'].create({
            'config_id': config.id,
            'reference': f'EOD Invoices Sync {timestamp_str} (+00:00)',
            'record_type': 'eod_invoice',
            'record_id': 0,  # Bulk operation
            'status': 'processing',
            'sync_mode': 'manual',
            'request_method': 'POST',
        })

        # Get orders for target date (invoices are based on orders)
        pos_orders = self._get_orders_for_date(target_date, warehouse_ids)

        if not pos_orders:
            _logger.info('[NetSuite EOD Invoices] No orders found for target date')
            sync_log.write({
                'status': 'success',
                'notes': 'No invoices to sync',
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
            })
            return {
                'success': True,
                'message': 'No invoices to sync',
                'total_shops': 0,
                'total_orders': 0,
                'synced': 0,
                'failed': 0
            }

        # CRITICAL VALIDATION: Check if all products have NetSuite IDs
        _logger.info('[NetSuite EOD Invoices] Validating products have NetSuite IDs...')
        validation_result = self._validate_products_have_netsuite_ids(pos_orders)
        if not validation_result['valid']:
            product_list = '\n'.join(['   • ' + p for p in validation_result['products_without_ids'][:10]])
            if len(validation_result['products_without_ids']) > 10:
                product_list += f"\n   ... and {len(validation_result['products_without_ids']) - 10} more"

            error_msg = _(
                f"Cannot sync invoices: {len(validation_result['products_without_ids'])} product(s) missing NetSuite IDs:\n\n"
                f"{product_list}\n\n"
                "Please add NetSuite ID manually:\n"
                "Inventory → Products → Edit → Set 'NetSuite ID' field"
            )
            _logger.error(f'[NetSuite EOD Invoices] Validation failed: {len(validation_result["products_without_ids"])} products missing NetSuite IDs')
            sync_log.write({
                'status': 'failed',
                'error_message': error_msg,
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
            })
            raise ValidationError(error_msg)

        # Group orders by warehouse/shop
        orders_by_shop = self._group_orders_by_shop(pos_orders)

        _logger.info(f'[NetSuite EOD Invoices] Found {len(orders_by_shop)} shops with {len(pos_orders)} total orders')

        results = {
            'success': True,
            'total_shops': len(orders_by_shop),
            'total_orders': len(pos_orders),
            'synced': 0,
            'failed': 0,
            'errors': [],
            'sync_details': []
        }

        # Process each shop
        for warehouse_id, shop_orders in orders_by_shop.items():
            try:
                warehouse = self.env['stock.warehouse'].browse(warehouse_id)
                shop_name = warehouse.name
                _logger.info(f'[NetSuite EOD Invoices] Processing shop: {shop_name} ({len(shop_orders)} orders)')

                shop_result = self._sync_consolidated_invoice_for_shop(
                    config, warehouse_id, shop_orders, target_date
                )
                results['synced'] += 1
                results['sync_details'].append({
                    'shop': shop_name,
                    'orders': len(shop_orders),
                    'status': 'success',
                    'netsuite_id': shop_result.get('netsuite_invoice_id')
                })
                _logger.info(f'[NetSuite EOD Invoices] ✓ Successfully synced {shop_name}')
            except Exception as e:
                results['failed'] += 1
                error_msg = f'Failed to sync invoice for shop {warehouse_id}: {str(e)}'
                results['errors'].append(error_msg)
                results['sync_details'].append({
                    'shop': warehouse.name if warehouse_id else 'Unknown',
                    'orders': len(shop_orders),
                    'status': 'failed',
                    'error': str(e)
                })
                _logger.error(f'[NetSuite EOD Invoices] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0

        # Update sync log with final results
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        sync_log.write({
            'status': 'success' if results['success'] else ('partial' if results['synced'] > 0 else 'failed'),
            'error_message': '\n'.join(results['errors']) if results['errors'] else None,
            'response_payload': json.dumps(results, indent=2),
            'notes': f"Shops: {results['synced']}/{results['total_shops']}, Orders: {results['total_orders']}, Failed: {results['failed']}",
            'execution_time_ms': execution_time_ms,
        })

        _logger.info('[NetSuite EOD Invoices] ========== SYNC COMPLETED ==========')
        _logger.info(f'[NetSuite EOD Invoices] Results - Shops: {results["synced"]}/{results["total_shops"]}, Orders: {results["total_orders"]}, Failed: {results["failed"]}')

        return results

    def _get_all_unsynced_orders(self, warehouse_ids=None):
        """Get ALL past unsynced POS orders (excluding today)"""
        today_start = datetime.combine(datetime.now().date(), time.min)

        domain = [
            ('date_order', '<', today_start),  # Exclude today
            ('state', 'in', ['paid', 'done', 'invoiced']),
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        if warehouse_ids:
            domain.append(('config_id', 'in', warehouse_ids))

        orders = self.env['pos.order'].search(domain, order='date_order asc')
        _logger.info(f'[NetSuite EOD Orders] Found {len(orders)} unsynced orders from past dates')
        return orders

    def _get_orders_for_date(self, target_date, warehouse_ids=None):
        """Get POS orders for a specific date"""
        domain = [
            ('date_order', '>=', datetime.combine(target_date, time.min)),
            ('date_order', '<', datetime.combine(target_date + timedelta(days=1), time.min)),
            ('state', 'in', ['paid', 'done', 'invoiced']),
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        if warehouse_ids:
            domain.append(('config_id', 'in', warehouse_ids))

        return self.env['pos.order'].search(domain)

    def _group_orders_by_shop(self, pos_orders):
        """Group orders by warehouse/shop, then by date"""
        # Group by (warehouse_id, date)
        orders_by_shop_and_date = defaultdict(lambda: self.env['pos.order'])

        for order in pos_orders:
            # Get warehouse from session config
            warehouse_id = order.session_id.config_id.warehouse_id.id if order.session_id else None
            if warehouse_id:
                order_date = order.date_order.date()
                key = (warehouse_id, order_date)
                orders_by_shop_and_date[key] |= order

        return dict(orders_by_shop_and_date)

    def _validate_products_have_netsuite_ids(self, pos_orders):
        """
        Validate that all products in orders have NetSuite IDs

        Returns:
            dict: {
                'valid': True/False,
                'products_without_ids': ['Product Name 1', 'Product Name 2', ...],
                'total_products': 10,
                'products_with_ids': 8
            }
        """
        products_without_ids = set()
        all_products = set()

        for order in pos_orders:
            for line in order.lines:
                product = line.product_id
                all_products.add(product.id)

                if not product.x_netsuite_id:
                    products_without_ids.add(f"{product.name} ({product.default_code or 'No Code'})")

        return {
            'valid': len(products_without_ids) == 0,
            'products_without_ids': sorted(list(products_without_ids)),
            'total_products': len(all_products),
            'products_with_ids': len(all_products) - len(products_without_ids)
        }

    def _sync_consolidated_order_for_shop(self, config, warehouse_id, shop_orders, target_date):
        """
        Create ONE consolidated Sales Order in NetSuite for a shop for a day
        """
        # Get subsidiary mapping
        SubsidiaryMapping = self.env['netsuite.subsidiary.mapping']
        subsidiary_data = SubsidiaryMapping.get_subsidiary_for_warehouse(warehouse_id)

        if not subsidiary_data:
            raise ValidationError(_(
                f'No NetSuite subsidiary mapping found for warehouse ID {warehouse_id}. '
                'Please configure subsidiary mappings first.'
            ))

        # Aggregate line items by product
        aggregated_lines = self._aggregate_order_lines(shop_orders, config)

        # Prepare consolidated order payload
        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        order_date = target_date.strftime('%Y-%m-%d')

        payload = {
            'recordType': 'salesorder',
            'tranDate': order_date,
            'subsidiary': subsidiary_data['subsidiary_id'],
            'department': subsidiary_data.get('department_id'),
            'location': subsidiary_data.get('location_id'),
            'entity': self._get_default_customer_id(config),  # Default customer for POS
            'memo': f'Consolidated POS Order - {warehouse.name} - {order_date}',
            'custbody_pos_shop': warehouse.name,
            'custbody_pos_date': order_date,
            'custbody_pos_order_count': len(shop_orders),
            'items': aggregated_lines
        }

        # Send to NetSuite
        response = self._post_to_netsuite(config, '/app/site/hosting/restlet.nl?action=createSalesOrder', payload)

        if response.get('success'):
            netsuite_id = response.get('id')
            netsuite_tran_id = response.get('tranId')

            # Update all orders in this consolidation
            shop_orders.write({
                'netsuite_sync_status': 'synced',
                'netsuite_id': netsuite_id,
                'netsuite_tran_id': netsuite_tran_id,
                'netsuite_sync_date': fields.Datetime.now(),
                'netsuite_error': False,
            })

            return {
                'netsuite_id': netsuite_id,
                'netsuite_tran_id': netsuite_tran_id,
                'success': True
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            shop_orders.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })
            raise Exception(error_msg)

    def _sync_consolidated_invoice_for_shop(self, config, warehouse_id, shop_orders, target_date):
        """
        Create ONE consolidated Invoice in NetSuite for a shop for a day
        """
        # Get subsidiary mapping
        SubsidiaryMapping = self.env['netsuite.subsidiary.mapping']
        subsidiary_data = SubsidiaryMapping.get_subsidiary_for_warehouse(warehouse_id)

        if not subsidiary_data:
            raise ValidationError(_(
                f'No NetSuite subsidiary mapping found for warehouse ID {warehouse_id}'
            ))

        # Aggregate line items and payments
        aggregated_lines = self._aggregate_order_lines(shop_orders, config)
        aggregated_payments = self._aggregate_payments(shop_orders)

        # Prepare consolidated invoice payload
        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        invoice_date = target_date.strftime('%Y-%m-%d')

        payload = {
            'recordType': 'invoice',
            'tranDate': invoice_date,
            'subsidiary': subsidiary_data['subsidiary_id'],
            'department': subsidiary_data.get('department_id'),
            'location': subsidiary_data.get('location_id'),
            'entity': self._get_default_customer_id(config),
            'memo': f'Consolidated POS Invoice - {warehouse.name} - {invoice_date}',
            'custbody_pos_shop': warehouse.name,
            'custbody_pos_date': invoice_date,
            'custbody_pos_order_count': len(shop_orders),
            'items': aggregated_lines,
            'payments': aggregated_payments
        }

        # Send to NetSuite
        response = self._post_to_netsuite(config, '/app/site/hosting/restlet.nl?action=createEODInvoice', payload)

        if response.get('success'):
            netsuite_invoice_id = response.get('id')

            # Update orders
            shop_orders.write({
                'x_netsuite_invoice_id': netsuite_invoice_id,
                'x_netsuite_invoice_sync_date': fields.Datetime.now(),
            })

            return {
                'netsuite_invoice_id': netsuite_invoice_id,
                'success': True
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            raise Exception(error_msg)

    def _aggregate_order_lines(self, shop_orders, config):
        """
        Aggregate all order lines by product (sum quantities)

        Raises:
            ValidationError: If any product is missing NetSuite ID
        """
        product_totals = defaultdict(lambda: {'quantity': 0, 'amount': 0, 'product_id': None, 'name': ''})
        products_without_netsuite_id = []

        for order in shop_orders:
            for line in order.lines:
                product = line.product_id

                # CRITICAL: Validate that product has NetSuite ID
                if not product.x_netsuite_id:
                    if product.name not in products_without_netsuite_id:
                        products_without_netsuite_id.append(product.name)
                    continue  # Skip this line item

                product_key = product.x_netsuite_id

                product_totals[product_key]['quantity'] += line.qty
                product_totals[product_key]['amount'] += line.price_subtotal_incl
                product_totals[product_key]['product_id'] = product.x_netsuite_id
                product_totals[product_key]['name'] = product.name

        # Raise error if any products are missing NetSuite IDs
        if products_without_netsuite_id:
            product_list = '\n'.join([f'   • {p}' for p in products_without_netsuite_id[:15]])
            if len(products_without_netsuite_id) > 15:
                product_list += f'\n   ... and {len(products_without_netsuite_id) - 15} more'

            error_msg = _(
                f'Cannot sync: {len(products_without_netsuite_id)} product(s) missing NetSuite IDs:\n\n'
                f'{product_list}\n\n'
                'Please add NetSuite ID manually:\n'
                'Inventory → Products → Edit → Set "NetSuite ID" field'
            )
            _logger.error(f'[NetSuite EOD] Products missing NetSuite IDs: {products_without_netsuite_id}')
            raise ValidationError(error_msg)

        # Convert to NetSuite line format
        lines = []
        for product_key, totals in product_totals.items():
            # Calculate the rate as average: total_amount / total_quantity
            # This ensures rate × quantity = amount (consistent, no rounding issues)
            rate = totals['amount'] / totals['quantity'] if totals['quantity'] else 0

            lines.append({
                'item': totals['product_id'],  # Always use NetSuite ID (validated above)
                'quantity': totals['quantity'],
                'rate': round(rate, 2),  # Average rate per unit (tax-inclusive)
                'amount': round(totals['amount'], 2)  # Total amount (tax-inclusive)
            })

        return lines

    def _aggregate_payments(self, shop_orders):
        """
        Aggregate payment data by payment method
        """
        payment_totals = defaultdict(float)

        for order in shop_orders:
            for payment in order.payment_ids:
                payment_method = payment.payment_method_id.name
                payment_totals[payment_method] += payment.amount

        # Convert to NetSuite payment format
        payments = []
        for method, amount in payment_totals.items():
            # Get NetSuite payment method mapping
            mapping = self.env['netsuite.payment.method.mapping'].search([
                ('odoo_payment_method_name', '=', method)
            ], limit=1)

            payments.append({
                'paymentMethod': mapping.netsuite_payment_method_id if mapping else method,
                'amount': amount
            })

        return payments

    def _get_default_customer_id(self, config):
        """
        Get default customer ID for POS transactions
        TODO: Make this configurable
        """
        return '1'  # Default customer in NetSuite

    def _post_to_netsuite(self, config, endpoint, payload):
        """
        POST data to NetSuite REST API
        """
        url = f"{config.api_url.rstrip('/')}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Add authentication headers
        if config.consumer_key:
            headers['Authorization'] = f'OAuth realm="{config.account_id}"'

        timeout = (config.config_connection_timeout or 30, config.config_request_timeout or 120)

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error(f'NetSuite API error: {str(e)}', exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
