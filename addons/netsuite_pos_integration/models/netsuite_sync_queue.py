# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class NetSuiteSyncQueue(models.Model):
    """
    Sync Queue for NetSuite Integration
    Manages queued records waiting to be synced
    """
    _name = 'netsuite.sync.queue'
    _description = 'NetSuite Sync Queue'
    _order = 'priority desc, create_date asc'
    _rec_name = 'reference'

    config_id = fields.Many2one(
        'netsuite.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env['netsuite.config'].get_active_config()
    )

    reference = fields.Char(
        string='Reference',
        required=True,
        help='Reference to the source record (e.g., POS Order number)'
    )

    record_type = fields.Selection([
        ('sales_order', 'Sales Order'),
        ('customer', 'Customer'),
        ('payment', 'Payment'),
    ], string='Record Type', required=True)

    record_id = fields.Integer(
        string='Record ID',
        required=True,
        help='ID of the source Odoo record'
    )

    model = fields.Char(
        string='Model',
        required=True,
        help='Odoo model name'
    )

    status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retry', 'Retry Queue'),
    ], string='Status', default='pending', required=True)

    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Lower number = higher priority'
    )

    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        default=fields.Datetime.now,
        help='When this record should be processed'
    )

    processed_date = fields.Datetime(
        string='Processed Date',
        readonly=True
    )

    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        readonly=True
    )

    last_error = fields.Text(
        string='Last Error',
        readonly=True
    )

    request_payload = fields.Text(
        string='Request Payload',
        help='JSON payload sent to NetSuite'
    )

    response_payload = fields.Text(
        string='Response Payload',
        readonly=True,
        help='JSON response from NetSuite'
    )

    netsuite_id = fields.Char(
        string='NetSuite Internal ID',
        readonly=True,
        help='Internal ID returned by NetSuite'
    )

    netsuite_tran_id = fields.Char(
        string='NetSuite Transaction ID',
        readonly=True,
        help='Transaction ID in NetSuite'
    )

    batch_id = fields.Char(
        string='Batch ID',
        help='Group related records in the same batch'
    )

    sync_mode = fields.Selection([
        ('realtime', 'Real-time'),
        ('batch', 'Batch'),
        ('manual', 'Manual'),
    ], string='Sync Mode', default='realtime')

    notes = fields.Text(string='Notes')

    def action_process_now(self):
        """Manually trigger processing of queue items"""
        for record in self:
            if record.status in ['processing']:
                raise UserError(_('This record is already being processed'))

            record.status = 'pending'
            record.retry_count = 0
            record.last_error = False

        # Process records
        self._process_queue_items()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Processing Started'),
                'message': _('Queue items are being processed'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_reset_to_pending(self):
        """Reset failed items back to pending"""
        for record in self:
            record.write({
                'status': 'pending',
                'retry_count': 0,
                'last_error': False,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reset Successful'),
                'message': _('%d record(s) reset to pending') % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_sync_log(self):
        """View related sync logs"""
        self.ensure_one()
        return {
            'name': _('Sync Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.log',
            'view_mode': 'tree,form',
            'domain': [
                ('reference', '=', self.reference),
                ('record_type', '=', self.record_type)
            ],
        }

    def _process_queue_items(self):
        """Process pending queue items"""
        NetSuiteAPI = self.env['netsuite.api.client']

        for queue_item in self:
            try:
                queue_item.status = 'processing'
                self.env.cr.commit()  # Commit status change

                # Get the source record
                source_record = self.env[queue_item.model].browse(queue_item.record_id)
                if not source_record.exists():
                    queue_item.write({
                        'status': 'failed',
                        'last_error': 'Source record not found',
                        'processed_date': fields.Datetime.now()
                    })
                    continue

                # Process based on record type
                if queue_item.record_type == 'sales_order':
                    result = NetSuiteAPI.create_sales_order(source_record, queue_item.config_id)
                elif queue_item.record_type == 'customer':
                    result = NetSuiteAPI.create_customer(source_record, queue_item.config_id)
                elif queue_item.record_type == 'payment':
                    result = NetSuiteAPI.create_payment(source_record, queue_item.config_id)
                else:
                    raise UserError(_('Unknown record type: %s') % queue_item.record_type)

                # Update queue item with success
                queue_item.write({
                    'status': 'success',
                    'processed_date': fields.Datetime.now(),
                    'response_payload': str(result),
                    'netsuite_id': result.get('id'),
                    'netsuite_tran_id': result.get('tranId'),
                    'last_error': False,
                })

            except Exception as e:
                _logger.error(f'Error processing queue item {queue_item.id}: {str(e)}', exc_info=True)

                # Handle retry logic
                config = queue_item.config_id
                if config.enable_retry and queue_item.retry_count < config.max_retry_attempts:
                    next_retry = fields.Datetime.now()
                    queue_item.write({
                        'status': 'retry',
                        'retry_count': queue_item.retry_count + 1,
                        'last_error': str(e),
                        'scheduled_date': next_retry,
                    })
                else:
                    queue_item.write({
                        'status': 'failed',
                        'last_error': str(e),
                        'processed_date': fields.Datetime.now()
                    })

            self.env.cr.commit()  # Commit after each item

    @api.model
    def cron_process_batch_queue(self):
        """Cron job to process batch queue"""
        _logger.info('Starting batch queue processing')

        config = self.env['netsuite.config'].get_active_config()
        if not config.active or config.sync_mode != 'batch':
            _logger.info('Batch sync is not enabled')
            return

        # Get pending items
        pending_items = self.search([
            ('status', 'in', ['pending', 'retry']),
            ('scheduled_date', '<=', fields.Datetime.now()),
            ('config_id', '=', config.id)
        ], limit=config.batch_size, order='priority desc, create_date asc')

        if pending_items:
            _logger.info(f'Processing {len(pending_items)} batch items')
            pending_items._process_queue_items()
        else:
            _logger.info('No pending items to process')

    @api.model
    def cron_retry_failed_items(self):
        """Cron job to retry failed items"""
        _logger.info('Starting retry processing')

        config = self.env['netsuite.config'].get_active_config()
        if not config.enable_retry:
            return

        # Get items eligible for retry
        retry_items = self.search([
            ('status', '=', 'retry'),
            ('scheduled_date', '<=', fields.Datetime.now()),
            ('config_id', '=', config.id)
        ], limit=config.batch_size)

        if retry_items:
            _logger.info(f'Retrying {len(retry_items)} items')
            retry_items._process_queue_items()
