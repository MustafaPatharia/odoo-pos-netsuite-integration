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
