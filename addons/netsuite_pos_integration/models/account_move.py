# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """
    Extension of Account Move (Invoice) for NetSuite integration
    """
    _inherit = 'account.move'

    netsuite_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('queued', 'Queued'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ], string='NetSuite Status', default='not_synced', copy=False, tracking=True,
       help='Sync status of this invoice to NetSuite')

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
        help='Transaction number in NetSuite (e.g., INV-12345)'
    )

    netsuite_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        copy=False,
        help='Date and time when this invoice was last synced to NetSuite'
    )

    netsuite_error = fields.Text(
        string='Sync Error',
        readonly=True,
        copy=False,
        help='Last error message from NetSuite sync attempt'
    )

    netsuite_sync_count = fields.Integer(
        string='Sync Attempts',
        default=0,
        copy=False,
        help='Number of times sync has been attempted'
    )

    def action_view_netsuite_sync_log(self):
        """
        View NetSuite sync logs for this invoice
        """
        self.ensure_one()

        return {
            'name': _('NetSuite Sync Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.log',
            'view_mode': 'tree,form',
            'domain': [
                ('record_type', '=', 'invoice'),
                ('record_id', '=', self.id)
            ],
            'context': {'default_record_id': self.id}
        }

    def _auto_sync_to_netsuite(self):
        """Automatically sync invoice to NetSuite based on configuration"""
        config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)

        # Only sync if realtime mode is enabled and invoice sync is enabled
        if not config or config.config_integration_mode != 'realtime':
            return

        # Check if sync on invoice validated is enabled
        if not config.config_sync_on_invoice_validated:
            return

        api_client = self.env['netsuite.api.client']

        for invoice in self:
            # Skip if already synced or queued
            if invoice.netsuite_sync_status in ['synced', 'queued']:
                continue

            # Only sync customer invoices (out_invoice)
            if invoice.move_type != 'out_invoice':
                continue

            # Only sync posted invoices
            if invoice.state != 'posted':
                continue

            # Only sync paid/in_payment invoices (or posted for immediate sync)
            if invoice.payment_state not in ['paid', 'in_payment', 'not_paid']:
                continue

            # Check if this invoice is from a POS order
            pos_order = self.env['pos.order'].search([('account_move', '=', invoice.id)], limit=1)

            if pos_order:
                # Direct sync for POS invoices (individual, not consolidated)
                _logger.info(f'[NetSuite Invoice Realtime] Syncing POS invoice {invoice.name} directly to NetSuite')

                try:
                    # Call API client directly for individual invoice sync
                    invoice.write({'netsuite_sync_status': 'queued'})
                    self.env.cr.commit()

                    api_client.create_invoice(invoice, config)

                except Exception as e:
                    _logger.error(f'[NetSuite Invoice Realtime] Failed to sync {invoice.name}: {str(e)}')
                    invoice.write({
                        'netsuite_sync_status': 'failed',
                        'netsuite_error': str(e)
                    })
            else:
                # Queue-based sync for non-POS invoices
                _logger.info(f'[NetSuite Invoice Realtime] Queueing non-POS invoice {invoice.name} for sync')

                queue_vals = {
                    'config_id': config.id,
                    'reference': invoice.name,
                    'record_type': 'invoice',
                    'record_id': invoice.id,
                    'model': 'account.move',
                    'status': 'pending',
                    'sync_mode': 'realtime',
                    'priority': 10,
                }

                queue = self.env['netsuite.sync.queue'].create(queue_vals)
                invoice.netsuite_sync_status = 'queued'

                # Process in background (commit first to avoid blocking UI)
                self.env.cr.commit()
                queue._process_queue_items()

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger auto-sync when invoice is created from POS"""
        invoices = super(AccountMove, self).create(vals_list)

        # Check if realtime sync is enabled
        config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
        if config and config.config_integration_mode == 'realtime' and config.config_sync_on_invoice_validated:
            # Filter invoices that should be synced immediately
            invoices_to_sync = invoices.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.state == 'posted'
            )

            if invoices_to_sync:
                _logger.info(f'[NetSuite Invoice Realtime] New invoice(s) created, triggering auto-sync for {len(invoices_to_sync)} invoice(s)')
                # Delay sync slightly to ensure POS order link is established
                invoices_to_sync.with_delay()._auto_sync_to_netsuite() if hasattr(invoices_to_sync, 'with_delay') else invoices_to_sync._auto_sync_to_netsuite()

        return invoices

    def write(self, vals):
        """Override write to trigger auto-sync on state/payment_state change"""
        result = super(AccountMove, self).write(vals)

        # Check if invoice was posted or payment state changed to paid
        state_changed = 'state' in vals and vals.get('state') == 'posted'
        payment_changed = 'payment_state' in vals and vals.get('payment_state') in ['paid', 'in_payment']

        if state_changed or payment_changed:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if config and config.config_integration_mode == 'realtime' and config.config_sync_on_invoice_validated:
                # Filter only customer invoices that are posted
                invoices_to_sync = self.filtered(
                    lambda inv: inv.move_type == 'out_invoice'
                    and inv.state == 'posted'
                )

                if invoices_to_sync:
                    _logger.info(f'[NetSuite Invoice Realtime] Triggering auto-sync for {len(invoices_to_sync)} invoice(s)')
                    invoices_to_sync._auto_sync_to_netsuite()

        return result
