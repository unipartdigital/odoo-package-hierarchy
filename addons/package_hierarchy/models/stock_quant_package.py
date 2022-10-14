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
        "stock.quant.package",
        "Parent Package",
        ondelete="restrict",
        help="The package containing this item",
    )
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
        if not self.env.context.get("bypass_multi_location_check", False):
            packages = self.filtered(lambda p: p.package_id)
            parent_packages = self - packages
            multi_package_locations = False
            multi_parent_package_locations = False
            multi_loc_package_ids = []
            if parent_packages:
                parent_package_query = """
                    SELECT pck.package_id
                    FROM stock_quant sq
                    JOIN stock_quant_package pck
                    ON sq.package_id = pck.id
                    WHERE pck.package_id in %(package_ids)s
                    GROUP BY pck.package_id
                    HAVING COUNT(Distinct sq.location_id) > 1;
                """
                self.env.cr.execute(
                    parent_package_query, {"package_ids": tuple(parent_packages.ids)},
                )
                multi_parent_package_locations = self.env.cr.fetchall()
            if packages:
                package_query = """
                    SELECT sq.package_id
                    FROM stock_quant sq
                    WHERE sq.package_id in %(package_ids)s
                    GROUP BY sq.package_id
                    HAVING COUNT(Distinct sq.location_id) > 1;
                """
                self.env.cr.execute(
                    package_query, {"package_ids": tuple(packages.ids)},
                )
                multi_package_locations = self.env.cr.fetchall()
            if multi_parent_package_locations:
                multi_loc_package_ids.extend([result[0] for result in multi_parent_package_locations])
            if multi_package_locations:
                multi_loc_package_ids.extend([result[0] for result in multi_package_locations])
            if multi_loc_package_ids:
                multi_loc_packages = self.browse(multi_loc_package_ids)
                raise ValidationError(
                    _("The following packages cannot be set into multiple locations:\n%s") %
                    (", ".join([p.name for p in multi_loc_packages]))
                )

    @api.depends('package_id', 'children_ids')
    def _compute_parent_ids(self):
        for package in self.filtered(lambda p: not isinstance(p.id, models.NewId)):
            package.parent_ids = self.env['stock.quant.package'].search([('id', 'parent_of', package.id)]).ids

    @api.depends('package_id', 'children_ids', 'quant_ids.package_id')
    def _compute_children_quant_ids(self):
        for package in self.filtered(lambda p: not isinstance(p.id, models.NewId)):
            package.children_quant_ids = self.env['stock.quant'].search([('package_id', 'child_of', package.id)])

    @api.depends('quant_ids.package_id', 'quant_ids.location_id', 'quant_ids.company_id', 'quant_ids.owner_id')
    def _compute_package_info(self):
        for package in self:
            values = {
                'location_id': False, 'company_id': self.env.user.company_id.id, 'owner_id': False
            }
            locations = package.with_context(prefetch_fields=False).children_quant_ids.mapped('location_id')
            if len(locations) == 1:
                values['location_id'] = locations
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

    def action_view_picking(self):
        """
        Override method to be able to see package transfers from a parent package too.
        Default filter will be confirmed picks:
          state in ('confirmed', 'waiting', 'assigned')
        """
        MoveLine = self.env["stock.move.line"]
        action = self.env.ref("stock.action_picking_tree_all").read()[0]

        packages = self.search([("id", "child_of", self.ids), ("package_id", "!=", False)])
        domain = [
            "|", ("result_package_id", "in", packages.ids), ("package_id", "in", packages.ids)
        ]
        pickings = MoveLine.search(domain).mapped("picking_id")
        action["domain"] = [("id", "in", pickings.ids)]
        action["context"] = {"search_default_confirmed": 1}
        return action
