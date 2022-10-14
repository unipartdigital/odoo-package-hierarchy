from odoo import fields, models, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _compute_entire_package_ids(self):
        """Add parent packages to picking."""
        super(StockPicking, self)._compute_entire_package_ids()

        for picking in self:
            packages = self.env["stock.quant.package"]
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
            all_mls = picking.move_line_ids
            mls = all_mls.filtered(lambda ml: not ml.u_result_parent_package_id)
            # Get result packages of move lines without result parent package
            result_packages = mls.mapped("result_package_id")
            all_packages = all_mls.mapped("result_package_id")
            parent_packages = result_packages.mapped("package_id")
            # get all children in bulk
            parent_packages.mapped("children_ids")
            for parent_package in parent_packages:
                if len(parent_package.children_ids - all_packages) == 0:
                    pack_mls = mls.filtered(
                        lambda ml: ml.result_package_id.package_id == parent_package
                        and not ml.u_result_parent_package_id
                    )
                    pack_mls.write({"u_result_parent_package_id": parent_package.id})
                    mls -= pack_mls

    @api.multi
    def action_done(self):
        """
        Override to initially bypass multi location check for quant packages and call it manually
        once action_done is complete and all moves are in their new location.
        """
        Package = self.env["stock.quant.package"]
        res = super(StockPicking, self.with_context(bypass_multi_location_check=True)).action_done()
        query = """
        SELECT * FROM (
          SELECT DISTINCT UNNEST (ARRAY_AGG(DISTINCT package_id) || 
            ARRAY_AGG(DISTINCT result_package_id) || ARRAY_AGG(DISTINCT u_result_parent_package_id))
          FROM stock_move_line AS all_packages WHERE picking_id in %(picking_ids)s
          ) AS all_unique_packages 
          WHERE all_unique_packages IS NOT NULL
          ORDER BY all_unique_packages;
        """
        self.env.cr.execute(query, {"picking_ids": tuple(self.ids)},)
        tuple_unique_packages = self.env.cr.fetchall()
        package_ids = [package[0] for package in tuple_unique_packages]
        if package_ids:
            Package.browse(package_ids)._check_not_multi_location()
        return res
