from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_pallet_id = fields.Many2one('stock.quant.package', 'Pallet:')

    def palletise(self):
        self.ensure_one()
        if not self.x_pallet_id:
            raise UserError(_('Select a pallet.'))

        selected_lines = self.move_line_ids.filtered(lambda l: l.x_selected)
        if not len(selected_lines):
            # If there are no selected lines, palletise was a no-op.
            # It wasn't intentionally being used that way, and is generally a
            # sign that it's being called when it shouldn't be, eg after
            # incorrect initialization, so it now raises an error instead of
            # silently doing nothing.
            raise UserError(_('palletise requires at least one selected line'))
        selected_lines.mapped('result_package_id').write({'package_id': self.x_pallet_id.id})
        self.x_pallet_id._check_not_multi_location()
        self.move_line_ids.write({'x_selected': False})
        self.x_pallet_id = None

    def _compute_entire_package_ids(self):
        """Add parent packages to picking."""
        super(StockPicking, self)._compute_entire_package_ids()

        for picking in self:
            packages = self.env['stock.quant.package']
            current_packages = picking.entire_package_detail_ids | picking.entire_package_ids

            for package in current_packages:
                parent_pack = package.package_id
                if parent_pack and parent_pack.is_all_contents_in(current_packages):
                    packages |= parent_pack

            picking.entire_package_ids = current_packages | packages
            picking.entire_package_detail_ids = current_packages | packages

    def _check_entire_pack(self):
        """Set u_result_parent_package_id when moving entire parent package."""
        super(StockPicking, self)._check_entire_pack()
        for picking in self:
            result_packages = picking.move_line_ids.mapped('result_package_id')
            parent_packages = result_packages.mapped("package_id")
            for parent_package in parent_packages:
                if len(parent_package.children_ids - result_packages) == 0:
                    picking.move_line_ids.filtered(lambda ml: ml.result_package_id.package_id == parent_package).write({'u_result_parent_package_id': parent_package.id})

