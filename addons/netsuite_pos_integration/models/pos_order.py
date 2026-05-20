# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """
    Extension of POS Order for NetSuite integration
    """
    _inherit = 'pos.order'

    netsuite_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('queued', 'Queued'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ], string='NetSuite Status', default='not_synced', copy=False, tracking=True)

    netsuite_id = fields.Char(
        string='NetSuite ID',
        copy=False,
        readonly=True,
        help='Internal ID in NetSuite'
    )

    netsuite_tran_id = fields.Char(
        string='NetSuite Transaction ID',
        copy=False,
        readonly=True,
        help='Transaction number in NetSuite (e.g., SO-12345)'
    )

    netsuite_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        copy=False
    )

    netsuite_error = fields.Text(
        string='Sync Error',
        readonly=True,
        copy=False
    )

    netsuite_sync_count = fields.Integer(
        string='Sync Attempts',
        default=0,
        copy=False
    )

    # Invoice sync fields (for consolidated invoice sync)
    x_netsuite_invoice_id = fields.Char(
        string='NetSuite Invoice ID',
        readonly=True,
        copy=False,
        help='NetSuite Internal ID of the consolidated invoice'
    )

    x_netsuite_invoice_sync_date = fields.Datetime(
        string='Invoice Sync Date',
        readonly=True,
        copy=False,
        help='Date when this order was synced as part of a consolidated invoice'
    )

    def action_sync_to_netsuite(self):
        """
        Batch sync to NetSuite - Creates ONE consolidated invoice per shop per day
        This is the manual version of the end-of-day cron job
        """
        config = self.env['netsuite.config'].get_active_config()

        if not config or not config.netsuite_config:
            raise UserError(_('NetSuite configuration not loaded. Please fetch configuration first.'))

        # Get EOD time from config
        eod_time_str = config.config_end_of_day_sync_time
        if not eod_time_str:
            raise UserError(_('End-of-day sync time not configured in NetSuite'))

        # Get current time in user's timezone
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        now_utc = datetime.utcnow()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)
        today = now_local.date()

        # Filter out today's orders and already synced orders
        orders_to_process = self.browse()
        today_orders_count = 0
        already_synced_count = 0

        for order in self:
            # Skip already synced
            if order.netsuite_sync_status == 'synced':
                already_synced_count += 1
                continue

            # Get order date in local timezone
            order_date_utc = order.date_order
            order_date_local = pytz.utc.localize(order_date_utc).astimezone(tz)
            order_date = order_date_local.date()

            if order_date < today:
                orders_to_process |= order
            else:
                today_orders_count += 1

        # If user selected ONLY today's orders
        if today_orders_count > 0 and not orders_to_process:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("⏰ Cannot Sync Today's Orders"),
                    'message': _("Orders can only be synced after %s.\\n\\nToday's orders will be available for sync tomorrow.") % eod_time_str,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not orders_to_process:
            msg = _('No orders to sync.')
            if already_synced_count > 0:
                msg += _(' %d order(s) already synced.') % already_synced_count
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('ℹ️ Info'),
                    'message': msg,
                    'type': 'info',
                    'sticky': False,
                }
            }

        # Group orders by shop and date
        grouped_orders = {}
        for order in orders_to_process:
            # Get order date
            order_date_utc = order.date_order
            order_date_local = pytz.utc.localize(order_date_utc).astimezone(tz)
            business_day = order_date_local.date()

            # Get shop (POS config)
            shop_id = order.session_id.config_id.id if order.session_id and order.session_id.config_id else 'default'
            shop_name = order.session_id.config_id.name if order.session_id and order.session_id.config_id else 'Default Shop'

            key = (business_day, shop_id, shop_name)
            if key not in grouped_orders:
                grouped_orders[key] = []
            grouped_orders[key].append(order)

        # Create consolidated invoices
        api_client = self.env['netsuite.api.client']
        total_invoices_created = 0
        total_orders_synced = 0
        failed_invoices = []

        for (business_day, shop_id, shop_name), orders in grouped_orders.items():
            _logger.info(f"Creating consolidated invoice for {shop_name} on {business_day}: {len(orders)} orders")

            # Prepare consolidated invoice data
            invoice_data = {
                'tranDate': business_day.strftime('%Y-%m-%d'),
                'externalId': f'ODOO-MANUAL-{business_day.strftime("%Y%m%d")}-SHOP-{shop_id}',
                'shop': shop_name,
                'orders': [
                    {
                        'orderId': order.id,
                        'orderName': order.name,
                        'amount': order.amount_total,
                        'date': order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
                    } for order in orders
                ],
                'totalAmount': sum(order.amount_total for order in orders),
                'orderCount': len(orders),
            }

            # Make API request
            success, response_data, error_msg, status_code, execution_time = api_client._make_request(
                config, 'app/site/hosting/restlet.nl?action=createEODInvoice', 'POST', invoice_data
            )

            if success:
                # Mark all orders as synced
                netsuite_invoice_id = response_data.get('internalId')
                netsuite_tran_id = response_data.get('tranId')

                for order in orders:
                    order.write({
                        'netsuite_sync_status': 'synced',
                        'netsuite_id': netsuite_invoice_id,
                        'netsuite_tran_id': netsuite_tran_id,
                        'netsuite_sync_date': datetime.now(),
                        'netsuite_error': False,
                    })

                total_invoices_created += 1
                total_orders_synced += len(orders)

                # Log the sync
                api_client._log_sync(
                    config, f'MANUAL-{business_day}-SHOP-{shop_id}', 'eod_invoice',
                    0, 'pos.order', 'success', 'create',
                    f"{config.api_url}/app/site/hosting/restlet.nl?action=createEODInvoice",
                    'POST', invoice_data, response_data, None,
                    status_code, execution_time, netsuite_invoice_id
                )
            else:
                _logger.error(f"Failed to sync invoice for {shop_name} on {business_day}: {error_msg}")

                # Mark orders as failed
                for order in orders:
                    order.write({
                        'netsuite_sync_status': 'failed',
                        'netsuite_error': f'Consolidated sync failed: {error_msg}',
                    })

                failed_invoices.append(f"{shop_name} ({business_day})")

                # Log the failure
                api_client._log_sync(
                    config, f'MANUAL-{business_day}-SHOP-{shop_id}', 'eod_invoice',
                    0, 'pos.order', 'failed', 'create',
                    f"{config.api_url}/app/site/hosting/restlet.nl?action=createEODInvoice",
                    'POST', invoice_data, response_data, error_msg,
                    status_code, execution_time, None
                )

        # Show summary notification
        title = _('✅ Sync Complete')
        message_parts = []

        if total_invoices_created > 0:
            message_parts.append(
                _('%d consolidated invoice(s) created for %d order(s)') % (total_invoices_created, total_orders_synced)
            )

        if failed_invoices:
            title = _('⚠️ Sync Completed with Errors')
            message_parts.append(_('Failed: %s') % ', '.join(failed_invoices))

        if today_orders_count > 0:
            message_parts.append(_('%d order(s) from today skipped') % today_orders_count)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': '\\n'.join(message_parts),
                'type': 'success' if not failed_invoices else 'warning',
                'sticky': True if failed_invoices else False,
            }
        }

    def action_force_resync(self):
        """Force resync even if already synced"""
        for order in self:
            order.write({
                'netsuite_sync_status': 'not_synced',
                'netsuite_id': False,
                'netsuite_tran_id': False,
                'netsuite_error': False,
            })

        return self.action_sync_to_netsuite()

    def action_view_netsuite_logs(self):
        """View NetSuite sync logs for this order"""
        self.ensure_one()
        return {
            'name': _('NetSuite Sync Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.log',
            'view_mode': 'tree,form',
            'domain': [('reference', '=', self.name)],
            'context': {'default_reference': self.name}
        }

    def action_view_sync_queue(self):
        """View sync queue items for this order"""
        self.ensure_one()
        return {
            'name': _('Sync Queue'),
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.queue',
            'view_mode': 'tree,form',
            'domain': [('reference', '=', self.name)],
        }

    def _auto_sync_to_netsuite(self):
        """Automatically sync order to NetSuite based on configuration"""
        config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
        # Only sync if realtime mode is enabled
        if not config or config.config_integration_mode != 'realtime':
            return

        for order in self:
            # Skip if already synced or queued
            if order.netsuite_sync_status in ['synced', 'queued']:
                continue

            # Create queue item for realtime processing
            queue_vals = {
                'config_id': config.id,
                'reference': order.name,
                'record_type': 'sales_order',
                'record_id': order.id,
                'model': 'pos.order',
                'status': 'pending',
                'sync_mode': 'realtime',
                'priority': 10,
            }

            queue = self.env['netsuite.sync.queue'].create(queue_vals)
            order.netsuite_sync_status = 'queued'

            # Process in background (commit first to avoid blocking UI)
            self.env.cr.commit()
            queue._process_queue_items()

    @api.model
    def create(self, vals):
        """Override create to trigger auto-sync on creation"""
        order = super(PosOrder, self).create(vals)

        # Realtime mode: sync immediately when order is confirmed
        config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
        if config and config.config_integration_mode == 'realtime' and order.state in ['paid', 'done', 'invoiced']:
            order._auto_sync_to_netsuite()

        return order

    def write(self, vals):
        """Override write to trigger auto-sync on state change"""
        result = super(PosOrder, self).write(vals)

        # Realtime mode: sync immediately when order state changes to confirmed
        if 'state' in vals and vals.get('state') in ['paid', 'done', 'invoiced']:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if config and config.config_integration_mode == 'realtime':
                self._auto_sync_to_netsuite()

        return result
