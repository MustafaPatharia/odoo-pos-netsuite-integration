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
    # Computed Fields from NetSuite Config (New Schema)
    # ============================================

    # Integration Mode
    config_integration_mode = fields.Selection([
        ('realtime', 'Real-Time'),
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual Only')
    ], string='Integration Mode', compute='_compute_netsuite_config_fields', store=False)

    # Retry Policy
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
        string='Initial Retry Delay (minutes)',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_use_exponential_backoff = fields.Boolean(
        string='Use Exponential Backoff',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_backoff_multiplier = fields.Integer(
        string='Backoff Multiplier',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Scheduled Settings
    config_hourly_sync_enabled = fields.Boolean(
        string='Product Hourly Sync Enabled',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_product_sync_frequency = fields.Char(
        string='Product Sync Frequency',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_order_sync_time = fields.Char(
        string='Order Sync Time',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_invoice_sync_time = fields.Char(
        string='Invoice Sync Time',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Realtime Settings
    config_sync_on_order_confirmed = fields.Boolean(
        string='Sync on Order Confirmed',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_sync_on_invoice_validated = fields.Boolean(
        string='Sync on Invoice Validated',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Manual Execution
    config_manual_execution_enabled = fields.Boolean(
        string='Manual Execution Enabled',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_allow_retry_failed = fields.Boolean(
        string='Allow Retry Failed',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Batch Processing
    config_order_batch_size = fields.Integer(
        string='Order Batch Size',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_invoice_batch_size = fields.Integer(
        string='Invoice Batch Size',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_product_batch_size = fields.Integer(
        string='Product Batch Size',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Notifications
    config_send_email_on_failure = fields.Boolean(
        string='Send Email on Failure',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_send_email_on_success = fields.Boolean(
        string='Send Email on Success',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_notification_recipients = fields.Text(
        string='Notification Recipients',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Logging
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

    config_log_request_payload = fields.Boolean(
        string='Log Request Payload',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_log_response_payload = fields.Boolean(
        string='Log Response Payload',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # API Settings
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

    config_api_rate_limit = fields.Integer(
        string='API Rate Limit (per minute)',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # Consolidation Rules
    config_consolidate_orders = fields.Boolean(
        string='Consolidate Orders Per Shop Per Day',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_consolidate_invoices = fields.Boolean(
        string='Consolidate Invoices Per Shop Per Day',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_aggregate_line_items = fields.Boolean(
        string='Aggregate Line Items',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    config_group_by_product = fields.Boolean(
        string='Group By Product',
        compute='_compute_netsuite_config_fields',
        store=False
    )

    # ============================================
    # Methods
    # ============================================

    @api.depends('netsuite_config')
    def _compute_netsuite_config_fields(self):
        """Parse NetSuite config JSON and populate computed fields (New Schema)"""
        for record in self:
            # Set defaults
            defaults = {
                'config_integration_mode': 'scheduled',
                'config_retry_enabled': False,
                'config_max_retries': 3,
                'config_retry_delay': 5,
                'config_use_exponential_backoff': True,
                'config_backoff_multiplier': 2,
                'config_hourly_sync_enabled': True,
                'config_product_sync_frequency': 'hourly',
                'config_order_sync_time': '00:00',
                'config_invoice_sync_time': '00:00',
                'config_sync_on_order_confirmed': False,
                'config_sync_on_invoice_validated': False,
                'config_manual_execution_enabled': True,
                'config_allow_retry_failed': True,
                'config_order_batch_size': 100,
                'config_invoice_batch_size': 100,
                'config_product_batch_size': 50,
                'config_send_email_on_failure': False,
                'config_send_email_on_success': False,
                'config_notification_recipients': '',
                'config_debug_logging': False,
                'config_log_retention_days': 90,
                'config_log_request_payload': True,
                'config_log_response_payload': True,
                'config_connection_timeout': 30,
                'config_request_timeout': 120,
                'config_api_rate_limit': 60,
                'config_consolidate_orders': True,
                'config_consolidate_invoices': True,
                'config_aggregate_line_items': True,
                'config_group_by_product': True,
            }

            if not record.netsuite_config:
                for key, value in defaults.items():
                    setattr(record, key, value)
                continue

            try:
                config_json = json.loads(record.netsuite_config)
                config = config_json.get('configuration', {})

                # Integration Mode
                record.config_integration_mode = config.get('integration_mode', defaults['config_integration_mode'])

                # Retry Policy
                retry_policy = config.get('retry_policy', {})
                record.config_retry_enabled = retry_policy.get('enabled', defaults['config_retry_enabled'])
                record.config_max_retries = retry_policy.get('max_retries', defaults['config_max_retries'])
                record.config_retry_delay = retry_policy.get('initial_delay_minutes', defaults['config_retry_delay'])
                record.config_use_exponential_backoff = retry_policy.get('use_exponential_backoff', defaults['config_use_exponential_backoff'])
                record.config_backoff_multiplier = retry_policy.get('backoff_multiplier', defaults['config_backoff_multiplier'])

                # Scheduled Settings
                scheduled = config.get('scheduled_settings', {})
                record.config_hourly_sync_enabled = scheduled.get('enabled', defaults['config_hourly_sync_enabled'])
                record.config_product_sync_frequency = scheduled.get('product_sync_frequency', defaults['config_product_sync_frequency'])
                record.config_order_sync_time = scheduled.get('order_sync_time', defaults['config_order_sync_time'])
                record.config_invoice_sync_time = scheduled.get('invoice_sync_time', defaults['config_invoice_sync_time'])

                # Realtime Settings
                realtime = config.get('realtime_settings', {})
                record.config_sync_on_order_confirmed = realtime.get('sync_on_order_confirmed', defaults['config_sync_on_order_confirmed'])
                record.config_sync_on_invoice_validated = realtime.get('sync_on_invoice_validated', defaults['config_sync_on_invoice_validated'])

                # Manual Execution
                manual = config.get('manual_execution', {})
                record.config_manual_execution_enabled = manual.get('enabled', defaults['config_manual_execution_enabled'])
                record.config_allow_retry_failed = manual.get('allow_retry_failed', defaults['config_allow_retry_failed'])

                # Batch Processing
                batch = config.get('batch_processing', {})
                record.config_order_batch_size = batch.get('order_batch_size', defaults['config_order_batch_size'])
                record.config_invoice_batch_size = batch.get('invoice_batch_size', defaults['config_invoice_batch_size'])
                record.config_product_batch_size = batch.get('product_batch_size', defaults['config_product_batch_size'])

                # Notifications
                notification = config.get('notification', {})
                record.config_send_email_on_failure = notification.get('send_email_on_failure', defaults['config_send_email_on_failure'])
                record.config_send_email_on_success = notification.get('send_email_on_success', defaults['config_send_email_on_success'])
                recipients = notification.get('notification_recipients', [])
                record.config_notification_recipients = ', '.join(recipients) if recipients else defaults['config_notification_recipients']

                # Logging
                logging_config = config.get('logging', {})
                record.config_debug_logging = logging_config.get('enable_debug_logging', defaults['config_debug_logging'])
                record.config_log_retention_days = logging_config.get('log_retention_days', defaults['config_log_retention_days'])
                record.config_log_request_payload = logging_config.get('log_request_payload', defaults['config_log_request_payload'])
                record.config_log_response_payload = logging_config.get('log_response_payload', defaults['config_log_response_payload'])

                # API Settings
                api_settings = config.get('api_settings', {})
                record.config_connection_timeout = api_settings.get('connection_timeout_seconds', defaults['config_connection_timeout'])
                record.config_request_timeout = api_settings.get('request_timeout_seconds', defaults['config_request_timeout'])
                record.config_api_rate_limit = api_settings.get('api_rate_limit_per_minute', defaults['config_api_rate_limit'])

                # Consolidation Rules
                consolidation = config.get('consolidation_rules', {})
                record.config_consolidate_orders = consolidation.get('consolidate_orders_per_shop_per_day', defaults['config_consolidate_orders'])
                record.config_consolidate_invoices = consolidation.get('consolidate_invoices_per_shop_per_day', defaults['config_consolidate_invoices'])
                record.config_aggregate_line_items = consolidation.get('aggregate_line_items', defaults['config_aggregate_line_items'])
                record.config_group_by_product = consolidation.get('group_by_product', defaults['config_group_by_product'])

            except Exception as e:
                _logger.error(f'Error parsing NetSuite config JSON: {str(e)}')
                # Set all to defaults on error
                for key, value in defaults.items():
                    setattr(record, key, value)

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

