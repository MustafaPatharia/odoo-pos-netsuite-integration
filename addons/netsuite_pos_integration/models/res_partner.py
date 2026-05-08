# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    """
    Extension of Partner/Customer for NetSuite integration
    """
    _inherit = 'res.partner'

    netsuite_id = fields.Char(
        string='NetSuite Customer ID',
        copy=False,
        help='Internal customer ID in NetSuite'
    )

    netsuite_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        copy=False
    )

    netsuite_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ], string='NetSuite Status', default='not_synced', copy=False)
