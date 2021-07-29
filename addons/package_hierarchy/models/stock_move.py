# -*- coding: utf-8 -*-
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """
        Override to set result parent package in move lines if applicable.

        If a parent package if set then also set the result package to avoid triggering an error
        about trying to set a result parent package without a result package.
        """
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)

        if reserved_quant:
            reserved_quant.ensure_one()

            parent_package_id = (
                reserved_quant.package_id.package_id.id if reserved_quant.package_id else False
            )
            if parent_package_id:
                package_id = vals.get("package_id", False)
                vals.update(
                    {
                        "result_package_id": package_id,
                        "u_result_parent_package_id": parent_package_id,
                    }
                )

        return vals
