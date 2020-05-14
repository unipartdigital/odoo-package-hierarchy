from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _check_entire_pack(self):
        """Create links when moving entire parent packages."""
        super(StockPicking, self)._check_entire_pack()
        self.move_line_ids.construct_package_hierarchy_links()
