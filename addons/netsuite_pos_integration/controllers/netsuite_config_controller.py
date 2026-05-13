# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class NetSuiteConfigAPI(http.Controller):
    """
    REST API Controller for NetSuite Configuration Updates
    NetSuite calls this endpoint to push configuration changes to Odoo
    """

    @http.route('/api/netsuite/config/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_config(self, **kwargs):
        """
        POST API endpoint for NetSuite to update Odoo configuration
        
        Expected payload structure:
        {
            "db": "odoo_database_name",
            "login": "api_user",
            "password": "api_key_or_password",
            "configuration": {
                "integration_mode": "realtime|scheduled|manual",
                "realtime_settings": {...},
                "scheduled_settings": {...},
                ...
            },
            "metadata": {...}
        }
        
        Returns:
        {
            "success": true/false,
            "message": "...",
            "config_id": 1,
            "applied_at": "..."
        }
        """
        try:
            # Extract authentication and payload
            payload = request.jsonrequest
            
            db_name = payload.get('db')
            login = payload.get('login')
            password = payload.get('password')
            config_data = payload.get('configuration')
            metadata = payload.get('metadata', {})
            
            # Validate required fields
            if not all([db_name, login, password, config_data]):
                return {
                    'success': False,
                    'error': {
                        'code': 'MISSING_REQUIRED_FIELDS',
                        'message': 'Missing required fields: db, login, password, or configuration'
                    }
                }
            
            # Authenticate user
            try:
                uid = request.session.authenticate(db_name, login, password)
                if not uid:
                    return {
                        'success': False,
                        'error': {
                            'code': 'AUTHENTICATION_FAILED',
                            'message': 'Invalid credentials'
                        }
                    }
            except Exception as auth_error:
                _logger.error(f'Authentication error: {str(auth_error)}')
                return {
                    'success': False,
                    'error': {
                        'code': 'AUTHENTICATION_ERROR',
                        'message': str(auth_error)
                    }
                }
            
            # Validate configuration structure
            validation_error = self._validate_config_structure(config_data)
            if validation_error:
                return {
                    'success': False,
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': validation_error
                    }
                }
            
            # Get or create NetSuite config record
            NetSuiteConfig = request.env['netsuite.config'].sudo()
            config_record = NetSuiteConfig.search([('active', '=', True)], limit=1)
            
            if not config_record:
                # Create new config if none exists
                config_record = NetSuiteConfig.create({
                    'name': 'NetSuite Integration',
                    'active': True,
                })
            
            # Prepare full config JSON with metadata
            full_config = {
                'configuration': config_data,
                'metadata': {
                    'config_version': metadata.get('config_version', '1.0'),
                    'last_updated_by': metadata.get('last_updated_by', 'NetSuite System'),
                    'last_updated_at': metadata.get('last_updated_at', http.request.env['ir.fields'].datetime.now().isoformat()),
                    'netsuite_environment': metadata.get('netsuite_environment', 'production')
                }
            }
            
            # Update configuration
            config_record.write({
                'netsuite_config': json.dumps(full_config, indent=2),
                'last_config_fetch': http.request.env['ir.fields'].datetime.now()
            })
            
            _logger.info(f'NetSuite configuration updated successfully for config ID: {config_record.id}')
            
            return {
                'success': True,
                'message': 'Configuration updated successfully',
                'config_id': config_record.id,
                'applied_at': config_record.last_config_fetch.isoformat() if config_record.last_config_fetch else None
            }
            
        except Exception as e:
            _logger.error(f'Error updating NetSuite configuration: {str(e)}', exc_info=True)
            return {
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': str(e)
                }
            }
    
    def _validate_config_structure(self, config_data):
        """
        Validate configuration JSON structure
        Returns error message if invalid, None if valid
        """
        if not isinstance(config_data, dict):
            return 'Configuration must be a JSON object'
        
        # Validate integration_mode
        integration_mode = config_data.get('integration_mode')
        if integration_mode and integration_mode not in ['realtime', 'scheduled', 'manual']:
            return f'Invalid integration_mode: {integration_mode}. Must be realtime, scheduled, or manual'
        
        # Validate retry_policy
        retry_policy = config_data.get('retry_policy', {})
        if retry_policy:
            max_retries = retry_policy.get('max_retries', 0)
            if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
                return 'retry_policy.max_retries must be between 0 and 10'
        
        # Validate notification emails
        notification = config_data.get('notification', {})
        if notification:
            recipients = notification.get('notification_recipients', [])
            if recipients and not isinstance(recipients, list):
                return 'notification.notification_recipients must be an array'
        
        # Validate logging
        logging_config = config_data.get('logging', {})
        if logging_config:
            retention_days = logging_config.get('log_retention_days', 90)
            if not isinstance(retention_days, int) or retention_days < 7 or retention_days > 365:
                return 'logging.log_retention_days must be between 7 and 365'
        
        # Validate scheduled_settings time format
        scheduled_settings = config_data.get('scheduled_settings', {})
        if scheduled_settings:
            order_sync_time = scheduled_settings.get('order_sync_time')
            if order_sync_time:
                try:
                    hour, minute = order_sync_time.split(':')
                    if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                        return f'Invalid time format in scheduled_settings.order_sync_time: {order_sync_time}'
                except:
                    return f'scheduled_settings.order_sync_time must be in HH:MM format'
        
        return None
    
    @http.route('/api/netsuite/config/status', type='json', auth='public', methods=['GET'], csrf=False)
    def get_config_status(self, **kwargs):
        """
        GET endpoint to check current configuration status
        
        Returns current config version, last update time, and active status
        """
        try:
            payload = request.jsonrequest or {}
            
            db_name = payload.get('db')
            login = payload.get('login')
            password = payload.get('password')
            
            if not all([db_name, login, password]):
                return {
                    'success': False,
                    'error': {
                        'code': 'MISSING_CREDENTIALS',
                        'message': 'Missing db, login, or password'
                    }
                }
            
            # Authenticate
            try:
                uid = request.session.authenticate(db_name, login, password)
                if not uid:
                    return {'success': False, 'error': {'code': 'AUTH_FAILED', 'message': 'Invalid credentials'}}
            except Exception as e:
                return {'success': False, 'error': {'code': 'AUTH_ERROR', 'message': str(e)}}
            
            # Get config
            config = request.env['netsuite.config'].sudo().search([('active', '=', True)], limit=1)
            
            if not config:
                return {
                    'success': False,
                    'error': {
                        'code': 'NO_CONFIG_FOUND',
                        'message': 'No active configuration found'
                    }
                }
            
            config_json = json.loads(config.netsuite_config) if config.netsuite_config else {}
            metadata = config_json.get('metadata', {})
            
            return {
                'success': True,
                'config_id': config.id,
                'active': config.active,
                'last_updated': config.last_config_fetch.isoformat() if config.last_config_fetch else None,
                'metadata': metadata,
                'has_configuration': bool(config.netsuite_config)
            }
            
        except Exception as e:
            _logger.error(f'Error getting config status: {str(e)}')
            return {
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': str(e)
                }
            }
