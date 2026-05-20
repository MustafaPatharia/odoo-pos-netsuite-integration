# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)


class NetSuiteInvoicesSync(models.AbstractModel):
    """
    Service for syncing Customer Invoices (account.move) from Odoo to NetSuite
    
    Supports:
    - Individual 1:1 sync (one Odoo invoice → one NetSuite invoice)
    - Consolidated N:1 sync (multiple invoices per warehouse/payment → one NetSuite invoice)
    - Uses NetSuite Standard REST API
    """
    _name = 'netsuite.invoices.sync'
    _description = 'NetSuite Invoices Sync Service'

    # ============================================================================
    # HELPER METHODS - Logging & Notifications
    # ============================================================================

    def _log_debug(self, config, message):
        """Conditional debug logging based on config"""
        if config and config.config_debug_logging:
            _logger.info(message)

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
                return

            smtp_server = self.env['ir.mail_server'].sudo().search([], limit=1)
            if not smtp_server:
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
    def sync_invoices(self, target_date=None, warehouse_ids=None, sync_mode='manual'):
        """
        Sync customer invoices to NetSuite
        
        Args:
            target_date: Date to sync (default: yesterday for scheduled/manual, today for realtime)
            warehouse_ids: List of warehouse IDs to sync (default: all)
            sync_mode: 'manual', 'scheduled', or 'realtime'
        
        Returns:
            dict: Sync results
        """
        config = self.env['netsuite.config'].get_active_config()

        # Cron jobs should only run in 'scheduled' integration mode
        if sync_mode == 'scheduled' and config.config_integration_mode != 'scheduled':
            _logger.info(f'[NetSuite Invoice Sync Cron] Skipped - Integration mode is "{config.config_integration_mode}"')
            return {'success': True, 'skipped': True, 'reason': f'Integration mode is {config.config_integration_mode}, not scheduled'}

        self._log_debug(config, '[NetSuite Invoices] ========== SYNC STARTED ==========')

        # Consolidation is determined by config flag ONLY
        use_consolidation = config.config_consolidate_invoices

        self._log_debug(config, f'[NetSuite Invoices] Integration mode: {config.config_integration_mode}')
        self._log_debug(config, f'[NetSuite Invoices] Consolidation enabled: {use_consolidation}')

        # Determine target date based on integration mode
        if not target_date:
            if config.config_integration_mode == 'realtime' and sync_mode == 'manual':
                target_date = datetime.now().date()
                self._log_debug(config, '[NetSuite Invoices] Realtime fallback: Using TODAY')
            else:
                target_date = (datetime.now() - timedelta(days=1)).date()
                self._log_debug(config, '[NetSuite Invoices] Scheduled/Manual mode: Using YESTERDAY')
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        # Create sync log
        now_utc = fields.Datetime.now()
        timestamp_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        start_time = datetime.now()

        sync_log = self.env['netsuite.sync.log'].create({
            'config_id': config.id,
            'reference': f'Invoices Sync {timestamp_str} (+00:00)',
            'record_type': 'eod_invoice',
            'record_id': 0,
            'status': 'processing',
            'sync_mode': sync_mode,
            'request_method': 'POST',
            'request_payload': '',
        })

        # Get invoices for target date
        invoices = self._get_invoices_for_date(target_date, warehouse_ids, config)

        if not invoices:
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

        # Validate products have NetSuite IDs
        validation_result = self._validate_invoice_products_have_netsuite_ids(invoices)
        if not validation_result['valid']:
            product_list = '\n'.join(['   • ' + p for p in validation_result['products_without_ids'][:10]])
            if len(validation_result['products_without_ids']) > 10:
                product_list += f"\n   ... and {len(validation_result['products_without_ids']) - 10} more"

            error_msg = _(
                f"Cannot sync invoices: {len(validation_result['products_without_ids'])} product(s) missing NetSuite IDs:\n\n"
                f"{product_list}\n\n"
                "Please add NetSuite ID manually"
            )
            sync_log.write({
                'status': 'failed',
                'error_message': error_msg,
                'execution_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                'response_code': 400,
            })
            raise ValidationError(error_msg)

        # Group invoices based on consolidation setting
        if use_consolidation:
            _logger.info('[NetSuite Invoices] Using CONSOLIDATED sync (N:1)')
            invoices_grouped = self._group_invoices_by_warehouse_and_payment(invoices)
            total_portions = sum(len(portions) for portions in invoices_grouped.values())
        else:
            _logger.info('[NetSuite Invoices] Using INDIVIDUAL sync (1:1)')
            invoices_grouped = {}
            for invoice in invoices:
                warehouse_id = invoice.pos_order_ids[0].config_id.warehouse_id.id if invoice.pos_order_ids else None
                key = (warehouse_id, None, invoice.id)
                invoices_grouped[key] = [{
                    'invoice': invoice,
                    'proportion': 1.0,
                    'payment_amount': invoice.amount_total,
                    'payment_method_id': None
                }]
            total_portions = len(invoices)

        results = {
            'success': True,
            'total_groups': len(invoices_grouped),
            'total_invoices': len(invoices),
            'total_portions': total_portions,
            'synced': 0,
            'failed': 0,
            'errors': [],
            'sync_details': [],
            'status_codes': [],
            'request_payloads': []
        }

        # Process each group
        for key, invoice_portions in invoices_grouped.items():
            try:
                if use_consolidation:
                    warehouse_id, payment_method_id = key
                else:
                    warehouse_id, payment_method_id, invoice_id = key

                warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
                warehouse_name = warehouse.name if warehouse else 'Default'

                group_result = self._sync_invoice_for_warehouse(
                    config, warehouse_id, invoice_portions, target_date, payment_method_id
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
                    'invoice_portions': len(invoice_portions),
                    'status': 'success',
                    'status_code': group_result.get('status_code'),
                    'netsuite_id': group_result.get('netsuite_invoice_id')
                })
            except Exception as e:
                results['failed'] += 1
                status_code = getattr(e, 'status_code', None)
                results['status_codes'].append(status_code)
                error_msg = f'Failed to sync invoices for warehouse {warehouse_id}: {str(e)}'
                results['errors'].append(error_msg)
                results['sync_details'].append({
                    'warehouse': warehouse_name if 'warehouse_name' in locals() else 'Unknown',
                    'payment_method': payment_method_id if 'payment_method_id' in locals() else 'Unknown',
                    'invoice_portions': len(invoice_portions) if 'invoice_portions' in locals() else 0,
                    'status': 'failed',
                    'status_code': status_code,
                    'error': str(e)
                })
                _logger.error(f'[NetSuite Invoices] ✗ {error_msg}', exc_info=True)

        results['success'] = results['failed'] == 0
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

        log_data.update(self._prepare_sync_log_payload(
            config,
            request_payloads=results.get('request_payloads', []),
            response_data=results
        ))

        sync_log.write(log_data)

        # Send email notification
        if results['success']:
            subject = f'✓ NetSuite Invoices Sync Successful - {results["synced"]} group(s)'
            body = f'''
                <h3>NetSuite Invoices Sync Completed Successfully</h3>
                <ul>
                    <li><strong>Synced:</strong> {results["synced"]}/{results["total_groups"]}</li>
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

    # ============================================================================
    # HELPER METHODS - Invoice Fetching
    # ============================================================================

    def _get_invoices_for_date(self, target_date, warehouse_ids=None, config=None):
        """Get posted customer invoices for a specific date"""
        domain = [
            ('invoice_date', '>=', target_date),
            ('invoice_date', '<', target_date + timedelta(days=1)),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['paid', 'in_payment']),
            '|',
            ('netsuite_sync_status', 'in', ['not_synced', 'failed']),
            ('netsuite_sync_status', '=', False),
        ]

        invoices = self.env['account.move'].search(domain, order='invoice_date asc')

        # Filter by POS-only if configured
        if config and config.sync_only_pos_invoices:
            pos_invoices = self.env['account.move']
            for invoice in invoices:
                pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)
                if pos_order:
                    pos_invoices |= invoice
            invoices = pos_invoices

        # Validate all invoices have payment methods
        invalid_invoices = []
        for invoice in invoices:
            pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)
            if pos_order and not pos_order.payment_ids:
                invalid_invoices.append(invoice.name)

        if invalid_invoices:
            raise ValidationError(_(
                f"Cannot sync invoices: {len(invalid_invoices)} invoice(s) have no payment method:\n\n" +
                "\n".join([f"   • {inv}" for inv in invalid_invoices[:10]])
            ))

        _logger.info(f'[NetSuite Invoices] Found {len(invoices)} valid unsynced invoices for {target_date}')
        return invoices

    def _get_payment_proportions_for_invoice(self, invoice):
        """Calculate payment method proportions for an invoice"""
        pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)

        if not pos_order or not pos_order.payment_ids:
            return []

        total_amount = sum(payment.amount for payment in pos_order.payment_ids)
        if total_amount == 0:
            return []

        proportions = []
        for payment in pos_order.payment_ids:
            mapping = self.env['netsuite.payment.method.mapping'].search([
                ('odoo_payment_method_id', '=', payment.payment_method_id.id)
            ], limit=1)

            netsuite_payment_method = mapping.netsuite_payment_method_id if mapping else '1'

            proportions.append({
                'payment_method_id': netsuite_payment_method,
                'amount': payment.amount,
                'proportion': payment.amount / total_amount
            })

        return proportions

    def _group_invoices_by_warehouse_and_payment(self, invoices):
        """Group invoices by warehouse and payment method"""
        grouped = defaultdict(list)

        for invoice in invoices:
            warehouse_id = None

            pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)

            if pos_order and pos_order.session_id and pos_order.session_id.config_id:
                pos_config = pos_order.session_id.config_id
                if hasattr(pos_config, 'warehouse_id') and pos_config.warehouse_id:
                    warehouse_id = pos_config.warehouse_id.id

            if not warehouse_id:
                default_warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', invoice.company_id.id)
                ], limit=1)
                if default_warehouse:
                    warehouse_id = default_warehouse.id

            payment_proportions = self._get_payment_proportions_for_invoice(invoice)

            if not payment_proportions:
                payment_proportions = [{'payment_method_id': '1', 'amount': 0, 'proportion': 1.0}]

            for payment_info in payment_proportions:
                group_key = (warehouse_id, payment_info['payment_method_id'])
                grouped[group_key].append({
                    'invoice': invoice,
                    'proportion': payment_info['proportion'],
                    'payment_amount': payment_info['amount']
                })

        return dict(grouped)

    def _validate_invoice_products_have_netsuite_ids(self, invoices):
        """Validate that all products in invoices have NetSuite IDs"""
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

    # ============================================================================
    # SYNC EXECUTION
    # ============================================================================

    def _sync_invoice_for_warehouse(self, config, warehouse_id, invoice_portions, target_date, payment_method_id):
        """Create Invoice in NetSuite for a warehouse + payment method"""
        SubsidiaryMapping = self.env['netsuite.subsidiary.mapping']
        subsidiary_data = SubsidiaryMapping.get_subsidiary_for_warehouse(warehouse_id) if warehouse_id else None

        if not subsidiary_data:
            subsidiary_data = {
                'subsidiary_id': '1',
                'department_id': None,
                'location_id': None
            }

        aggregated_lines = self._aggregate_invoice_lines_proportional(invoice_portions, config)

        unique_invoices = list(set(portion['invoice'] for portion in invoice_portions))
        invoice_ids = [inv.id for inv in unique_invoices]

        warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
        warehouse_name = warehouse.name if warehouse else 'Default'
        invoice_date = target_date.strftime('%Y-%m-%d')

        customer_id = self._get_customer_for_payment_method(config, payment_method_id)

        payload = {
            'entity': {'id': str(customer_id)},
            'tranDate': invoice_date,
            'subsidiary': {'id': str(subsidiary_data['subsidiary_id'])},
            'currency': {'id': '1'},
            'paymentMethod': {'id': str(payment_method_id)},
            'memo': f'Invoice - {warehouse_name} - {invoice_date}',
        }

        if subsidiary_data.get('department_id'):
            payload['department'] = {'id': str(subsidiary_data['department_id'])}
        if subsidiary_data.get('location_id'):
            payload['location'] = {'id': str(subsidiary_data['location_id'])}

        payload['item'] = {'items': aggregated_lines}
        payload['custbody_odoo_invoice_ids'] = invoice_ids
        payload['custbody_odoo_invoice_count'] = len(invoice_ids)
        payload['custbody_payment_type'] = str(payment_method_id)

        response = self._post_to_netsuite(config, '/services/rest/record/v1/invoice', payload)

        if response.get('id'):
            netsuite_invoice_id = response.get('id')
            netsuite_tran_id = response.get('tranId')
            status_code = response.get('status_code', 201)

            invoices_recordset = self.env['account.move'].browse([inv.id for inv in unique_invoices])
            invoices_recordset.write({
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

            invoices_recordset = self.env['account.move'].browse([inv.id for inv in unique_invoices])
            invoices_recordset.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })

            error = Exception(error_msg)
            error.status_code = status_code
            raise error

    def _aggregate_invoice_lines_proportional(self, invoice_portions, config):
        """Aggregate invoice lines with proportional amounts for split-payment invoices"""
        product_totals = defaultdict(lambda: {'quantity': 0, 'amount': 0, 'product_id': None, 'name': ''})

        for portion_data in invoice_portions:
            invoice = portion_data['invoice']
            proportion = portion_data['proportion']

            for line in invoice.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue

                product = line.product_id
                if not product or not product.x_netsuite_id:
                    continue

                product_key = product.x_netsuite_id

                proportional_qty = line.quantity * proportion
                proportional_amount = line.price_subtotal * proportion

                product_totals[product_key]['quantity'] += proportional_qty
                product_totals[product_key]['amount'] += proportional_amount
                product_totals[product_key]['product_id'] = product.x_netsuite_id
                product_totals[product_key]['name'] = product.name

        items = []
        for product_id, totals in product_totals.items():
            items.append({
                'item': {'id': str(product_id)},
                'quantity': round(totals['quantity'], 3),
                'rate': round(totals['amount'] / totals['quantity'], 2) if totals['quantity'] > 0 else 0,
                'amount': round(totals['amount'], 2),
                'description': totals['name'],
                'taxCode': {'id': '5'}
            })

        return items

    def _get_customer_for_payment_method(self, config, payment_method_id):
        """Get NetSuite customer entity ID based on payment method"""
        payment_customer_map = {
            '1': '1',
            '2': '2',
            '3': '3',
        }
        return payment_customer_map.get(str(payment_method_id), '1')

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
                    time.sleep(delay_seconds)

                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                result = response.json()
                result['status_code'] = response.status_code
                result['retry_count'] = retry_count

                return result

            except requests.exceptions.HTTPError as e:
                retry_count += 1
                last_status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                last_error = str(e)

                if last_status_code and (last_status_code >= 500 or last_status_code == 429):
                    if attempt < max_retries:
                        continue
                else:
                    break

            except requests.exceptions.RequestException as e:
                retry_count += 1
                last_status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                last_error = str(e)

                if attempt < max_retries:
                    continue
                else:
                    break

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                break

        return {
            'success': False,
            'error': last_error,
            'status_code': last_status_code,
            'retry_count': retry_count
        }
