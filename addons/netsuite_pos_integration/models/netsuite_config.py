# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class NetSuiteConfig(models.Model):
    """
    NetSuite Integration Configuration
    ONLY stores credentials - NetSuite controls all business logic
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

    # ============================================
    # CREDENTIALS ONLY - Nothing else stored here
    # ============================================

    api_url = fields.Char(
        string='API URL',
        required=True,
        default='http://host.docker.internal:3000',
        help='NetSuite base URL'
    )

    account_id = fields.Char(
        string='Account ID',
        required=True,
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

    # ============================================
    # Configuration from NetSuite (Read-only in Odoo)
    # ============================================

    netsuite_config = fields.Text(
        string='NetSuite Configuration JSON',
        readonly=True,
        help='Raw configuration fetched from NetSuite'
    )

    last_config_fetch = fields.Datetime(
        string='Last Config Fetch',
        readonly=True
    )
    
    # ============================================
    # Computed Fields from NetSuite Config
    # ============================================
    
    config_retry_enabled = fields.Boolean(
        string='Retry Enabled',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_max_retries = fields.Integer(
        string='Max Retries',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_retry_delay = fields.Integer(
        string='Retry Delay (minutes)',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_send_email = fields.Boolean(
        string='Send Email on Failure',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_notification_email = fields.Char(
        string='Notification Email',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_batch_size = fields.Integer(
        string='Batch Size',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_hourly_sync_enabled = fields.Boolean(
        string='Hourly Sync Enabled',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_end_of_day_sync_enabled = fields.Boolean(
        string='End of Day Sync Enabled',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_end_of_day_sync_time = fields.Char(
        string='End of Day Sync Time',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_debug_logging = fields.Boolean(
        string='Debug Logging',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_log_retention_days = fields.Integer(
        string='Log Retention (days)',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_sync_on_invoice_confirm = fields.Boolean(
        string='Sync on Invoice Confirm',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_connection_timeout = fields.Integer(
        string='Connection Timeout (seconds)',
        compute='_compute_netsuite_config_fields',
        store=False
    )
    
    config_request_timeout = fields.Integer(
        string='Request Timeout (seconds)',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # ============================================
    # Methods
    # ============================================
    
    @api.depends('netsuite_config')
    def _compute_netsuite_config_fields(self):
        """Parse NetSuite config JSON and populate computed fields"""
        for record in self:
            if not record.netsuite_config:
                record.config_retry_enabled = False
                record.config_max_retries = 0
                record.config_retry_delay = 0
                record.config_send_email = False
                record.config_notification_email = ''
                record.config_batch_size = 0
                record.config_hourly_sync_enabled = False
                record.config_end_of_day_sync_enabled = False
                record.config_end_of_day_sync_time = ''
                record.config_debug_logging = False
                record.config_log_retention_days = 0
                record.config_sync_on_invoice_confirm = False
                record.config_connection_timeout = 0
                record.config_request_timeout = 0
                continue
                
            try:
                config_json = json.loads(record.netsuite_config)
                config = config_json.get('configuration', {})
                
                record.config_retry_enabled = config.get('retry_enabled', False)
                record.config_max_retries = config.get('max_retries', 0)
                record.config_retry_delay = config.get('retry_delay_minutes', 0)
                record.config_send_email = config.get('send_email_on_failure', False)
                record.config_notification_email = config.get('notification_email', '')
                record.config_batch_size = config.get('batch_size', 0)
                record.config_hourly_sync_enabled = config.get('hourly_sync_enabled', False)
                record.config_end_of_day_sync_enabled = config.get('end_of_day_sync_enabled', False)
                record.config_end_of_day_sync_time = config.get('end_of_day_sync_time', '')
                record.config_debug_logging = config.get('enable_debug_logging', False)
                record.config_log_retention_days = config.get('log_retention_days', 0)
                record.config_sync_on_invoice_confirm = config.get('sync_on_invoice_confirm', False)
                record.config_connection_timeout = config.get('connection_timeout', 0)
                record.config_request_timeout = config.get('request_timeout', 0)
            except:
                record.config_retry_enabled = False
                record.config_max_retries = 0
                record.config_retry_delay = 0
                record.config_send_email = False
                record.config_notification_email = ''
                record.config_batch_size = 0
                record.config_hourly_sync_enabled = False
                record.config_end_of_day_sync_enabled = False
                record.config_end_of_day_sync_time = ''
                record.config_debug_logging = False
                record.config_log_retention_days = 0
                record.config_sync_on_invoice_confirm = False
                record.config_connection_timeout = 0
                record.config_request_timeout = 0

    def action_fetch_config(self):
        """Fetch configuration from NetSuite"""
        self.ensure_one()
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'OAuth realm="{self.account_id}"'
            }

            url = f"{self.api_url.rstrip('/')}/app/site/hosting/restlet.nl?action=getConfig"

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            config_data = response.json()

            self.write({
                'netsuite_config': json.dumps(config_data, indent=2),
                'last_config_fetch': fields.Datetime.now()
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Configuration Fetched',
                    'message': 'Successfully fetched configuration from NetSuite',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f'Error fetching config from NetSuite: {str(e)}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Fetch Failed',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_test_connection(self):
        """Test NetSuite API connection"""
        self.ensure_one()
        try:
            url = f"{self.api_url.rstrip('/')}/health"
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': 'Successfully connected to NetSuite',
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

    @api.model
    def get_active_config(self):
        """Get the active configuration"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValidationError('No active NetSuite configuration found. Please configure NetSuite integration.')
        return config

    def get_netsuite_config_value(self, key, default=None):
        """Get a configuration value from NetSuite config JSON"""
        self.ensure_one()
        if not self.netsuite_config:
            return default
        try:
            config = json.loads(self.netsuite_config)
            return config.get(key, default)
        except:
            return default

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

