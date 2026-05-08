# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import UserError
import requests
import json
import time
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class NetSuiteAPIClient(models.AbstractModel):
    """
    NetSuite API Client Service
    Handles all communication with NetSuite RESTlet endpoints
    """
    _name = 'netsuite.api.client'
    _description = 'NetSuite API Client'

    @api.model
    def _get_headers(self, config):
        """Generate request headers"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Add OAuth headers if credentials are configured
        if config.consumer_key:
            # In production, implement proper OAuth 1.0 signing
            # For mock server, we don't need authentication
            headers['Authorization'] = f'OAuth realm="{config.account_id}"'

        return headers

    @api.model
    def _make_request(self, config, endpoint, method='POST', data=None):
        """
        Make HTTP request to NetSuite
        Returns: (success, response_data, error_message, status_code, execution_time)
        """
        start_time = time.time()

        url = f"{config.api_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._get_headers(config)

        try:
            if method == 'POST':
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=(config.connection_timeout, config.request_timeout)
                )
            elif method == 'PUT':
                response = requests.put(
                    url,
                    headers=headers,
                    json=data,
                    timeout=(config.connection_timeout, config.request_timeout)
                )
            elif method == 'GET':
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=(config.connection_timeout, config.request_timeout)
                )
            else:
                raise UserError(_('Unsupported HTTP method: %s') % method)

            execution_time = int((time.time() - start_time) * 1000)  # milliseconds

            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {'raw': response.text}

            # Check if request was successful
            if response.status_code in [200, 201]:
                if isinstance(response_data, dict) and response_data.get('success') is False:
                    # NetSuite returned success=false
                    error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                    return False, response_data, error_msg, response.status_code, execution_time

                return True, response_data, None, response.status_code, execution_time
            else:
                error_msg = response_data.get('error', {}).get('message', response.text)
                return False, response_data, error_msg, response.status_code, execution_time

        except requests.exceptions.Timeout:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = 'Request timeout'
            return False, {}, error_msg, 0, execution_time

        except requests.exceptions.ConnectionError:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = 'Connection error - unable to reach NetSuite server'
            return False, {}, error_msg, 0, execution_time

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            _logger.error(f'NetSuite API Error: {error_msg}', exc_info=True)
            return False, {}, error_msg, 0, execution_time

    @api.model
    def _log_sync(self, config, reference, record_type, record_id, model,
                  status, operation, request_url, method, request_data,
                  response_data, error_msg, status_code, execution_time,
                  netsuite_id=None, netsuite_tran_id=None, sync_mode='realtime'):
        """Create sync log entry"""
        log_vals = {
            'config_id': config.id,
            'reference': reference,
            'record_type': record_type,
            'record_id': record_id,
            'model': model,
            'status': status,
            'operation': operation,
            'request_url': request_url,
            'request_method': method,
            'response_code': status_code,
            'execution_time_ms': execution_time,
            'sync_mode': sync_mode,
            'netsuite_id': netsuite_id,
            'netsuite_tran_id': netsuite_tran_id,
        }

        if config.log_payload:
            log_vals['request_payload'] = json.dumps(request_data, indent=2) if request_data else ''
            log_vals['response_payload'] = json.dumps(response_data, indent=2) if response_data else ''

        if error_msg:
            log_vals['error_message'] = error_msg

        return self.env['netsuite.sync.log'].create(log_vals)

    @api.model
    def create_sales_order(self, pos_order, config):
        """
        Create Sales Order in NetSuite from POS Order
        """
        # Prepare payload
        order_data = {
            'entity': pos_order.partner_id.netsuite_id or '1',  # Default customer if not mapped
            'tranDate': pos_order.date_order.strftime('%Y-%m-%d'),
            'currency': pos_order.currency_id.name or 'USD',
            'memo': f'Odoo POS Order: {pos_order.name}',
            'externalId': f'ODOO-POS-{pos_order.id}',
            'items': [],
        }

        # Add line items
        total_amount = 0
        for line in pos_order.lines:
            line_data = {
                'item': line.product_id.default_code or line.product_id.name,
                'quantity': line.qty,
                'rate': line.price_unit,
                'amount': line.price_subtotal,
                'description': line.product_id.name,
            }
            order_data['items'].append(line_data)
            total_amount += line.price_subtotal

        order_data['total'] = total_amount

        # Make API request
        success, response_data, error_msg, status_code, execution_time = self._make_request(
            config, 'salesorder', 'POST', order_data
        )

        # Log the sync
        log_status = 'success' if success else 'failed'
        netsuite_id = response_data.get('id') if success else None
        netsuite_tran_id = response_data.get('tranId') if success else None

        self._log_sync(
            config, pos_order.name, 'sales_order', pos_order.id, 'pos.order',
            log_status, 'create', f"{config.api_url}/salesorder", 'POST',
            order_data, response_data, error_msg, status_code, execution_time,
            netsuite_id, netsuite_tran_id
        )

        # Update POS order
        if success:
            pos_order.write({
                'netsuite_sync_status': 'synced',
                'netsuite_id': netsuite_id,
                'netsuite_tran_id': netsuite_tran_id,
                'netsuite_sync_date': datetime.now(),
                'netsuite_error': False,
            })
        else:
            pos_order.write({
                'netsuite_sync_status': 'failed',
                'netsuite_error': error_msg,
            })
            raise UserError(_('NetSuite Sync Failed: %s') % error_msg)

        return response_data

    @api.model
    def create_customer(self, partner, config):
        """
        Create Customer in NetSuite from Partner
        """
        customer_data = {
            'companyName': partner.name,
            'email': partner.email or '',
            'phone': partner.phone or '',
            'externalId': f'ODOO-CUST-{partner.id}',
        }

        if partner.street:
            customer_data['address'] = {
                'addr1': partner.street,
                'addr2': partner.street2 or '',
                'city': partner.city or '',
                'state': partner.state_id.code if partner.state_id else '',
                'zip': partner.zip or '',
                'country': partner.country_id.code if partner.country_id else '',
            }

        # Make API request
        success, response_data, error_msg, status_code, execution_time = self._make_request(
            config, 'customer', 'POST', customer_data
        )

        # Log the sync
        log_status = 'success' if success else 'failed'
        netsuite_id = response_data.get('id') if success else None

        self._log_sync(
            config, partner.name, 'customer', partner.id, 'res.partner',
            log_status, 'create', f"{config.api_url}/customer", 'POST',
            customer_data, response_data, error_msg, status_code, execution_time,
            netsuite_id
        )

        # Update partner
        if success:
            partner.write({
                'netsuite_id': netsuite_id,
                'netsuite_sync_date': datetime.now(),
                'netsuite_sync_status': 'synced',
            })
        else:
            partner.write({
                'netsuite_sync_status': 'failed',
            })
            raise UserError(_('NetSuite Sync Failed: %s') % error_msg)

        return response_data

    @api.model
    def create_payment(self, payment, config):
        """
        Create Payment in NetSuite
        """
        payment_data = {
            'customer': payment.partner_id.netsuite_id if payment.partner_id else '1',
            'payment': payment.amount,
            'tranDate': payment.payment_date.strftime('%Y-%m-%d') if hasattr(payment, 'payment_date') else datetime.now().strftime('%Y-%m-%d'),
            'externalId': f'ODOO-PMT-{payment.id}',
        }

        # Make API request
        success, response_data, error_msg, status_code, execution_time = self._make_request(
            config, 'payment', 'POST', payment_data
        )

        # Log the sync
        log_status = 'success' if success else 'failed'
        netsuite_id = response_data.get('id') if success else None

        self._log_sync(
            config, f'Payment-{payment.id}', 'payment', payment.id, payment._name,
            log_status, 'create', f"{config.api_url}/payment", 'POST',
            payment_data, response_data, error_msg, status_code, execution_time,
            netsuite_id
        )

        if not success:
            raise UserError(_('NetSuite Sync Failed: %s') % error_msg)

        return response_data

    @api.model
    def batch_create_orders(self, pos_orders, config):
        """
        Create multiple sales orders in a single batch request
        """
        operations = []
        for order in pos_orders:
            order_data = {
                'entity': order.partner_id.netsuite_id or '1',
                'tranDate': order.date_order.strftime('%Y-%m-%d'),
                'externalId': f'ODOO-POS-{order.id}',
                'items': [
                    {
                        'item': line.product_id.default_code or line.product_id.name,
                        'quantity': line.qty,
                        'rate': line.price_unit,
                    } for line in order.lines
                ]
            }
            operations.append({
                'type': 'salesorder',
                'data': order_data
            })

        batch_data = {'operations': operations}

        # Make batch API request
        success, response_data, error_msg, status_code, execution_time = self._make_request(
            config, 'batch', 'POST', batch_data
        )

        # Process results
        if success and response_data.get('results'):
            results = response_data['results']
            for idx, result in enumerate(results):
                if idx < len(pos_orders):
                    order = pos_orders[idx]
                    if result.get('success'):
                        order.write({
                            'netsuite_sync_status': 'synced',
                            'netsuite_id': result.get('id'),
                            'netsuite_sync_date': datetime.now(),
                        })
                    else:
                        order.write({
                            'netsuite_sync_status': 'failed',
                            'netsuite_error': result.get('error', 'Unknown error'),
                        })

        return response_data
