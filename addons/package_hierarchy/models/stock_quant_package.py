"""Packages with inheritance."""

import logging
from itertools import chain, tee

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero, float_compare

_logger = logging.getLogger(__name__)


def pairwise(original_list):
    """"
    Returning couples of a list with N elements, example:
    s(N) -> [(s0,s1), (s1,s2), (s2, s3), ... (sN-1, sN)]"""
    a, b = tee(original_list)
    next(b, None)
    return zip(a, b)


class QuantPackage(models.Model):
    """Add the ability for a package to contain another package """

    _inherit = "stock.quant.package"
    _parent_name = "parent_id"
    _parent_order = "name"
    _order = "id"

    display_name = fields.Char("Display Name", compute="_compute_display_name")
    parent_id = fields.Many2one(
        "stock.quant.package",
        "Parent Package",
        ondelete="restrict",
        help="The package containing this item",
    )
    x_top_parent_id = fields.Many2one(
        "stock.quant.package", compute="_compute_top_parent_id", store=True
    )
    x_aggregated_quant_ids = fields.One2many(
        "stock.quant",
        string="Aggregated Quants",
        compute="_compute_aggregated_quant_ids",
        help=(
            "All quants that are contained within the package "
            "and within the contained package hierarchy."
        ),
    )
    child_ids = fields.One2many("stock.quant.package", "parent_id", "Contained Packages")
    x_depth = fields.Integer(string="Depth", compute="_compute_depth", store=True)

    @api.depends("parent_id", "parent_id.x_top_parent_id")
    def _compute_top_parent_id(self):
        for pack in self:
            parent = pack.parent_id
            if not parent:
                pack.x_top_parent_id = False
            elif parent.x_top_parent_id:
                pack.x_top_parent_id = parent.x_top_parent_id
            else:
                pack.x_top_parent_id = parent

    @api.constrains("parent_id", "child_ids")
    @api.onchange("parent_id", "child_ids")
    def _constrain_depth(self):
        max_package_depth = self.env.user.get_user_warehouse().x_max_package_depth
        for pack in self:
            top_parent = pack.x_top_parent_id
            if top_parent.x_depth > max_package_depth:
                raise ValidationError(_("Maximum package depth exceeded."))

    @api.depends("child_ids", "child_ids.x_depth")
    def _compute_depth(self):
        """Is the max depth of any children"""
        for pack in self:
            children = pack.child_ids
            if not children:
                pack.x_depth = 1
            else:
                pack.x_depth = max(pack.child_ids.mapped("x_depth")) + 1

    @api.constrains("x_top_parent_id")
    def _check_top_parent_not_multi_location(self):
        # Need trigger x_aggregated_quant_ids of top parent to be recomputed
        # before checking for multi-location as this may not have happened
        # automatically.
        self.x_top_parent_id._compute_aggregated_quant_ids()
        self.x_top_parent_id._check_not_multi_location()

    @api.constrains("parent_id")
    def _check_package_recursion(self):
        if not self._check_recursion("parent_id"):
            raise ValidationError("A package cannot be its own ancestor.")

    def _check_not_multi_location(self):
        for package in self:
            locations = package.x_aggregated_quant_ids.location_id
            if len(locations) > 1:
                raise ValidationError(
                    _("Package cannot be in multiple " "locations:\n%s\n%s")
                    % (package.name, ", ".join([l.name for l in locations]))
                )

    def _return_num_ancestors(self):
        self.ensure_one()
        return self.search_count([("id", "parent_of", self.id)]) - 1

    def _return_ancestors(self):
        self.ensure_one()
        packages = self.search([("id", "parent_of", self.id)])
        return packages - self

    @api.depends(
        "child_ids",
        "quant_ids.package_id",
        "child_ids.quant_ids",
        "child_ids.quant_ids.package_id",
    )
    def _compute_aggregated_quant_ids(self):
        Quant = self.env["stock.quant"]

        for package in self:
            if isinstance(package.id, models.NewId):
                package.x_aggregated_quant_ids = package.quant_ids
            else:
                package.x_aggregated_quant_ids = Quant.search(
                    [
                        ("package_id", "child_of", package.id),
                        "|",
                        ("quantity", "!=", 0),
                        ("reserved_quantity", "!=", 0),
                    ]
                )

    @api.depends(
        "quant_ids.package_id",
        "quant_ids.location_id",
        "quant_ids.company_id",
        "quant_ids.owner_id",
        "quant_ids.quantity",
        "quant_ids.reserved_quantity",
        "child_ids",
        "child_ids.parent_id",
        "child_ids.location_id",
        "child_ids.company_id",
        "child_ids.owner_id",
    )
    def _compute_package_info(self):
        Location = self.env["stock.location"]
        Company = self.env["res.company"]
        Partner = self.env["res.partner"]

        for package in self:
            # Initialise empty recordsets
            comparison_recordsets = {
                "location_id": Location,
                "company_id": Company,
                "owner_id": Partner,
            }

            for records in [package.quant_ids, package.child_ids]:
                if records:
                    comparison_recordsets["location_id"] |= records[0].location_id
                    comparison_recordsets["company_id"] |= records.company_id
                    comparison_recordsets["owner_id"] |= records.owner_id

            # If we don't have conflicting records, add to values.
            values = {
                key: recordsets
                for (key, recordsets) in comparison_recordsets.items()
                if len(recordsets) == 1
            }

            package.location_id = values.get("location_id", False)
            package.company_id = values.get("company_id", False)
            package.owner_id = values.get("owner_id", False)

    @api.depends("parent_id")
    def _compute_display_name(self):
        """Compute the display name for a package. Include name of immediate parent."""
        for package in self:
            if package.parent_id:
                package.display_name = "%s/%s" % (package.parent_id.name, package.name)
            else:
                package.display_name = package.name

    def _get_contained_quants(self):
        """Overide to include picks quants of child packages"""
        Quant = self.env["stock.quant"]

        return Quant.search([("package_id", "child_of", self.ids)])

    def _get_move_lines_of_children_domain(self):
        return [
            "|",
            ("result_package_id", "child_of", self.ids),
            ("package_id", "child_of", self.ids),
        ]

    def get_move_lines_of_children(self, aux_domain=None, **kwargs):
        MoveLines = self.env["stock.move.line"]

        domain = self._get_move_lines_of_children_domain()
        if aux_domain:
            domain.extend(aux_domain)
        if "order" not in kwargs:
            kwargs["order"] = "id"
        return MoveLines.search(domain, **kwargs)

    def action_view_picking(self):
        """Overide to include picks of child packages"""
        MoveLines = self.env["stock.move.line"]

        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        domain = self._get_move_lines_of_children_domain()
        pickings = MoveLines.search(domain, order="id").picking_id
        action["domain"] = [("id", "in", pickings.ids)]
        return action

    def product_quantities_by_key(self, get_key=lambda q: q.product_id):
        """This function computes the product quantities the given package grouped by a key
        Args:
            get_key: a callable which takes a quant and returns the key

        """
        res = {}
        for key, quant_grp in self._get_contained_quants().groupby(get_key):
            res[key] = sum(quant_grp.mapped("quantity"))
        return res

    def is_fulfilled_by(self, move_lines):
        """Check if a set of packages are fulfilled by a set of move lines"""
        Precision = self.env["decimal.precision"]

        def get_key(x):
            return (x.product_id, x.lot_id)

        precision_digits = Precision.precision_get("Product Unit of Measure")
        pack_qtys = self.product_quantities_by_key(get_key)
        pack_move_lines = self.get_move_lines_of_children(aux_domain=[("id", "in", move_lines.ids)])

        mls_qtys = {}
        for key, mls_grp in pack_move_lines.groupby(get_key):
            mls_qtys[key] = sum(mls_grp.mapped("product_qty"))

        for key in set(chain(pack_qtys.keys(), mls_qtys.keys())):
            if (
                float_compare(
                    pack_qtys.get(key, 0), mls_qtys.get(key, 0), precision_digits=precision_digits
                )
                > 0
            ):
                return False
        return True

    def _get_package_link_structure(self):
        """Get package link structure, in case not founded after specific search args,
        create a new one"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]

        self.ensure_one()
        hierarchy_lines = PackageHierarchyLink.browse()
        package = self
        while package.parent_id:
            parent_hierarchy_lines = PackageHierarchyLink.search(
                [("child_id", "=", package.id), ("parent_id", "=", package.parent_id.id)], limit=1
            )
            if not parent_hierarchy_lines:
                parent_hierarchy_lines = PackageHierarchyLink.create(
                    {"child_id": package.id, "parent_id": package.parent_id.id}
                )
            hierarchy_lines = hierarchy_lines | parent_hierarchy_lines
            package = package.parent_id
        package_hierarchy_lines = PackageHierarchyLink.search(
            [("child_id", "=", package.id), ("parent_id", "=", False)], limit=1
        )
        if not package_hierarchy_lines:
            package_hierarchy_lines = PackageHierarchyLink.create(
                {"child_id": package.id, "parent_id": False}
            )
        hierarchy_lines = hierarchy_lines | package_hierarchy_lines
        return hierarchy_lines.ids

    def get_or_construct_hierarchy_from_packages(self):
        """Getting or Creating (if any of hierarchy nodes doesnt exist) all hierarchy links of
        ordered packages that are in self recordset.

        :return: recordset of package hierarchy links
        """
        # Setting self to sudo to over pass access rights at this moment, have to be reviewed later
        self = self.sudo()
        PackageHierarchyLink = self.env["package.hierarchy.link"]

        # Empty recordset
        package_hierarchies = PackageHierarchyLink.browse()
        if not self.exists():
            return package_hierarchies
        # Looping in pairs through packages which are ordered
        for package, parent_package in pairwise(self):
            hierarchy_link = PackageHierarchyLink.search(
                [("child_id", "=", package.id), ("parent_id", "=", parent_package.id)], limit=1
            )
            if not hierarchy_link:
                hierarchy_link = PackageHierarchyLink.create({
                    "child_id": package.id,
                    "parent_id": parent_package.id
                })
            package_hierarchies |= hierarchy_link
        # If is only one record in self will not enter in the loop and will
        # need to find the unlink for self
        if len(self) == 1:
            parent_package = self
        hierarchy_link = PackageHierarchyLink.search(
                [("child_id", "=", parent_package.id), ("parent_id", "=", False)], limit=1
            )
        if not hierarchy_link:
            hierarchy_link = PackageHierarchyLink.create({
                "child_id": parent_package.id
            })
        package_hierarchies |= hierarchy_link
        return package_hierarchies
