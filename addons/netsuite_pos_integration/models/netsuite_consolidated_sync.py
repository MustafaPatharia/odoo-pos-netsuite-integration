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
    def sync_consolidated_orders(self, target_date=None, warehouse_ids=None):
        """
        Sync consolidated orders to NetSuite (one per shop per day)

        Args:
            target_date: Date to sync (default: yesterday)
            warehouse_ids: List of warehouse IDs to sync (default: all)

        Returns:
            dict: Sync results
        """
        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_orders:
            raise UserError(_('Consolidated order sync is disabled in configuration'))

        # Determine target date (default to yesterday)
        if not target_date:
            target_date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        _logger.info(f'Starting consolidated order sync for date: {target_date}')

        # Get orders for target date
        pos_orders = self._get_orders_for_date(target_date, warehouse_ids)

        if not pos_orders:
            _logger.info(f'No orders found for date {target_date}')
            return {
                'success': True,
                'message': 'No orders to sync',
                'total_shops': 0,
                'total_orders': 0,
                'synced': 0,
                'failed': 0
            }

        # Group orders by warehouse/shop
        orders_by_shop = self._group_orders_by_shop(pos_orders)

        _logger.info(f'Found {len(orders_by_shop)} shops with {len(pos_orders)} total orders')

        results = {
            'success': True,
            'total_shops': len(orders_by_shop),
            'total_orders': len(pos_orders),
            'synced': 0,
            'failed': 0,
            'errors': []
        }

        # Process each shop
        for warehouse_id, shop_orders in orders_by_shop.items():
            try:
                self._sync_consolidated_order_for_shop(
                    config, warehouse_id, shop_orders, target_date
                )
                results['synced'] += 1
                _logger.info(f'Successfully synced consolidated order for shop {warehouse_id}')
            except Exception as e:
                results['failed'] += 1
                error_msg = f'Failed to sync shop {warehouse_id}: {str(e)}'
                results['errors'].append(error_msg)
                _logger.error(error_msg, exc_info=True)

        results['success'] = results['failed'] == 0

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
        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_invoices:
            raise UserError(_('Consolidated invoice sync is disabled in configuration'))

        # Determine target date
        if not target_date:
            target_date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        _logger.info(f'Starting consolidated invoice sync for date: {target_date}')

        # Get orders for target date (invoices are based on orders)
        pos_orders = self._get_orders_for_date(target_date, warehouse_ids)

        if not pos_orders:
            _logger.info(f'No orders found for date {target_date}')
            return {
                'success': True,
                'message': 'No invoices to sync',
                'total_shops': 0,
                'total_orders': 0,
                'synced': 0,
                'failed': 0
            }

        # Group orders by warehouse/shop
        orders_by_shop = self._group_orders_by_shop(pos_orders)

        results = {
            'success': True,
            'total_shops': len(orders_by_shop),
            'total_orders': len(pos_orders),
            'synced': 0,
            'failed': 0,
            'errors': []
        }

        # Process each shop
        for warehouse_id, shop_orders in orders_by_shop.items():
            try:
                self._sync_consolidated_invoice_for_shop(
                    config, warehouse_id, shop_orders, target_date
                )
                results['synced'] += 1
                _logger.info(f'Successfully synced consolidated invoice for shop {warehouse_id}')
            except Exception as e:
                results['failed'] += 1
                error_msg = f'Failed to sync invoice for shop {warehouse_id}: {str(e)}'
                results['errors'].append(error_msg)
                _logger.error(error_msg, exc_info=True)

        results['success'] = results['failed'] == 0

        return results

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
        """Group orders by warehouse/shop"""
        orders_by_shop = defaultdict(lambda: self.env['pos.order'])

        for order in pos_orders:
            # Get warehouse from session config
            warehouse_id = order.session_id.config_id.warehouse_id.id if order.session_id else None
            if warehouse_id:
                orders_by_shop[warehouse_id] |= order

        return dict(orders_by_shop)

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
        response = self._post_to_netsuite(config, '/api/salesorder', payload)

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

            # Log success
            self.env['netsuite.sync.log'].create({
                'config_id': config.id,
                'sync_type': 'consolidated_order',
                'status': 'success',
                'start_time': fields.Datetime.now(),
                'end_time': fields.Datetime.now(),
                'records_processed': len(shop_orders),
                'records_success': len(shop_orders),
                'request_data': json.dumps(payload, indent=2),
                'response_data': json.dumps(response, indent=2),
            })
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
        response = self._post_to_netsuite(config, '/api/invoice', payload)

        if response.get('success'):
            netsuite_invoice_id = response.get('id')

            # Update orders
            shop_orders.write({
                'x_netsuite_invoice_id': netsuite_invoice_id,
                'x_netsuite_invoice_sync_date': fields.Datetime.now(),
            })

            # Log success
            self.env['netsuite.sync.log'].create({
                'config_id': config.id,
                'sync_type': 'consolidated_invoice',
                'status': 'success',
                'start_time': fields.Datetime.now(),
                'end_time': fields.Datetime.now(),
                'records_processed': len(shop_orders),
                'records_success': len(shop_orders),
                'request_data': json.dumps(payload, indent=2),
                'response_data': json.dumps(response, indent=2),
            })
        else:
            error_msg = response.get('error', 'Unknown error')
            raise Exception(error_msg)

    def _aggregate_order_lines(self, shop_orders, config):
        """
        Aggregate all order lines by product (sum quantities)
        """
        product_totals = defaultdict(lambda: {'quantity': 0, 'amount': 0, 'product_id': None, 'price': 0})

        for order in shop_orders:
            for line in order.lines:
                product = line.product_id
                product_key = product.x_netsuite_id or product.default_code or str(product.id)

                product_totals[product_key]['quantity'] += line.qty
                product_totals[product_key]['amount'] += line.price_subtotal_incl
                product_totals[product_key]['product_id'] = product.x_netsuite_id
                product_totals[product_key]['price'] = line.price_unit

        # Convert to NetSuite line format
        lines = []
        for product_key, totals in product_totals.items():
            lines.append({
                'item': totals['product_id'] or product_key,
                'quantity': totals['quantity'],
                'rate': totals['price'],
                'amount': totals['amount']
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
