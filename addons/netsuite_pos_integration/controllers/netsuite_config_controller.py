# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request, Response
from functools import wraps
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def validate_api_key(func):
    """
    Decorator to validate API key from request headers
    Expects 'X-API-Key' header with a valid Odoo API key
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Get API key from headers
        api_key = request.httprequest.headers.get('X-API-Key')

        _logger.info(f'API Key Validation - Received key: {api_key[:10] if api_key else None}...')

        if not api_key:
            _logger.warning('API Key Validation - No API key provided in X-API-Key header')
            return Response(
                json.dumps({
                    'success': False,
                    'error': {
                        'code': 'MISSING_API_KEY',
                        'message': 'Missing X-API-Key header'
                    }
                }),
                content_type='application/json',
                status=401
            )

        try:
            # Validate API key by trying to authenticate with it
            # In Odoo, API keys are stored in res.users.apikeys model
            _logger.info('API Key Validation - Attempting to retrieve res.users.apikeys model')

            ApiKey = request.env['res.users.apikeys'].sudo()
            _logger.info(f'API Key Validation - ApiKey model: {ApiKey}')

            # List all available API keys in the system for debugging
            all_keys = ApiKey.search([])
            _logger.info(f'API Key Validation - Total API keys in system: {len(all_keys)}')
            for key in all_keys:
                _logger.info(f'API Key Validation - DB Key ID: {key.id}, User: {key.user_id.login}, Name: {key.name}, Key prefix: {key.key[:10] if hasattr(key, "key") else "N/A"}...')

            _logger.info(f'API Key Validation - Calling _check_credentials with scope=rpc, key={api_key[:10]}...')
            user_id = ApiKey._check_credentials(scope='rpc', key=api_key)

            _logger.info(f'API Key Validation - _check_credentials returned user_id: {user_id} (type: {type(user_id).__name__})')

            if not user_id:
                _logger.warning(f'API Key Validation - No matching key found for: {api_key[:10]}...')
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'INVALID_API_KEY',
                            'message': 'Invalid or expired API key'
                        }
                    }),
                    content_type='application/json',
                    status=401
                )

            # Set the user context for this request
            # _check_credentials returns user_id (int), not a record
            request.update_env(user=user_id)

            # Get user info for logging
            user = request.env['res.users'].sudo().browse(user_id)
            _logger.info(f'API Key Validation - SUCCESS! User ID: {user_id}, User: {user.login}')

        except Exception as e:
            _logger.error(f'API key validation error: {str(e)}', exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': {
                        'code': 'AUTHENTICATION_ERROR',
                        'message': f'Failed to validate API key: {str(e)}'
                    }
                }),
                content_type='application/json',
                status=401
            )

        return func(self, *args, **kwargs)

    return wrapper


class NetSuiteConfigAPI(http.Controller):
    """
    REST API Controller for NetSuite Configuration Updates
    NetSuite calls this endpoint to push configuration changes to Odoo
    """

    @http.route('/api/netsuite/config/update', type='http', auth='none', methods=['POST'], csrf=False)
    @validate_api_key
    def update_config(self, **kwargs):
        """
        POST API endpoint for NetSuite to update Odoo configuration

        Authentication: API Key (X-API-Key header)

        Expected Headers:
        {
            "X-API-Key": "your_odoo_api_key_here",
            "Content-Type": "application/json"
        }

        Expected payload structure:
        {
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
            # Parse JSON body
            try:
                payload = json.loads(request.httprequest.data.decode('utf-8'))
                _logger.info(f'Parsed payload type: {type(payload)}, payload: {payload}')
            except json.JSONDecodeError as e:
                _logger.error(f'JSON decode error: {str(e)}')
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'INVALID_JSON',
                            'message': f'Invalid JSON payload: {str(e)}'
                        }
                    }),
                    content_type='application/json',
                    status=400
                )

            # Ensure payload is a dict
            if not isinstance(payload, dict):
                _logger.error(f'Payload is not a dict, type: {type(payload)}')
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'INVALID_PAYLOAD',
                            'message': 'Payload must be a JSON object'
                        }
                    }),
                    content_type='application/json',
                    status=400
                )

            config_data = payload.get('configuration')

            _logger.info(f'config_data type: {type(config_data)}')

            # Validate required fields
            if not config_data:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'MISSING_REQUIRED_FIELDS',
                            'message': 'Missing required field: configuration'
                        }
                    }),
                    content_type='application/json',
                    status=400
                )

            # Validate configuration structure
            validation_error = self._validate_config_structure(config_data)
            if validation_error:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'VALIDATION_ERROR',
                            'message': validation_error
                        }
                    }),
                    content_type='application/json',
                    status=400
                )

            # Get NetSuite config record - must exist with credentials
            NetSuiteConfig = request.env['netsuite.config'].sudo()
            config_record = NetSuiteConfig.search([('active', '=', True)], limit=1)

            if not config_record:
                _logger.warning('No active NetSuite configuration found')
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'NO_CONFIG_FOUND',
                            'message': 'Please first create a NetSuite connection (with credentials) in Odoo, then update the configuration via this API'
                        }
                    }),
                    content_type='application/json',
                    status=404
                )
            
            _logger.info(f'Found existing config ID: {config_record.id}, updating configuration...')

            # Prepare config JSON (no metadata - NetSuite is source of truth)
            full_config = {
                'configuration': config_data
            }

            # Update configuration
            config_record.write({
                'netsuite_config': json.dumps(full_config, indent=2),
                'last_config_fetch': fields.Datetime.now()
            })

            _logger.info(f'NetSuite configuration updated successfully for config ID: {config_record.id}')

            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Configuration updated successfully',
                    'config_id': config_record.id,
                    'applied_at': config_record.last_config_fetch.isoformat() if config_record.last_config_fetch else None
                }),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            _logger.error(f'Error updating NetSuite configuration: {str(e)}', exc_info=True)
            return Response(
                json.dumps({
                    'success': False,
                    'error': {
                        'code': 'INTERNAL_ERROR',
                        'message': str(e)
                    }
                }),
                content_type='application/json',
                status=500
            )

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

    @http.route('/api/netsuite/config/status', type='http', auth='none', methods=['GET'], csrf=False)
    @validate_api_key
    def get_config_status(self, **kwargs):
        """
        GET endpoint to check current configuration status

        Authentication: API Key (X-API-Key header)

        Returns current config version, last update time, and active status
        """
        try:
            # Get config
            config = request.env['netsuite.config'].sudo().search([('active', '=', True)], limit=1)

            if not config:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': {
                            'code': 'NO_CONFIG_FOUND',
                            'message': 'No active configuration found'
                        }
                    }),
                    content_type='application/json',
                    status=404
                )

            # Parse config JSON (it's stored as Text field)
            try:
                config_json = json.loads(config.netsuite_config) if config.netsuite_config else {}
            except (json.JSONDecodeError, TypeError) as e:
                _logger.error(f'Error parsing netsuite_config: {str(e)}')
                config_json = {}

            metadata = config_json.get('metadata', {}) if isinstance(config_json, dict) else {}

            return Response(
                json.dumps({
                    'success': True,
                    'config_id': config.id,
                    'active': config.active,
                    'last_updated': config.last_config_fetch.isoformat() if config.last_config_fetch else None,
                    'metadata': metadata,
                    'has_configuration': bool(config.netsuite_config)
                }),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            _logger.error(f'Error getting config status: {str(e)}')
            return Response(
                json.dumps({
                    'success': False,
                    'error': {
                        'code': 'INTERNAL_ERROR',
                        'message': str(e)
                    }
                }),
                content_type='application/json',
                status=500
            )
