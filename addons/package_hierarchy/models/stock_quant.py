from odoo import api, models
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.constrains("package_id")
    def _constrain_package(self):
        """Check that changing the package won't violate multi-location constraints.

        We cannot just check the top-parent package as the package may not have a parent.
        """
        context = self.env.context

        if not context.get("bypass_quant_multi_loc_checks"):
            self.package_id._check_not_multi_location()
            self.package_id._check_top_parent_not_multi_location()

    @api.model
    def _get_quants_action(self, domain=None, extend=False):
        """Hide empty quants from stock adjustment screen."""
        qty_domain = [("quantity", ">", 0)]
        if domain:
            domain += qty_domain
        else:
            domain = qty_domain
        return super(StockQuant, self)._get_quants_action(domain, extend)
