# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import time
from datetime import datetime, timedelta, time as dt_time
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

    # ============================================================================
    # HELPER METHODS - Logging & Notifications
    # ============================================================================

    def _log_debug(self, config, message):
        """Conditional debug logging based on config"""
        if config and config.config_debug_logging:
            _logger.info(message)

    def _log_error(self, message, exc_info=False):
        """Always log errors regardless of config"""
        _logger.error(message, exc_info=exc_info)

    def _send_notification_email(self, config, subject, body, is_success=True):
        """
        Send email notification if SMTP is configured and config enables it

        Args:
            config: NetSuite config object
            subject: Email subject
            body: Email body (HTML)
            is_success: True for success emails, False for failure emails
        """
        try:
            # Check if notifications are enabled
            if is_success:
                if not config.config_send_email_on_success:
                    return
            else:
                if not config.config_send_email_on_failure:
                    return

            # Check if recipients are configured
            if not config.config_notification_recipients:
                _logger.warning('[NetSuite Notification] No recipients configured')
                return

            # Check if SMTP is configured
            smtp_server = self.env['ir.mail_server'].sudo().search([], limit=1)
            if not smtp_server:
                _logger.warning('[NetSuite Notification] No SMTP server configured, skipping email')
                return

            # Parse recipients
            recipients = [email.strip() for email in config.config_notification_recipients.split(',') if email.strip()]
            if not recipients:
                return

            # Send email using Odoo's email system
            mail_values = {
                'subject': subject,
                'body_html': body,
                'email_to': ', '.join(recipients),
                'email_from': smtp_server.smtp_user or 'noreply@odoo.local',
                'auto_delete': False,
            }

            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            _logger.info(f'[NetSuite Notification] Email sent to {len(recipients)} recipient(s)')

        except Exception as e:
            _logger.error(f'[NetSuite Notification] Failed to send email: {str(e)}', exc_info=True)

    def _prepare_sync_log_payload(self, config, request_payloads=None, response_data=None):
        """
        Prepare sync log payload based on config logging flags

        Args:
            config: NetSuite config object
            request_payloads: List of request payloads (will be JSON stringified)
            response_data: Response data (will be JSON stringified)

        Returns:
            dict: Sync log data with conditional payloads
        """
        log_data = {}

        # Only include request payload if logging is enabled
        if config.config_log_request_payload and request_payloads is not None:
            log_data['request_payload'] = json.dumps(request_payloads, indent=2)

        # Only include response payload if logging is enabled
        if config.config_log_response_payload and response_data is not None:
            log_data['response_payload'] = json.dumps(response_data, indent=2)

        return log_data

    # ============================================================================
    # MAIN SYNC METHODS
    # ============================================================================

    @api.model
    def sync_consolidated_orders(self, target_date=None, warehouse_ids=None, sync_all_dates=True, sync_mode='manual'):
        """
        Sync consolidated orders to NetSuite (one per shop per day)

        Args:
            target_date: Specific date to sync (if None and sync_all_dates=False, uses yesterday)
            warehouse_ids: List of warehouse IDs to sync (default: all)
            sync_all_dates: If True, syncs ALL past unsynced orders grouped by date (manual mode)
                            If False, syncs only target_date (cron mode)
            sync_mode: 'manual' (button click) or 'scheduled' (cron job)

        Returns:
            dict: Sync results
        """
        self._log_debug(config, '[NetSuite EOD Orders] ========== SYNC STARTED ==========')

        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_orders:
            raise UserError(_('Consolidated order sync is disabled in configuration'))

        self._log_debug(config, f'[NetSuite EOD Orders] Sync mode: {"ALL DATES" if sync_all_dates else "SINGLE DATE"}')
        self._log_debug(config, f'[NetSuite EOD Orders] Using config: {config.name} (API: {config.api_url})')

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
            'sync_mode': sync_mode,
            'request_method': 'POST',
            'request_payload': '',  # Will be updated during sync
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
                'response_code': 200,
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
                'response_code': 400,
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
            'sync_details': [],
            'status_codes': [],  # Track all status codes
            'request_payloads': []  # Track all request payloads
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
                results['status_codes'].append(shop_result.get('status_code'))
                results['request_payloads'].append({
                    'shop': shop_name,
                    'date': str(order_date),
                    'payload': shop_result.get('payload')
                })
                results['sync_details'].append({
                    'shop': shop_name,
                    'date': str(order_date),
                    'orders': len(shop_orders),
                    'status': 'success',
                    'status_code': shop_result.get('status_code'),
                    'netsuite_id': shop_result.get('netsuite_id')
                })
                _logger.info(f'[NetSuite EOD Orders] ✓ Successfully synced {shop_name} - {order_date}')
            except Exception as e:
                results['failed'] += 1
                status_code = getattr(e, 'status_code', None)
                results['status_codes'].append(status_code)
                error_msg = f'Failed to sync {warehouse.name} - {order_date}: {str(e)}'
                results['errors'].append(error_msg)
                results['sync_details'].append({
                    'shop': warehouse.name if warehouse_id else 'Unknown',
                    'date': str(order_date),
                    'orders': len(shop_orders),
                    'status': 'failed',
                    'status_code': status_code,
                    'error': str(e)
                })
                _logger.error(f'[NetSuite EOD Orders] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0

        # Determine response code: 200 if all success, else first error status code or None
        response_code = 200 if results['success'] else (
            next((sc for sc in results['status_codes'] if sc is not None and sc != 200), None)
        )

        # Update sync log with final results
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        log_data = {
            'status': 'success' if results['success'] else ('partial' if results['synced'] > 0 else 'failed'),
            'error_message': '\n'.join(results['errors']) if results['errors'] else None,
            'notes': f"Synced: {results['synced']}/{results['total_combinations']}, Orders: {results['total_orders']}, Failed: {results['failed']}",
            'execution_time_ms': execution_time_ms,
            'response_code': response_code,
        }

        # Add conditional payloads based on config
        log_data.update(self._prepare_sync_log_payload(
            config,
            request_payloads=results.get('request_payloads', []),
            response_data=results
        ))

        sync_log.write(log_data)

        self._log_debug(config, '[NetSuite EOD Orders] ========== SYNC COMPLETED ==========')
        self._log_debug(config, f'[NetSuite EOD Orders] Results - Synced: {results["synced"]}/{results["total_combinations"]}, Orders: {results["total_orders"]}, Failed: {results["failed"]}')

        # Send email notification
        if results['success']:
            subject = f'✓ NetSuite Orders Sync Successful - {results["synced"]} sync(s)'
            body = f'''
                <h3>NetSuite Orders Sync Completed Successfully</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_combinations"]} shop+date combinations</li>
                    <li><strong>Total Orders:</strong> {results["total_orders"]}</li>
                    <li><strong>Failed:</strong> {results["failed"]}</li>
                    <li><strong>Execution Time:</strong> {execution_time_ms}ms</li>
                </ul>
            '''
            self._send_notification_email(config, subject, body, is_success=True)
        else:
            subject = f'✗ NetSuite Orders Sync Failed - {results["failed"]} error(s)'
            error_details = '<br>'.join(results.get('errors', []))
            body = f'''
                <h3 style="color: red;">NetSuite Orders Sync Failed</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_combinations"]}</li>
                    <li><strong>Failed:</strong> {results["failed"]}</li>
                    <li><strong>Errors:</strong><br>{error_details}</li>
                </ul>
            '''
            self._send_notification_email(config, subject, body, is_success=False)

        return results

    @api.model
    def sync_consolidated_invoices(self, target_date=None, warehouse_ids=None, sync_mode='manual'):
        """
        Sync consolidated INVOICES (account.move) to NetSuite (one per warehouse per day)

        This syncs account.move records (customer invoices), grouping them by warehouse/shop

        Args:
            target_date: Date to sync (default: yesterday)
            warehouse_ids: List of warehouse IDs to sync (default: all)
            sync_mode: 'manual' (button click) or 'scheduled' (cron job)

        Returns:
            dict: Sync results
        """
        self._log_debug(config, '[NetSuite EOD Invoices] ========== SYNC STARTED ==========')

        config = self.env['netsuite.config'].get_active_config()

        if not config.config_consolidate_invoices:
            raise UserError(_('Consolidated invoice sync is disabled in configuration'))

        # Determine target date
        if not target_date:
            target_date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        self._log_debug(config, f'[NetSuite EOD Invoices] Target date: {target_date}, Warehouses: {warehouse_ids or "ALL"}')
        self._log_debug(config, f'[NetSuite EOD Invoices] Using config: {config.name} (API: {config.api_url})')

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
            'sync_mode': sync_mode,
            'request_method': 'POST',
            'request_payload': '',  # Will be updated during sync
        })

        # Get invoices for target date
        invoices = self._get_invoices_for_date(target_date, warehouse_ids, config)

        if not invoices:
            _logger.info('[NetSuite EOD Invoices] No invoices found for target date')
            sync_log.write({
                'status': 'success',
                'notes': 'No invoices to sync',
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                'response_code': 200,
            })
            return {
                'success': True,
                'message': 'No invoices to sync',
                'total_warehouses': 0,
                'total_invoices': 0,
                'synced': 0,
                'failed': 0
            }

        # CRITICAL VALIDATION: Check if all products have NetSuite IDs
        _logger.info('[NetSuite EOD Invoices] Validating products have NetSuite IDs...')
        validation_result = self._validate_invoice_products_have_netsuite_ids(invoices)
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
                'response_code': 400,
            })
            raise ValidationError(error_msg)

        # Group invoices by warehouse and payment method
        invoices_grouped = self._group_invoices_by_warehouse_and_payment(invoices)

        _logger.info(f'[NetSuite EOD Invoices] Found {len(invoices_grouped)} groups (warehouse+payment) with {len(invoices)} total invoices')

        results = {
            'success': True,
            'total_groups': len(invoices_grouped),
            'total_invoices': len(invoices),
            'synced': 0,
            'failed': 0,
            'errors': [],
            'sync_details': [],
            'status_codes': [],
            'request_payloads': []
        }

        # Process each group (warehouse + payment method)
        for (warehouse_id, payment_method_id), group_invoices in invoices_grouped.items():
            try:
                warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
                warehouse_name = warehouse.name if warehouse else 'Default'
                _logger.info(f'[NetSuite EOD Invoices] Processing: {warehouse_name} | Payment Method: {payment_method_id} | {len(group_invoices)} invoices')

                group_result = self._sync_consolidated_invoice_for_warehouse(
                    config, warehouse_id, group_invoices, target_date, payment_method_id
                )
                results['synced'] += 1
                results['status_codes'].append(group_result.get('status_code'))
                results['request_payloads'].append({
                    'warehouse': warehouse_name,
                    'payment_method': payment_method_id,
                    'payload': group_result.get('payload')
                })
                results['sync_details'].append({
                    'warehouse': warehouse_name,
                    'payment_method': payment_method_id,
                    'invoices': len(group_invoices),
                    'status': 'success',
                    'status_code': group_result.get('status_code'),
                    'netsuite_id': group_result.get('netsuite_invoice_id')
                })
                _logger.info(f'[NetSuite EOD Invoices] ✓ Successfully synced {warehouse_name} - Payment: {payment_method_id}')
            except Exception as e:
                results['failed'] += 1
                status_code = getattr(e, 'status_code', None)
                results['status_codes'].append(status_code)
                error_msg = f'Failed to sync invoices for warehouse {warehouse_id}, payment {payment_method_id}: {str(e)}'
                results['errors'].append(error_msg)
                results['sync_details'].append({
                    'warehouse': warehouse_name if 'warehouse_name' in locals() else 'Unknown',
                    'payment_method': payment_method_id if 'payment_method_id' in locals() else 'Unknown',
                    'invoices': len(group_invoices),
                    'status': 'failed',
                    'status_code': status_code,
                    'error': str(e)
                })
                _logger.error(f'[NetSuite EOD Invoices] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0

        # Determine response code
        response_code = 200 if results['success'] else (
            next((sc for sc in results['status_codes'] if sc is not None and sc != 200), None)
        )

        # Update sync log
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        log_data = {
            'status': 'success' if results['success'] else ('partial' if results['synced'] > 0 else 'failed'),
            'error_message': '\n'.join(results['errors']) if results['errors'] else None,
            'notes': f"Groups: {results['synced']}/{results['total_groups']}, Invoices: {results['total_invoices']}, Failed: {results['failed']}",
            'execution_time_ms': execution_time_ms,
            'response_code': response_code,
        }

        # Add conditional payloads based on config
        log_data.update(self._prepare_sync_log_payload(
            config,
            request_payloads=results.get('request_payloads', []),
            response_data=results
        ))

        sync_log.write(log_data)

        self._log_debug(config, '[NetSuite EOD Invoices] ========== SYNC COMPLETED ==========')
        self._log_debug(config, f'[NetSuite EOD Invoices] Results - Groups: {results["synced"]}/{results["total_groups"]}, Invoices: {results["total_invoices"]}, Failed: {results["failed"]}')

        # Send email notification
        if results['success']:
            subject = f'✓ NetSuite Invoices Sync Successful - {results["synced"]} sync(s)'
            body = f'''
                <h3>NetSuite Invoices Sync Completed Successfully</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_groups"]} warehouse+payment groups</li>
                    <li><strong>Total Invoices:</strong> {results["total_invoices"]}</li>
                    <li><strong>Failed:</strong> {results["failed"]}</li>
                    <li><strong>Execution Time:</strong> {execution_time_ms}ms</li>
                </ul>
            '''
            self._send_notification_email(config, subject, body, is_success=True)
        else:
            subject = f'✗ NetSuite Invoices Sync Failed - {results["failed"]} error(s)'
            error_details = '<br>'.join(results.get('errors', []))
            body = f'''
                <h3 style="color: red;">NetSuite Invoices Sync Failed</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_groups"]}</li>
                    <li><strong>Failed:</strong> {results["failed"]}</li>
                    <li><strong>Errors:</strong><br>{error_details}</li>
                </ul>
            '''
            self._send_notification_email(config, subject, body, is_success=False)

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

        # Collect Odoo order IDs for custom field
        order_ids = [order.name for order in shop_orders]  # Order names/numbers

        # Prepare consolidated order payload
        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        order_date = target_date.strftime('%Y-%m-%d')

        payload = {
            'entity': {'id': str(self._get_default_customer_id(config))},
            'tranDate': order_date,
            'subsidiary': {'id': str(subsidiary_data['subsidiary_id'])},
            'currency': {'id': '1'},  # AED currency
            'memo': f'Consolidated POS Order - {warehouse.name} - {order_date}',
        }

        # Add optional fields if present
        if subsidiary_data.get('department_id'):
            payload['department'] = {'id': str(subsidiary_data['department_id'])}
        if subsidiary_data.get('location_id'):
            payload['location'] = {'id': str(subsidiary_data['location_id'])}

        # Add line items (must be after department/location)
        payload['item'] = {
            'items': aggregated_lines
        }

        # Add custom fields for Odoo order tracking
        payload['custbody_odoo_order_ids'] = order_ids
        payload['custbody_odoo_order_count'] = len(order_ids)

        if response.get('success'):
            netsuite_id = response.get('id')
            netsuite_tran_id = response.get('tranId')
            status_code = response.get('status_code', 200)

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
                'status_code': status_code,
                'success': True,
                'payload': payload  # Return payload for logging
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            status_code = response.get('status_code')
            shop_orders.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })
            error = Exception(error_msg)
            error.status_code = status_code  # Attach status code to exception
            raise error

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

        # Collect POS order IDs for custom field
        order_ids = [order.name for order in shop_orders]  # Order names/numbers

        payload = {
            'entity': {'id': str(self._get_default_customer_id(config))},
            'tranDate': invoice_date,
            'subsidiary': {'id': str(subsidiary_data['subsidiary_id'])},
            'currency': {'id': '1'},  # AED currency
            'memo': f'Consolidated POS Invoice - {warehouse.name} - {invoice_date}',
        }

        # Add optional classification fields BEFORE item (NetSuite requirement)
        if subsidiary_data.get('department_id'):
            payload['department'] = {'id': str(subsidiary_data['department_id'])}
        if subsidiary_data.get('location_id'):
            payload['location'] = {'id': str(subsidiary_data['location_id'])}

        # Add line items
        payload['item'] = {
            'items': aggregated_lines
        }

        # Custom fields for consolidation tracking
        payload['custbody_warehouse'] = warehouse.name
        payload['custbody_invoice_date'] = invoice_date
        payload['custbody_odoo_order_ids'] = order_ids
        payload['custbody_odoo_order_count'] = len(order_ids)

        # Add payments if present
        if aggregated_payments:
            payload['payments'] = aggregated_payments

        # Send to NetSuite
        response = self._post_to_netsuite(config, '/app/site/hosting/restlet.nl?action=createEODInvoice', payload)

        if response.get('success'):
            netsuite_invoice_id = response.get('id')
            status_code = response.get('status_code', 200)

            # Update orders
            shop_orders.write({
                'x_netsuite_invoice_id': netsuite_invoice_id,
                'x_netsuite_invoice_sync_date': fields.Datetime.now(),
            })

            return {
                'netsuite_invoice_id': netsuite_invoice_id,
                'status_code': status_code,
                'success': True,
                'payload': payload  # Return payload for logging
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            status_code = response.get('status_code')
            error = Exception(error_msg)
            error.status_code = status_code  # Attach status code to exception
            raise error

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
                'item': {'id': str(totals['product_id'])},  # NetSuite item reference
                'quantity': totals['quantity'],
                'rate': round(rate, 2),  # Unit price (tax-exclusive)
                'amount': round(totals['amount'], 2),  # Line total (tax-exclusive)
                'description': totals['name'],
                'taxCode': {'id': '5'}  # Default tax code (5% VAT) - should be configurable
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
        POST data to NetSuite REST API with retry logic

        Returns:
            dict: Response with 'success', 'status_code', 'retry_count', and data or 'error'
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

        # Retry configuration from NetSuite config
        retry_enabled = config.config_retry_enabled if hasattr(config, 'config_retry_enabled') else True
        max_retries = config.config_max_retries if hasattr(config, 'config_max_retries') else 3
        initial_delay_minutes = config.config_retry_delay if hasattr(config, 'config_retry_delay') else 5
        use_exponential_backoff = config.config_use_exponential_backoff if hasattr(config, 'config_use_exponential_backoff') else True
        backoff_multiplier = config.config_backoff_multiplier if hasattr(config, 'config_backoff_multiplier') else 2

        # If retry is disabled, only attempt once
        if not retry_enabled:
            max_retries = 0

        retry_count = 0
        last_error = None
        last_status_code = None

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    # Calculate delay based on backoff strategy
                    if use_exponential_backoff:
                        # Exponential backoff: initial_delay * (multiplier ^ (attempt-1)) minutes
                        delay_minutes = initial_delay_minutes * (backoff_multiplier ** (attempt - 1))
                    else:
                        # Linear backoff: initial_delay minutes each time
                        delay_minutes = initial_delay_minutes

                    delay_seconds = delay_minutes * 60
                    _logger.info(f'[NetSuite Retry] Attempt {attempt + 1}/{max_retries + 1} after {delay_minutes}min ({delay_seconds}s) delay')
                    time.sleep(delay_seconds)

                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                result = response.json()
                result['status_code'] = response.status_code
                result['retry_count'] = retry_count

                if retry_count > 0:
                    _logger.info(f'[NetSuite Retry] ✓ Success after {retry_count} retries')

                return result

            except requests.exceptions.HTTPError as e:
                retry_count += 1
                last_status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                last_error = str(e)

                # Only retry on 5xx errors or 429 (rate limit)
                if last_status_code and (last_status_code >= 500 or last_status_code == 429):
                    if attempt < max_retries:
                        _logger.warning(f'[NetSuite Retry] HTTP {last_status_code} - will retry ({attempt + 1}/{max_retries})')
                        continue
                else:
                    # 4xx errors (except 429) are not retryable
                    _logger.error(f'NetSuite API HTTPError (status={last_status_code}): {last_error} - NOT retrying')
                    break

            except requests.exceptions.RequestException as e:
                retry_count += 1
                last_status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                last_error = str(e)

                if attempt < max_retries:
                    _logger.warning(f'[NetSuite Retry] RequestException - will retry ({attempt + 1}/{max_retries}): {last_error}')
                    continue
                else:
                    _logger.error(f'NetSuite API RequestException after {retry_count} retries: {last_error}')
                    break

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                _logger.error(f'NetSuite API error: {last_error}', exc_info=True)
                break

        # All retries failed
        _logger.error(f'[NetSuite Retry] ✗ Failed after {retry_count} retries. Last error: {last_error}')
        return {
            'success': False,
            'error': last_error,
            'status_code': last_status_code,
            'retry_count': retry_count
        }

    # ============================================================================
    # INVOICE-SPECIFIC HELPER METHODS
    # ============================================================================

    def _get_invoices_for_date(self, target_date, warehouse_ids=None, config=None):
        """Get posted customer invoices (account.move) for a specific date"""
        domain = [
            ('invoice_date', '>=', target_date),
            ('invoice_date', '<', target_date + timedelta(days=1)),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['paid', 'in_payment']),  # Only paid invoices
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        # Note: warehouse_ids filter will be applied during grouping
        # as account.move doesn't have direct warehouse_id field

        invoices = self.env['account.move'].search(domain, order='invoice_date asc')

        # Filter by POS-only if configured
        if config and config.sync_only_pos_invoices:
            pos_invoices = self.env['account.move']
            for invoice in invoices:
                pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)
                if pos_order:
                    pos_invoices |= invoice
            invoices = pos_invoices
            _logger.info(f'[NetSuite EOD Invoices] Filtered to POS-only: {len(invoices)} invoices')

        # Validate all invoices have payment methods
        invalid_invoices = []
        for invoice in invoices:
            pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)
            if pos_order:
                if not pos_order.payment_ids:
                    invalid_invoices.append(invoice.name)
            # Skip validation for non-POS invoices if sync_only_pos_invoices is False

        if invalid_invoices:
            raise ValidationError(_(
                f"Cannot sync invoices: {len(invalid_invoices)} invoice(s) have no payment method:\n\n" +
                "\n".join([f"   • {inv}" for inv in invalid_invoices[:10]]) +
                (f"\n   ... and {len(invalid_invoices) - 10} more" if len(invalid_invoices) > 10 else "")
            ))

        _logger.info(f'[NetSuite EOD Invoices] Found {len(invoices)} valid unsynced invoices for {target_date}')
        return invoices

    def _group_invoices_by_warehouse(self, invoices):
        """
        Group invoices by warehouse

        For POS invoices: Use POS order's session config warehouse
        For non-POS invoices: Use company's default warehouse or None
        """
        invoices_by_warehouse = defaultdict(lambda: self.env['account.move'])

        for invoice in invoices:
            warehouse_id = None

            # Try to get warehouse from POS order
            pos_order = self.env['pos.order'].search([
                ('account_move', '=', invoice.id)
            ], limit=1)

            if pos_order and pos_order.session_id and pos_order.session_id.config_id:
                # POS invoice - use POS config's warehouse
                pos_config = pos_order.session_id.config_id
                if hasattr(pos_config, 'warehouse_id') and pos_config.warehouse_id:
                    warehouse_id = pos_config.warehouse_id.id

            # Fallback: use company's default warehouse
            if not warehouse_id:
                default_warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', invoice.company_id.id)
                ], limit=1)
                if default_warehouse:
                    warehouse_id = default_warehouse.id

            invoices_by_warehouse[warehouse_id] |= invoice

        return dict(invoices_by_warehouse)

    def _get_netsuite_payment_method_for_invoice(self, invoice):
        """
        Get NetSuite payment method ID for an invoice

        Returns:
            str: NetSuite payment method ID or None
        """
        # Get POS order linked to this invoice
        pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)

        if not pos_order or not pos_order.payment_ids:
            return None

        # Get the first payment method (skip multi-payment for now)
        payment = pos_order.payment_ids[0]
        odoo_payment_method_id = payment.payment_method_id.id

        # Look up NetSuite payment method mapping
        mapping = self.env['netsuite.payment.method.mapping'].search([
            ('odoo_payment_method_id', '=', odoo_payment_method_id)
        ], limit=1)

        if mapping and mapping.netsuite_payment_method_id:
            return mapping.netsuite_payment_method_id

        return None

    def _group_invoices_by_warehouse_and_payment(self, invoices):
        """
        Group invoices by warehouse and payment method

        Returns:
            dict: {
                (warehouse_id, netsuite_payment_method_id): [invoice1, invoice2, ...],
                ...
            }
        """
        grouped = defaultdict(lambda: self.env['account.move'])

        for invoice in invoices:
            warehouse_id = None

            # Get warehouse from POS order
            pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)

            if pos_order and pos_order.session_id and pos_order.session_id.config_id:
                pos_config = pos_order.session_id.config_id
                if hasattr(pos_config, 'warehouse_id') and pos_config.warehouse_id:
                    warehouse_id = pos_config.warehouse_id.id

            # Fallback: use company's default warehouse
            if not warehouse_id:
                default_warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', invoice.company_id.id)
                ], limit=1)
                if default_warehouse:
                    warehouse_id = default_warehouse.id

            # Get NetSuite payment method
            netsuite_payment_method = self._get_netsuite_payment_method_for_invoice(invoice)

            if not netsuite_payment_method:
                _logger.warning(f'[NetSuite EOD Invoices] Invoice {invoice.name} has no NetSuite payment method mapping, using default')
                netsuite_payment_method = '1'  # Default payment method

            group_key = (warehouse_id, netsuite_payment_method)
            grouped[group_key] |= invoice

        return dict(grouped)

    def _validate_invoice_products_have_netsuite_ids(self, invoices):
        """
        Validate that all products in invoices have NetSuite IDs

        Returns:
            dict: {
                'valid': True/False,
                'products_without_ids': ['Product Name 1', ...],
                'total_products': 10,
                'products_with_ids': 8
            }
        """
        products_without_ids = set()
        all_products = set()

        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue

                product = line.product_id
                if product:
                    all_products.add(product.id)

                    if not product.x_netsuite_id:
                        products_without_ids.add(f"{product.name} ({product.default_code or 'No Code'})")

        return {
            'valid': len(products_without_ids) == 0,
            'products_without_ids': sorted(list(products_without_ids)),
            'total_products': len(all_products),
            'products_with_ids': len(all_products) - len(products_without_ids)
        }

    def _sync_consolidated_invoice_for_warehouse(self, config, warehouse_id, invoices, target_date, payment_method_id):
        """
        Create ONE consolidated Invoice in NetSuite for a warehouse + payment method for a day
        Updates account.move records with NetSuite sync info
        """
        # Get subsidiary mapping
        SubsidiaryMapping = self.env['netsuite.subsidiary.mapping']
        subsidiary_data = SubsidiaryMapping.get_subsidiary_for_warehouse(warehouse_id) if warehouse_id else None

        if not subsidiary_data:
            # Use default subsidiary if no mapping found
            _logger.warning(f'No NetSuite subsidiary mapping found for warehouse ID {warehouse_id}, using defaults')
            subsidiary_data = {
                'subsidiary_id': '1',  # Default subsidiary
                'department_id': None,
                'location_id': None
            }

        # Aggregate line items from all invoices
        aggregated_lines = self._aggregate_invoice_lines(invoices, config)

        # Collect Odoo invoice IDs for custom field
        invoice_ids = [inv.id for inv in invoices]  # Internal database IDs

        # Prepare consolidated invoice payload
        warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
        warehouse_name = warehouse.name if warehouse else 'Default'
        invoice_date = target_date.strftime('%Y-%m-%d')

        payload = {
            'entity': {'id': str(self._get_default_customer_id(config))},
            'tranDate': invoice_date,
            'subsidiary': {'id': str(subsidiary_data['subsidiary_id'])},
            'currency': {'id': '1'},  # AED currency
            'paymentMethod': {'id': str(payment_method_id)},
            'memo': f'Consolidated Invoice - {warehouse_name} - {invoice_date}',
        }

        # Add optional fields if present
        if subsidiary_data.get('department_id'):
            payload['department'] = {'id': str(subsidiary_data['department_id'])}
        if subsidiary_data.get('location_id'):
            payload['location'] = {'id': str(subsidiary_data['location_id'])}

        # Add line items (must be after department/location)
        payload['item'] = {
            'items': aggregated_lines
        }

        # Add custom fields for Odoo invoice tracking
        payload['custbody_odoo_invoice_ids'] = invoice_ids
        payload['custbody_odoo_invoice_count'] = len(invoice_ids)

        # Send to NetSuite
        response = self._post_to_netsuite(config, '/app/site/hosting/restlet.nl?action=createEODInvoice', payload)

        if response.get('success'):
            netsuite_invoice_id = response.get('id')
            netsuite_tran_id = response.get('tranId')
            status_code = response.get('status_code', 200)

            # Update all invoices in this consolidation
            invoices.write({
                'netsuite_sync_status': 'synced',
                'netsuite_id': netsuite_invoice_id,
                'netsuite_tran_id': netsuite_tran_id,
                'netsuite_sync_date': fields.Datetime.now(),
                'netsuite_error': False,
            })

            return {
                'netsuite_invoice_id': netsuite_invoice_id,
                'netsuite_tran_id': netsuite_tran_id,
                'status_code': status_code,
                'success': True,
                'payload': payload
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            status_code = response.get('status_code')

            # Update invoices with error
            invoices.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })

            error = Exception(error_msg)
            error.status_code = status_code
            raise error

    def _aggregate_invoice_lines(self, invoices, config):
        """
        Aggregate all invoice lines by product (sum quantities and amounts)

        Raises:
            ValidationError: If any product is missing NetSuite ID
        """
        product_totals = defaultdict(lambda: {'quantity': 0, 'amount': 0, 'product_id': None, 'name': ''})
        products_without_netsuite_id = []

        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue

                product = line.product_id
                if not product:
                    continue

                # CRITICAL: Validate that product has NetSuite ID
                if not product.x_netsuite_id:
                    if product.name not in products_without_netsuite_id:
                        products_without_netsuite_id.append(product.name)
                    continue

                product_key = product.x_netsuite_id

                product_totals[product_key]['quantity'] = round(product_totals[product_key]['quantity'] + line.quantity, 2)
                product_totals[product_key]['amount'] = round(product_totals[product_key]['amount'] + line.price_subtotal, 2)
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
                'Please add NetSuite ID to products before syncing.'
            )
            raise ValidationError(error_msg)

        # Convert to NetSuite line items format
        items = []
        for product_id, totals in product_totals.items():
            items.append({
                'item': {'id': str(product_id)},  # NetSuite item reference
                'quantity': totals['quantity'],
                'rate': round(totals['amount'] / totals['quantity'], 2) if totals['quantity'] > 0 else 0,
                'amount': totals['amount'],
                'description': totals['name'],
                'taxCode': {'id': '5'}  # Default tax code (5% VAT) - should be configurable
            })

        return items
