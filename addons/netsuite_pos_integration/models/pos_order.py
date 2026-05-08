# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
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

    def action_sync_to_netsuite(self):
        """Manual sync to NetSuite"""
        config = self.env['netsuite.config'].get_active_config()

        if not config.enable_manual_sync:
            raise UserError(_('Manual sync is disabled in configuration'))

        synced_count = 0
        failed_count = 0

        for order in self:
            try:
                # Create queue item
                queue_vals = {
                    'config_id': config.id,
                    'reference': order.name,
                    'record_type': 'sales_order',
                    'record_id': order.id,
                    'model': 'pos.order',
                    'status': 'pending',
                    'sync_mode': 'manual',
                    'priority': 5,
                }

                queue = self.env['netsuite.sync.queue'].create(queue_vals)

                # Update order status
                order.write({
                    'netsuite_sync_status': 'queued',
                    'netsuite_sync_count': order.netsuite_sync_count + 1,
                })

                # Process immediately
                queue._process_queue_items()

                synced_count += 1

            except Exception as e:
                _logger.error(f'Error syncing order {order.name}: {str(e)}')
                order.write({
                    'netsuite_sync_status': 'failed',
                    'netsuite_error': str(e),
                })
                failed_count += 1

        # Show notification
        if synced_count > 0:
            message = _('%d order(s) queued for sync') % synced_count
            if failed_count > 0:
                message += _(', %d failed') % failed_count

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Initiated'),
                    'message': message,
                    'type': 'success' if failed_count == 0 else 'warning',
                    'sticky': False,
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
        if not config or not config.enable_auto_sync:
            return

        for order in self:
            # Skip if already synced or queued
            if order.netsuite_sync_status in ['synced', 'queued']:
                continue

            # Determine sync mode
            if config.sync_mode == 'realtime':
                # Create queue item and process immediately
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

            elif config.sync_mode == 'batch':
                # Just create queue item for later batch processing
                queue_vals = {
                    'config_id': config.id,
                    'reference': order.name,
                    'record_type': 'sales_order',
                    'record_id': order.id,
                    'model': 'pos.order',
                    'status': 'pending',
                    'sync_mode': 'batch',
                    'priority': 10,
                }

                self.env['netsuite.sync.queue'].create(queue_vals)
                order.netsuite_sync_status = 'queued'

    @api.model
    def create(self, vals):
        """Override create to trigger auto-sync on creation"""
        order = super(PosOrder, self).create(vals)

        # Check if auto-sync on order creation is enabled
        config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
        if config and config.enable_auto_sync and order.state in ['paid', 'done', 'invoiced']:
            order._auto_sync_to_netsuite()

        return order

    def write(self, vals):
        """Override write to trigger auto-sync on state change"""
        result = super(PosOrder, self).write(vals)

        # Check if state changed to paid/done
        if 'state' in vals and vals.get('state') in ['paid', 'done', 'invoiced']:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if config and config.enable_auto_sync and config.sync_on_order_confirm:
                self._auto_sync_to_netsuite()

        return result
