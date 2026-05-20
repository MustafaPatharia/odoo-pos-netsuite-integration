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


class NetSuiteOrdersSync(models.AbstractModel):
    """
    Service for syncing POS Orders from Odoo to NetSuite
    
    Supports:
    - Individual 1:1 sync (one Odoo order → one NetSuite sales order)
    - Consolidated N:1 sync (multiple orders per shop per day → one NetSuite sales order)
    - Uses NetSuite Standard REST API
    """
    _name = 'netsuite.orders.sync'
    _description = 'NetSuite Orders Sync Service'

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
        """Send email notification if SMTP is configured and config enables it"""
        try:
            if is_success:
                if not config.config_send_email_on_success:
                    return
            else:
                if not config.config_send_email_on_failure:
                    return

            if not config.config_notification_recipients:
                _logger.warning('[NetSuite Notification] No recipients configured')
                return

            smtp_server = self.env['ir.mail_server'].sudo().search([], limit=1)
            if not smtp_server:
                _logger.warning('[NetSuite Notification] No SMTP server configured, skipping email')
                return

            recipients = [email.strip() for email in config.config_notification_recipients.split(',') if email.strip()]
            if not recipients:
                return

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
        """Prepare sync log payload based on config logging flags"""
        log_data = {}

        if config.config_log_request_payload and request_payloads is not None:
            log_data['request_payload'] = json.dumps(request_payloads, indent=2)

        if config.config_log_response_payload and response_data is not None:
            log_data['response_payload'] = json.dumps(response_data, indent=2)

        return log_data

    # ============================================================================
    # MAIN SYNC METHOD
    # ============================================================================

    @api.model
    def sync_orders(self, target_date=None, warehouse_ids=None, sync_all_dates=True, sync_mode='manual'):
        """
        Sync POS orders to NetSuite
        
        Args:
            target_date: Specific date to sync
            warehouse_ids: List of warehouse IDs to sync (default: all)
            sync_all_dates: If True, syncs ALL past unsynced orders
            sync_mode: 'manual', 'scheduled', or 'realtime'
        
        Returns:
            dict: Sync results
        """
        config = self.env['netsuite.config'].get_active_config()

        # Cron jobs should only run in 'scheduled' integration mode
        if sync_mode == 'scheduled' and config.config_integration_mode != 'scheduled':
            _logger.info(f'[NetSuite Order Sync Cron] Skipped - Integration mode is "{config.config_integration_mode}", expected "scheduled"')
            return {'success': True, 'skipped': True, 'reason': f'Integration mode is {config.config_integration_mode}, not scheduled'}

        self._log_debug(config, '[NetSuite Orders] ========== SYNC STARTED ==========')

        # Consolidation is determined by config flag ONLY
        use_consolidation = config.config_consolidate_orders

        self._log_debug(config, f'[NetSuite Orders] Integration mode: {config.config_integration_mode}')
        self._log_debug(config, f'[NetSuite Orders] Consolidation enabled: {use_consolidation}')

        # Create sync log
        now_utc = fields.Datetime.now()
        timestamp_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        start_time = datetime.now()

        sync_log = self.env['netsuite.sync.log'].create({
            'config_id': config.id,
            'reference': f'Orders Sync {timestamp_str} (+00:00)',
            'record_type': 'eod_order',
            'record_id': 0,
            'status': 'processing',
            'sync_mode': sync_mode,
            'request_method': 'POST',
            'request_payload': '',
        })

        # Get orders based on sync mode and integration mode
        if sync_all_dates:
            if config.config_integration_mode == 'realtime':
                pos_orders = self._get_all_unsynced_orders_including_today(warehouse_ids)
                self._log_debug(config, '[NetSuite Orders] Realtime fallback: Including TODAY')
            else:
                pos_orders = self._get_all_unsynced_orders(warehouse_ids)
                self._log_debug(config, '[NetSuite Orders] Manual/Scheduled mode: Excluding TODAY')
        else:
            if not target_date:
                if config.config_integration_mode == 'realtime' and sync_mode == 'manual':
                    target_date = datetime.now().date()
                    self._log_debug(config, '[NetSuite Orders] Realtime fallback: Using TODAY')
                else:
                    target_date = (datetime.now() - timedelta(days=1)).date()
                    self._log_debug(config, '[NetSuite Orders] Scheduled/Manual mode: Using YESTERDAY')
            elif isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            pos_orders = self._get_orders_for_date(target_date, warehouse_ids)

        if not pos_orders:
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

        # Validate products have NetSuite IDs
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
            sync_log.write({
                'status': 'failed',
                'error_message': error_msg,
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                'response_code': 400,
            })
            raise ValidationError(error_msg)

        # Group orders based on consolidation setting
        if use_consolidation:
            _logger.info('[NetSuite Orders] Using CONSOLIDATED sync (N:1)')
            orders_by_shop_and_date = self._group_orders_by_shop(pos_orders)
        else:
            _logger.info('[NetSuite Orders] Using INDIVIDUAL sync (1:1)')
            orders_by_shop_and_date = {}
            for order in pos_orders:
                key = (order.config_id.warehouse_id.id, order.date_order.date(), order.id)
                orders_by_shop_and_date[key] = self.env['pos.order'].browse(order.id)

        results = {
            'success': True,
            'total_combinations': len(orders_by_shop_and_date),
            'total_orders': len(pos_orders),
            'synced': 0,
            'failed': 0,
            'errors': [],
            'sync_details': [],
            'status_codes': [],
            'request_payloads': []
        }

        # Process each group
        for key, shop_orders in orders_by_shop_and_date.items():
            try:
                if use_consolidation:
                    warehouse_id, order_date = key
                else:
                    warehouse_id, order_date, order_id = key

                warehouse = self.env['stock.warehouse'].browse(warehouse_id)
                
                shop_result = self._sync_order_for_shop(
                    config, warehouse_id, shop_orders, order_date
                )
                results['synced'] += 1
                results['status_codes'].append(shop_result.get('status_code'))
                results['request_payloads'].append({
                    'shop': warehouse.name,
                    'date': str(order_date),
                    'payload': shop_result.get('payload')
                })
                results['sync_details'].append({
                    'shop': warehouse.name,
                    'date': str(order_date),
                    'orders': len(shop_orders),
                    'status': 'success',
                    'status_code': shop_result.get('status_code'),
                    'netsuite_id': shop_result.get('netsuite_id')
                })
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
                _logger.error(f'[NetSuite Orders] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0
        response_code = 200 if results['success'] else (
            next((sc for sc in results['status_codes'] if sc is not None and sc != 200), None)
        )

        # Update sync log
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        log_data = {
            'status': 'success' if results['success'] else ('partial' if results['synced'] > 0 else 'failed'),
            'error_message': '\n'.join(results['errors']) if results['errors'] else None,
            'notes': f"Synced: {results['synced']}/{results['total_combinations']}, Orders: {results['total_orders']}, Failed: {results['failed']}",
            'execution_time_ms': execution_time_ms,
            'response_code': response_code,
        }

        log_data.update(self._prepare_sync_log_payload(
            config,
            request_payloads=results.get('request_payloads', []),
            response_data=results
        ))

        sync_log.write(log_data)

        # Send email notification
        if results['success']:
            subject = f'✓ NetSuite Orders Sync Successful - {results["synced"]} sync(s)'
            body = f'''
                <h3>NetSuite Orders Sync Completed Successfully</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_combinations"]}</li>
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

    # ============================================================================
    # HELPER METHODS - Order Fetching
    # ============================================================================

    def _get_all_unsynced_orders(self, warehouse_ids=None):
        """Get ALL past unsynced POS orders (excluding today)"""
        today_start = datetime.combine(datetime.now().date(), dt_time.min)

        domain = [
            ('date_order', '<', today_start),
            ('state', 'in', ['paid', 'done', 'invoiced']),
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        if warehouse_ids:
            domain.append(('config_id', 'in', warehouse_ids))

        orders = self.env['pos.order'].search(domain, order='date_order asc')
        _logger.info(f'[NetSuite Orders] Found {len(orders)} unsynced orders from past dates')
        return orders

    def _get_all_unsynced_orders_including_today(self, warehouse_ids=None):
        """Get ALL unsynced POS orders (INCLUDING today - for realtime fallback)"""
        domain = [
            ('state', 'in', ['paid', 'done', 'invoiced']),
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        if warehouse_ids:
            domain.append(('config_id', 'in', warehouse_ids))

        orders = self.env['pos.order'].search(domain, order='date_order asc')
        _logger.info(f'[NetSuite Orders] Found {len(orders)} unsynced orders (including today)')
        return orders

    def _get_orders_for_date(self, target_date, warehouse_ids=None):
        """Get POS orders for a specific date"""
        domain = [
            ('date_order', '>=', datetime.combine(target_date, dt_time.min)),
            ('date_order', '<', datetime.combine(target_date + timedelta(days=1), dt_time.min)),
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
        orders_by_shop_and_date = defaultdict(lambda: self.env['pos.order'])

        for order in pos_orders:
            warehouse_id = order.session_id.config_id.warehouse_id.id if order.session_id else None
            if warehouse_id:
                order_date = order.date_order.date()
                key = (warehouse_id, order_date)
                orders_by_shop_and_date[key] |= order

        return dict(orders_by_shop_and_date)

    def _validate_products_have_netsuite_ids(self, pos_orders):
        """Validate that all products in orders have NetSuite IDs"""
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

    # ============================================================================
    # SYNC EXECUTION
    # ============================================================================

    def _sync_order_for_shop(self, config, warehouse_id, shop_orders, target_date):
        """Create Sales Order in NetSuite for a shop"""
        SubsidiaryMapping = self.env['netsuite.subsidiary.mapping']
        subsidiary_data = SubsidiaryMapping.get_subsidiary_for_warehouse(warehouse_id)

        if not subsidiary_data:
            raise ValidationError(_(
                f'No NetSuite subsidiary mapping found for warehouse ID {warehouse_id}. '
                'Please configure subsidiary mappings first.'
            ))

        aggregated_lines = self._aggregate_order_lines(shop_orders, config)
        order_ids = [order.name for order in shop_orders]

        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        order_date = target_date.strftime('%Y-%m-%d')

        payload = {
            'entity': {'id': str(self._get_default_customer_id(config))},
            'tranDate': order_date,
            'subsidiary': {'id': str(subsidiary_data['subsidiary_id'])},
            'currency': {'id': '1'},
            'memo': f'POS Order - {warehouse.name} - {order_date}',
        }

        if subsidiary_data.get('department_id'):
            payload['department'] = {'id': str(subsidiary_data['department_id'])}
        if subsidiary_data.get('location_id'):
            payload['location'] = {'id': str(subsidiary_data['location_id'])}

        payload['item'] = {'items': aggregated_lines}
        payload['custbody_odoo_order_ids'] = order_ids
        payload['custbody_odoo_order_count'] = len(order_ids)

        response = self._post_to_netsuite(config, '/services/rest/record/v1/salesorder', payload)

        if response.get('id'):
            netsuite_id = response.get('id')
            netsuite_tran_id = response.get('tranId')
            status_code = response.get('status_code', 201)

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
                'payload': payload
            }
        else:
            error_msg = response.get('error', 'Unknown error')
            status_code = response.get('status_code')
            shop_orders.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })
            error = Exception(error_msg)
            error.status_code = status_code
            raise error

    def _aggregate_order_lines(self, shop_orders, config):
        """Aggregate all order lines by product"""
        product_totals = defaultdict(lambda: {'quantity': 0, 'amount': 0, 'product_id': None, 'name': ''})

        for order in shop_orders:
            for line in order.lines:
                product = line.product_id
                if not product.x_netsuite_id:
                    continue

                product_key = product.x_netsuite_id
                product_totals[product_key]['quantity'] += line.qty
                product_totals[product_key]['amount'] += line.price_subtotal_incl
                product_totals[product_key]['product_id'] = product.x_netsuite_id
                product_totals[product_key]['name'] = product.name

        lines = []
        for product_key, totals in product_totals.items():
            rate = totals['amount'] / totals['quantity'] if totals['quantity'] else 0

            lines.append({
                'item': {'id': str(totals['product_id'])},
                'quantity': totals['quantity'],
                'rate': round(rate, 2),
                'amount': round(totals['amount'], 2),
                'description': totals['name'],
                'taxCode': {'id': '5'}
            })

        return lines

    def _get_default_customer_id(self, config):
        """Get default customer ID for POS transactions"""
        return '1'

    def _post_to_netsuite(self, config, endpoint, payload):
        """POST data to NetSuite REST API with retry logic"""
        url = f"{config.api_url.rstrip('/')}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if config.consumer_key:
            headers['Authorization'] = f'OAuth realm="{config.account_id}"'

        timeout = (30, 120)

        retry_enabled = config.config_retry_enabled if hasattr(config, 'config_retry_enabled') else True
        max_retries = config.config_max_retries if hasattr(config, 'config_max_retries') else 3
        initial_delay_minutes = config.config_retry_delay if hasattr(config, 'config_retry_delay') else 5
        use_exponential_backoff = config.config_use_exponential_backoff if hasattr(config, 'config_use_exponential_backoff') else True
        backoff_multiplier = config.config_backoff_multiplier if hasattr(config, 'config_backoff_multiplier') else 2

        if not retry_enabled:
            max_retries = 0

        retry_count = 0
        last_error = None
        last_status_code = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    if use_exponential_backoff:
                        delay_minutes = initial_delay_minutes * (backoff_multiplier ** (attempt - 1))
                    else:
                        delay_minutes = initial_delay_minutes

                    delay_seconds = delay_minutes * 60
                    _logger.info(f'[NetSuite Retry] Attempt {attempt + 1}/{max_retries + 1} after {delay_minutes}min')
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

                if last_status_code and (last_status_code >= 500 or last_status_code == 429):
                    if attempt < max_retries:
                        _logger.warning(f'[NetSuite Retry] HTTP {last_status_code} - will retry')
                        continue
                else:
                    _logger.error(f'NetSuite API HTTPError (status={last_status_code}): {last_error}')
                    break

            except requests.exceptions.RequestException as e:
                retry_count += 1
                last_status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                last_error = str(e)

                if attempt < max_retries:
                    _logger.warning(f'[NetSuite Retry] RequestException - will retry: {last_error}')
                    continue
                else:
                    _logger.error(f'NetSuite API RequestException after {retry_count} retries: {last_error}')
                    break

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                _logger.error(f'NetSuite API error: {last_error}', exc_info=True)
                break

        _logger.error(f'[NetSuite Retry] ✗ Failed after {retry_count} retries. Last error: {last_error}')
        return {
            'success': False,
            'error': last_error,
            'status_code': last_status_code,
            'retry_count': retry_count
        }
