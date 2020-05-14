# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_result_package_link_ids = fields.Many2many(
        "package.hierarchy.link",
        column1="move_line_id",
        column2="link_id",
        string="Package hierarchy links",
    )

    def _action_done(self):
        """When a move_line is done:
          - construct the package hierarchy
          - Bypass initial multi-location checks until the moves have been completed.
             This is needed as when product is being moved in action_done, quants are created
             individually at the destination location and are attached to the relevant package.
             This may result in a temporary situation where a package contains quants from both
             the source and destination location.
        """
        Quant = self.env["stock.quant"]

        super(StockMoveLine, self.with_context(bypass_quant_multi_loc_checks=True))._action_done()

        for dest_location, move_lines in self.exists().groupby("location_dest_id"):
            move_lines.u_result_package_link_ids.construct()

        self.result_package_id.quant_ids._constrain_package()

    def construct_package_hierarchy_links(self):
        """Construct links when entire packages are being moved.
        Currently only links that remove packages from the hierarchy (unlinks)
        are constructed.
        """
        Package = self.env["stock.quant.package"]
        PackageHierarchyLink = self.env["package.hierarchy.link"]

        packages = Package.search([("id", "parent_of", self.package_id.ids)])
        packages_fulfilled = packages.filtered(lambda p: p.is_fulfilled_by(self))
        top_fulfilled_packages = packages_fulfilled.filtered(
            lambda p: p.parent_id and p.parent_id not in packages_fulfilled
        )
        PackageHierarchyLink.create_unlinks(top_fulfilled_packages, self)
