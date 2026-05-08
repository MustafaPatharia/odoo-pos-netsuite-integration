# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NetSuiteManualSyncWizard(models.TransientModel):
    """
    Wizard for manual batch sync of orders
    """
    _name = 'netsuite.manual.sync.wizard'
    _description = 'NetSuite Manual Sync Wizard'

    order_ids = fields.Many2many(
        'pos.order',
        string='Orders to Sync',
        required=True
    )

    sync_mode = fields.Selection([
        ('individual', 'Individual (One by one)'),
        ('batch', 'Batch (Single request)'),
    ], string='Sync Mode', default='individual', required=True)

    force_resync = fields.Boolean(
        string='Force Resync',
        help='Resync even if already synced'
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-fill with selected orders"""
        res = super().default_get(fields_list)

        if self.env.context.get('active_model') == 'pos.order':
            order_ids = self.env.context.get('active_ids', [])
            res['order_ids'] = [(6, 0, order_ids)]

        return res

    def action_sync(self):
        """Execute sync"""
        self.ensure_one()

        if not self.order_ids:
            raise UserError(_('Please select at least one order to sync'))

        # Filter orders if not force resync
        orders_to_sync = self.order_ids
        if not self.force_resync:
            orders_to_sync = self.order_ids.filtered(
                lambda o: o.netsuite_sync_status != 'synced'
            )

        if not orders_to_sync:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Orders to Sync'),
                    'message': _('All selected orders are already synced'),
                    'type': 'info',
                    'sticky': False,
                }
            }

        # Reset if force resync
        if self.force_resync:
            orders_to_sync.write({
                'netsuite_sync_status': 'not_synced',
                'netsuite_id': False,
                'netsuite_tran_id': False,
            })

        # Perform sync
        if self.sync_mode == 'individual':
            orders_to_sync.action_sync_to_netsuite()
        else:
            # Batch sync
            config = self.env['netsuite.config'].get_active_config()
            self.env['netsuite.api.client'].batch_create_orders(orders_to_sync, config)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Initiated'),
                'message': _('%d order(s) queued for sync') % len(orders_to_sync),
                'type': 'success',
                'sticky': False,
            }
        }
