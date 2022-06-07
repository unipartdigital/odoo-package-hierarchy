from odoo import fields, models, api, _
from odoo.exceptions import UserError

import time

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _compute_entire_package_ids(self):
        """Add parent packages to picking."""
        print("#"*30)
        s = time.time()
        super(StockPicking, self)._compute_entire_package_ids()
        e = time.time()
        print(f"Took {e-s} to read XXX step 1")
        for picking in self:
            packages = self.env["stock.quant.package"]
            m1 = time.time()
            current_packages = picking.entire_package_detail_ids | picking.entire_package_ids
            m2 = time.time()
            print(f"Took {m2 - m1} to read XXX mid")
            # for parent, children_packages in current_packages.groupby("package_id"):
            #     if len(parent.children_ids - children_packages) == 0:
            #         packages |= parent
            current_packages.with_context(prefetch_fields=False).mapped("package_id")
            for package in current_packages:
                parent_pack = package.package_id
                if parent_pack and parent_pack.is_all_contents_in(current_packages):
                    packages |= parent_pack
            m3 = time.time()
            print(f"Took {m3 - m2} to read XXX mid 2")

            picking.entire_package_ids = current_packages | packages
            picking.entire_package_detail_ids = current_packages | packages
            m4 = time.time()
            print(f"Took {m4 - m3} to read XXX mid 3")
        e2 = time.time()
        print(f"Took {e2-e} to read XXX extra")

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
        res = super(StockPicking, self.with_context(bypass_multi_location_check=True)).action_done()
        self.mapped("move_line_ids").mapped("package_id")._check_not_multi_location()
        return res
