# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class NetSuiteSubsidiaryMapping(models.Model):
    """
    Maps Odoo Warehouses/Shops to NetSuite Subsidiaries
    Required for NetSuite OneWorld implementations
    """
    _name = 'netsuite.subsidiary.mapping'
    _description = 'NetSuite Subsidiary Mapping'
    _rec_name = 'warehouse_id'

    config_id = fields.Many2one(
        'netsuite.config',
        string='Configuration',
        required=True,
        default=lambda self: self.env['netsuite.config'].search([('active', '=', True)], limit=1),
        ondelete='cascade'
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Odoo Warehouse/Shop',
        required=True,
        help='Odoo warehouse that represents a shop/location'
    )

    warehouse_name = fields.Char(
        related='warehouse_id.name',
        string='Warehouse Name',
        readonly=True,
        store=True
    )

    warehouse_code = fields.Char(
        related='warehouse_id.code',
        string='Warehouse Code',
        readonly=True,
        store=True
    )

    # Only store IDs (not names) - names fetched in real-time from NetSuite
    netsuite_subsidiary_id = fields.Selection(
        selection='_get_netsuite_subsidiaries',
        string='NetSuite Subsidiary',
        required=True,
        help='Select NetSuite subsidiary from live data'
    )

    netsuite_department_id = fields.Selection(
        selection='_get_netsuite_departments',
        string='NetSuite Department',
        help='Optional department for additional classification'
    )

    netsuite_location_id = fields.Selection(
        selection='_get_netsuite_locations',
        string='NetSuite Location',
        help='Optional location for warehouse mapping'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    notes = fields.Text(
        string='Notes'
    )

    _sql_constraints = [
        ('warehouse_unique', 'unique(config_id, warehouse_id)',
         'Each warehouse can only be mapped to one NetSuite subsidiary!'),
    ]

    @api.model
    def _get_netsuite_subsidiaries(self):
        """Fetch subsidiaries from NetSuite REST API"""
        try:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if not config:
                return []

            api_client = self.env['netsuite.api.client']
            success, data, error, status_code, exec_time = api_client._make_request(
                config,
                '/services/rest/record/v1/subsidiary',
                method='GET'
            )

            if success and data and 'items' in data:
                return [(str(item['id']), item['name']) for item in data['items']]
            else:
                _logger.warning(f'Failed to fetch subsidiaries: {error}')
                return []
        except Exception as e:
            _logger.error(f'Error fetching subsidiaries: {str(e)}')
            return []

    @api.model
    def _get_netsuite_departments(self):
        """Fetch departments from NetSuite REST API"""
        try:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if not config:
                return []

            api_client = self.env['netsuite.api.client']
            success, data, error, status_code, exec_time = api_client._make_request(
                config,
                '/services/rest/record/v1/department',
                method='GET'
            )

            if success and data and 'items' in data:
                return [(str(item['id']), item['name']) for item in data['items']]
            else:
                _logger.warning(f'Failed to fetch departments: {error}')
                return []
        except Exception as e:
            _logger.error(f'Error fetching departments: {str(e)}')
            return []

    @api.model
    def _get_netsuite_locations(self):
        """Fetch locations from NetSuite REST API"""
        try:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if not config:
                return []

            api_client = self.env['netsuite.api.client']
            success, data, error, status_code, exec_time = api_client._make_request(
                config,
                '/services/rest/record/v1/location',
                method='GET'
            )

            if success and data and 'items' in data:
                return [(str(item['id']), item['name']) for item in data['items']]
            else:
                _logger.warning(f'Failed to fetch locations: {error}')
                return []
        except Exception as e:
            _logger.error(f'Error fetching locations: {str(e)}')
            return []

    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            # Get the name from the selection field
            subsidiary_name = dict(self._get_netsuite_subsidiaries()).get(record.netsuite_subsidiary_id, record.netsuite_subsidiary_id)
            name = f"{record.warehouse_id.name} → {subsidiary_name}"
            result.append((record.id, name))
        return result

    @api.model
    def get_subsidiary_for_warehouse(self, warehouse_id):
        """
        Get NetSuite subsidiary ID for a given warehouse

        Args:
            warehouse_id: Odoo warehouse ID (int or recordset)

        Returns:
            dict: {'subsidiary_id': '123', 'department_id': '456', 'location_id': '789'}
            or None if no mapping found
        """
        if isinstance(warehouse_id, models.BaseModel):
            warehouse_id = warehouse_id.id

        mapping = self.search([
            ('warehouse_id', '=', warehouse_id),
            ('active', '=', True)
        ], limit=1)

        if not mapping:
            _logger.warning(f'No NetSuite subsidiary mapping found for warehouse ID {warehouse_id}')
            return None

        return {
            'subsidiary_id': mapping.netsuite_subsidiary_id,
            'department_id': mapping.netsuite_department_id,
            'location_id': mapping.netsuite_location_id,
        }


class NetSuitePaymentMethodMapping(models.Model):
    """
    Maps Odoo Payment Methods to NetSuite Payment Methods
    Fetched from NetSuite as master data
    """
    _name = 'netsuite.payment.method.mapping'
    _description = 'NetSuite Payment Method Mapping'
    _rec_name = 'odoo_payment_method_id'

    config_id = fields.Many2one(
        'netsuite.config',
        string='Configuration',
        required=True,
        default=lambda self: self.env['netsuite.config'].search([('active', '=', True)], limit=1),
        ondelete='cascade'
    )

    odoo_payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Odoo Payment Method',
        required=True
    )

    odoo_payment_method_name = fields.Char(
        related='odoo_payment_method_id.name',
        string='Payment Method Name',
        readonly=True,
        store=True
    )

    # Only store ID - name shown directly in Selection widget
    netsuite_payment_method_id = fields.Selection(
        selection='_get_netsuite_payment_methods',
        string='NetSuite Payment Method',
        required=True,
        help='Select NetSuite payment method from live data'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    last_synced = fields.Datetime(
        string='Last Synced',
        readonly=True
    )

    _sql_constraints = [
        ('payment_method_unique', 'unique(config_id, odoo_payment_method_id)',
         'Each payment method can only be mapped once!'),
    ]

    @api.model
    def _get_netsuite_payment_methods(self):
        """Fetch payment methods from NetSuite REST API"""
        try:
            config = self.env['netsuite.config'].search([('active', '=', True)], limit=1)
            if not config:
                return []

            api_client = self.env['netsuite.api.client']
            success, data, error, status_code, exec_time = api_client._make_request(
                config,
                '/services/rest/record/v1/paymentmethod',
                method='GET'
            )

            if success and data and 'items' in data:
                return [(str(item['id']), item['name']) for item in data['items']]
            else:
                _logger.warning(f'Failed to fetch payment methods: {error}')
                return []
        except Exception as e:
            _logger.error(f'Error fetching payment methods: {str(e)}')
            return []

    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            # Get the name from the selection field
            payment_method_name = dict(self._get_netsuite_payment_methods()).get(record.netsuite_payment_method_id, record.netsuite_payment_method_id)
            name = f"{record.odoo_payment_method_id.name} → {payment_method_name}"
            result.append((record.id, name))
        return result

    @api.model
    def get_netsuite_payment_method(self, odoo_payment_method_id):
        """
        Get NetSuite payment method ID for an Odoo payment method

        Args:
            odoo_payment_method_id: Odoo payment method ID (int or recordset)

        Returns:
            str: NetSuite payment method ID or None
        """
        if isinstance(odoo_payment_method_id, models.BaseModel):
            odoo_payment_method_id = odoo_payment_method_id.id

        mapping = self.search([
            ('odoo_payment_method_id', '=', odoo_payment_method_id),
            ('active', '=', True)
        ], limit=1)

        if not mapping:
            _logger.warning(f'No NetSuite payment method mapping found for payment method ID {odoo_payment_method_id}')
            return None

        return mapping.netsuite_payment_method_id
