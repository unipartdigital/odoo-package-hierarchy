# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class QuantPackage(models.Model):
    """ Add the ability for a package to contain another package """
    _inherit = "stock.quant.package"

    _parent_name = "package_id"
    _parent_order = 'name'
    _order = 'id'

    display_name = fields.Char('Display Name', compute='_compute_display_name')
    package_id = fields.Many2one(
        'stock.quant.package', 'Parent Package',
        ondelete='restrict', readonly=True,
        help="The package containing this item")
    parent_ids = fields.One2many('stock.quant.package', string='Parent Packages', compute='_compute_parent_ids')
    children_quant_ids = fields.One2many('stock.quant', string='All content', compute='_compute_children_quant_ids')
    children_ids = fields.One2many('stock.quant.package', 'package_id', 'Contained Packages', readonly=True)

    def _check_not_multi_location(self):
        for package in self:
            locations = package.children_quant_ids.mapped('location_id')
            if len(locations) > 1:
                raise ValidationError(_('Package cannot be in multiple '
                                        'locations:\n%s\n%s') % (package.name,
                                                                 ', '.join( [l.name for l in locations])))

    @api.depends('package_id', 'children_ids')
    def _compute_parent_ids(self):
        for package in self.filtered(lambda p: not isinstance(p.id, models.NewId)):
            package._check_not_multi_location()
            package.ancestor_ids = self.env['stock.quant.package'].search([('id', 'parent_of', package.id)]).ids

    @api.depends('package_id', 'children_ids', 'quant_ids.package_id')
    def _compute_children_quant_ids(self):
        for package in self.filtered(lambda p: not isinstance(p.id, models.NewId)):
            package._check_not_multi_location()
            package.children_quant_ids = self.env['stock.quant'].search([('package_id', 'child_of', package.id)])

    @api.depends('quant_ids.package_id', 'quant_ids.location_id', 'quant_ids.company_id', 'quant_ids.owner_id')
    def _compute_package_info(self):
        for package in self:
            values = {'location_id': False, 'company_id': self.env.user.company_id.id, 'owner_id': False}
            package._check_not_multi_location()
            values['location_id'] = package.children_quant_ids.mapped('location_id')
            package.location_id = values['location_id']
            package.company_id = values['company_id']
            package.owner_id = values['owner_id']

    @api.depends('package_id')
    def _compute_display_name(self):
        """Compute the display name for a package. Include name of immediate parent."""
        for package in self:
            package.display_name = '%s/%s' % (package.package_id.name, package.name) if package.package_id else package.name

    def _compute_current_picking_info(self):
        # don't break _compute_package_info by having multiple records in self.
        for pack in self:
            super(QuantPackage, pack)._compute_current_picking_info()
