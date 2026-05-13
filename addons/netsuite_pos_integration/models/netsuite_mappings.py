# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

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
    
    netsuite_subsidiary_id = fields.Char(
        string='NetSuite Subsidiary ID',
        required=True,
        help='NetSuite Internal ID of the subsidiary'
    )
    
    netsuite_subsidiary_name = fields.Char(
        string='NetSuite Subsidiary Name',
        required=True,
        help='NetSuite subsidiary display name'
    )
    
    netsuite_department_id = fields.Char(
        string='NetSuite Department ID',
        help='Optional department ID for additional classification'
    )
    
    netsuite_location_id = fields.Char(
        string='NetSuite Location ID',
        help='Optional location ID for warehouse mapping'
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
    
    @api.constrains('netsuite_subsidiary_id')
    def _check_subsidiary_id(self):
        """Validate NetSuite subsidiary ID format"""
        for record in self:
            if record.netsuite_subsidiary_id:
                try:
                    int(record.netsuite_subsidiary_id)
                except ValueError:
                    raise ValidationError(_('NetSuite Subsidiary ID must be a numeric value'))
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = f"{record.warehouse_id.name} → {record.netsuite_subsidiary_name}"
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
            'subsidiary_name': mapping.netsuite_subsidiary_name,
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
    
    netsuite_payment_method_id = fields.Char(
        string='NetSuite Payment Method ID',
        required=True,
        help='NetSuite Internal ID'
    )
    
    netsuite_payment_method_name = fields.Char(
        string='NetSuite Payment Method Name',
        required=True
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
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = f"{record.odoo_payment_method_id.name} → {record.netsuite_payment_method_name}"
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
