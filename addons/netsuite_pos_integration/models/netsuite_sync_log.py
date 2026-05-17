# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NetSuiteSyncLog(models.Model):
    """
    Sync Log for NetSuite Integration
    Audit trail of all sync operations
    """
    _name = 'netsuite.sync.log'
    _description = 'NetSuite Sync Log'
    _order = 'create_date desc'
    _rec_name = 'reference'

    config_id = fields.Many2one(
        'netsuite.config',
        string='Configuration',
        required=True,
        ondelete='cascade'
    )

    reference = fields.Char(
        string='Reference',
        required=True,
        index=True
    )

    record_type = fields.Selection([
        ('sales_order', 'Sales Order'),
        ('customer', 'Customer'),
        ('payment', 'Payment'),
        ('eod_invoice', 'End-of-Day Invoice'),
        ('product', 'Product Import'),
    ], string='Record Type', required=True, index=True)

    record_id = fields.Integer(
        string='Record ID',
        required=True
    )

    model = fields.Char(string='Model')

    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
        ('processing', 'Processing'),
        ('partial', 'Partial Success'),
    ], string='Status', required=True, index=True)

    sync_mode = fields.Selection([
        ('realtime', 'Real-time'),
        ('batch', 'Batch'),
        ('manual', 'Manual'),
    ], string='Sync Mode')

    operation = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ], string='Operation', default='create')

    request_url = fields.Char(string='Request URL')

    request_method = fields.Char(string='Request Method', default='POST')

    request_payload = fields.Text(string='Request Payload')

    response_code = fields.Integer(string='Response Code')

    response_payload = fields.Text(string='Response Payload')

    error_message = fields.Text(string='Error Message')

    netsuite_id = fields.Char(
        string='NetSuite ID',
        index=True,
        help='Internal ID in NetSuite'
    )

    netsuite_tran_id = fields.Char(
        string='Transaction ID',
        help='Transaction ID in NetSuite'
    )

    execution_time_ms = fields.Integer(
        string='Execution Time (ms)',
        help='Time taken to complete the sync in milliseconds'
    )

    retry_count = fields.Integer(string='Retry Count', default=0)

    batch_id = fields.Char(string='Batch ID')

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user
    )

    notes = fields.Text(string='Notes')

    def action_view_request(self):
        """View request payload in a formatted way"""
        self.ensure_one()
        return {
            'name': 'Request Payload',
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.log',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_retry_sync(self):
        """Retry failed sync"""
        self.ensure_one()

        if self.status == 'success':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Already Synced',
                    'message': 'This record was already synced successfully',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Create a new queue item for retry
        queue_vals = {
            'config_id': self.config_id.id,
            'reference': self.reference,
            'record_type': self.record_type,
            'record_id': self.record_id,
            'model': self.model,
            'status': 'pending',
            'sync_mode': 'manual',
            'priority': 5,  # Higher priority for manual retries
        }

        queue = self.env['netsuite.sync.queue'].create(queue_vals)
        queue._process_queue_items()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Retry Initiated',
                'message': 'Sync retry has been queued',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cleanup_old_logs(self, days=30):
        """Clean up logs older than specified days"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count
