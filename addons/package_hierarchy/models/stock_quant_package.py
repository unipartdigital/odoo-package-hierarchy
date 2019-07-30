"""Packages with inheritance."""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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

    @api.constrains('package_id')
    def _check_parent_not_multi_location(self):
        for parent_package in self.mapped('package_id'):
            parent_package._check_not_multi_location()

    @api.constrains("package_id")
    def _check_package_recursion(self):
        if not self._check_recursion("package_id"):
            raise ValidationError("A package cannot be its own parent.")

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
            package.parent_ids = self.env['stock.quant.package'].search([('id', 'parent_of', package.id)]).ids

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

    def is_all_contents_in(self, rs):
        """See if the entire contents of a package is in recordset rs.
        rs can be a recordset of quants or packages.
        """
        if rs._name == 'stock.quant':
            compare_rs = self.children_quant_ids
        elif rs._name == 'stock.quant.package':
            compare_rs = self.children_ids
        else:
            msg = "Expected stock.quant or stock.quant.package, got %s instead."
            raise ValidationError(_(msg) % rs._name)
        return all([a in rs for a in compare_rs])

    def _compute_current_picking_info(self):
        """When a whole parent is in a picking, add it."""
        super(QuantPackage, self)._compute_current_picking_info()
        Picking = self.env['stock.picking']

        picking = Picking.browse(self.env.context.get('picking_id'))

        if picking:
            picking_packages = picking.entire_package_detail_ids | picking.entire_package_ids

            # TODO: Not sure what this is doing but it fails without it...
            picking_packages.mapped('current_picking_move_line_ids')

            for package in self:
                parent_pack = package.package_id
                if parent_pack and parent_pack.is_all_contents_in(picking_packages):
                    # entire parent pack is in picking. Add parent package to pickings packages.
                    children_packs = parent_pack.children_ids

                    parent_pack.current_picking_move_line_ids = children_packs.mapped('current_picking_move_line_ids')
                    parent_pack.current_picking_id = True
                    parent_pack.current_source_location_id = children_packs[:1].current_picking_move_line_ids[:1].location_id
                    parent_pack.current_destination_location_id = children_packs[:1].current_picking_move_line_ids[:1].location_dest_id
                    parent_pack.is_processed = all([p.is_processed for p in children_packs])

    def action_toggle_processed(self):
        picking_id = self.env.context.get('picking_id')
        if picking_id:
            self.ensure_one()

            move_lines = self.current_picking_move_line_ids

            if move_lines.filtered(lambda ml: ml.qty_done < ml.product_uom_qty):
                destination_location = self.env.context.get('destination_location')
                for ml in move_lines:
                    vals = {'qty_done': ml.product_uom_qty}
                    if destination_location:
                        vals['location_dest_id'] = destination_location
                    ml.write(vals)
            else:
                for ml in move_lines:
                    ml.qty_done = 0
