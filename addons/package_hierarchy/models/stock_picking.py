from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

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
        self._set_u_result_parent_package_id()

    def _set_u_result_parent_package_id(self):
        """Set u_result_parent_package_id when moving entire parent package."""
        for picking in self:
            mls = picking.move_line_ids.filtered(lambda ml: not ml.u_result_parent_package_id)
            # Get result packages of move lines without result parent package
            result_packages = mls.mapped('result_package_id')
            parent_packages = result_packages.mapped("package_id")
            # get all children in bulk
            parent_packages.mapped('children_ids')
            for parent_package in parent_packages:
                if len(parent_package.children_ids - result_packages) == 0:
                    pack_mls = mls.filtered(
                        lambda ml: ml.result_package_id.package_id == parent_package and
                                   not ml.u_result_parent_package_id)
                    pack_mls.write({'u_result_parent_package_id': parent_package.id})
                    mls -= pack_mls

