from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _check_entire_pack(self):
        """Create links when moving entire parent packages."""
        super(StockPicking, self)._check_entire_pack()
        mls_to_check = self.move_line_ids
        if self._context.get("check_mls"):
            mls_to_check = mls_to_check.filtered(lambda ml: ml.id in self._context.get("check_mls"))
        mls_to_check.construct_package_hierarchy_links()
