from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    x_max_package_depth = fields.Integer(
        "Maximum Package Depth",
        default=2,
        help=(
            "Maximum depth for package hierarchy. I.e. a value of 2 would limit the number of "
            "levels in hierarchy to 2, one level of packages (with no subpackages) inside an "
            "outer package."
        ),
    )
