# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class NetSuiteConfig(models.Model):
    """
    NetSuite Integration Configuration
    Manages connection settings, sync modes, and operational parameters
    """
    _name = 'netsuite.config'
    _description = 'NetSuite Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='NetSuite Integration',
        help='Friendly name for this configuration'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Enable or disable this configuration'
    )

    # Connection Settings
    api_url = fields.Char(
        string='API URL',
        required=True,
        default='http://mock-netsuite:3000/api',
        help='NetSuite RESTlet endpoint URL'
    )

    account_id = fields.Char(
        string='Account ID',
        help='NetSuite Account ID'
    )

    consumer_key = fields.Char(
        string='Consumer Key',
        help='OAuth Consumer Key'
    )

    consumer_secret = fields.Char(
        string='Consumer Secret',
        help='OAuth Consumer Secret'
    )

    token_id = fields.Char(
        string='Token ID',
        help='OAuth Token ID'
    )

    token_secret = fields.Char(
        string='Token Secret',
        help='OAuth Token Secret'
    )

    # Sync Mode Configuration
    sync_mode = fields.Selection([
        ('realtime', 'Real-time Sync'),
        ('batch', 'Daily Batch Sync'),
    ], string='Sync Mode', required=True, default='realtime',
       help='Choose how orders are synced to NetSuite')

    enable_manual_sync = fields.Boolean(
        string='Enable Manual Sync',
        default=True,
        help='Allow manual sync via UI buttons'
    )

    enable_auto_sync = fields.Boolean(
        string='Enable Auto Sync',
        default=True,
        help='Automatically sync based on configured triggers'
    )

    # Batch Configuration
    batch_size = fields.Integer(
        string='Batch Size',
        default=50,
        help='Number of records to process in each batch'
    )

    batch_schedule_time = fields.Char(
        string='Batch Schedule Time',
        default='02:00',
        help='Time to run daily batch sync (HH:MM format)'
    )

    # Retry Configuration
    enable_retry = fields.Boolean(
        string='Enable Retry',
        default=True,
        help='Automatically retry failed syncs'
    )

    max_retry_attempts = fields.Integer(
        string='Max Retry Attempts',
        default=3,
        help='Maximum number of retry attempts'
    )

    retry_delay_minutes = fields.Integer(
        string='Retry Delay (Minutes)',
        default=5,
        help='Delay between retry attempts in minutes'
    )

    # Timeout Settings
    connection_timeout = fields.Integer(
        string='Connection Timeout (seconds)',
        default=30,
        help='API connection timeout in seconds'
    )

    request_timeout = fields.Integer(
        string='Request Timeout (seconds)',
        default=60,
        help='API request timeout in seconds'
    )

    # Logging & Debug
    enable_debug_logging = fields.Boolean(
        string='Enable Debug Logging',
        default=False,
        help='Log detailed debug information'
    )

    log_payload = fields.Boolean(
        string='Log Request/Response Payload',
        default=True,
        help='Store full API request and response data'
    )

    # Sync Triggers
    sync_on_order_confirm = fields.Boolean(
        string='Sync on Order Confirmation',
        default=True,
        help='Trigger sync when POS order is confirmed'
    )

    sync_on_payment = fields.Boolean(
        string='Sync on Payment',
        default=False,
        help='Trigger sync when payment is completed'
    )

    # Statistics
    total_synced = fields.Integer(
        string='Total Synced',
        compute='_compute_sync_stats',
        store=False
    )

    total_failed = fields.Integer(
        string='Total Failed',
        compute='_compute_sync_stats',
        store=False
    )

    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True
    )

    @api.constrains('batch_size')
    def _check_batch_size(self):
        for record in self:
            if record.batch_size < 1 or record.batch_size > 1000:
                raise ValidationError('Batch size must be between 1 and 1000')

    @api.constrains('max_retry_attempts')
    def _check_retry_attempts(self):
        for record in self:
            if record.max_retry_attempts < 0 or record.max_retry_attempts > 10:
                raise ValidationError('Max retry attempts must be between 0 and 10')

    def _compute_sync_stats(self):
        for record in self:
            SyncLog = self.env['netsuite.sync.log']
            record.total_synced = SyncLog.search_count([
                ('config_id', '=', record.id),
                ('status', '=', 'success')
            ])
            record.total_failed = SyncLog.search_count([
                ('config_id', '=', record.id),
                ('status', '=', 'failed')
            ])

    def action_test_connection(self):
        """Test NetSuite API connection"""
        self.ensure_one()
        try:
            import requests
            response = requests.get(
                f"{self.api_url.rstrip('/api')}/health",
                timeout=self.connection_timeout
            )
            response.raise_for_status()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': 'Successfully connected to NetSuite API',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_sync_logs(self):
        """Open sync logs for this configuration"""
        self.ensure_one()
        return {
            'name': 'Sync Logs',
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.log',
            'view_mode': 'tree,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id}
        }

    def action_view_sync_queue(self):
        """Open sync queue for this configuration"""
        self.ensure_one()
        return {
            'name': 'Sync Queue',
            'type': 'ir.actions.act_window',
            'res_model': 'netsuite.sync.queue',
            'view_mode': 'tree,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id}
        }

    @api.model
    def get_active_config(self):
        """Get active NetSuite configuration"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValidationError('No active NetSuite configuration found. Please configure NetSuite integration first.')
        return config
