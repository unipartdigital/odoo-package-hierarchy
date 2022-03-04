# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PackageHierarchyLink(models.Model):
    """Package Hierarchy Link

    This is a model used to denote the potential package hierarchy.
    Each record represents a potential relationship between a
    child package and a parent package in a future state of the
    system. Links are primarily used to check the potential
    hierarchy against constraints of the system such as maximum
    package depth and package recursion.

    If a link does not have a parent, it represents the child
    package being removed from it's current package (known as
    an unlink for the purposes of this model).

    Links may be created by and associated with move lines.
    This allows the resulting package hierachy to be checked before
    the moves have been completed, allowing early warning of
    potential constraint violation.
    """

    _name = "package.hierarchy.link"
    _description = "Links for constructing package hierarchies"
    _order = "id"

    _parent_name = "parent_id"

    name = fields.Char(index=True, store=True, compute="_compute_name")

    parent_id = fields.Many2one(
        "stock.quant.package", string="Parent package", ondelete="cascade", check_company=True
    )
    child_id = fields.Many2one(
        "stock.quant.package",
        string="Child package",
        ondelete="cascade",
        check_company=True,
        required=True,
    )
    move_line_ids = fields.Many2many(
        "stock.move.line",
        column1="link_id",
        column2="move_line_id",
        string="Stock Move Line",
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def construct(self):
        for parent_package, links in self.groupby("parent_id"):
            links.child_id.write({"parent_id": parent_package.id if parent_package else False})

    @api.model
    def create_unlinks(self, packages, move_lines=False):
        """Create links that remove packages from hierarchies."""
        # Warm the postgres cache
        packages.get_move_lines_of_children(aux_domain=[("id", "in", move_lines.ids)])
        link_vals = []
        # Create unlinks from higher level packages
        for package in packages:
            if package.parent_id:
                mls = package.get_move_lines_of_children(aux_domain=[("id", "in", move_lines.ids)])
                link_vals.append(
                    {
                        "parent_id": False,
                        "child_id": package.id,
                        "move_line_ids": [(6, 0, mls.ids if mls else False)],
                    }
                )

        if link_vals:
            return self.create(link_vals)
        return self.browse()

    @api.depends("parent_id", "child_id")
    def _compute_name(self):
        for link in self.filtered(lambda p: not isinstance(p.id, models.NewId)):
            link.name = (
                "Link %s and %s" % (link.parent_id.name, link.child_id.name)
                if link.parent_id and link.child_id
                else "Unlink parent of %s" % link.child_id.name
            )

    @api.constrains("parent_id", "child_id")
    def constrain_links(self):
        """
        Find all the links related to the links in self through their moves/moves lines,
        and call validate links to check that they don't violate any of the constraints.

        NOTE: To be 'more correct' we should check against all links from related move
        lines that are acting on same package tree, however, this may be computationally
        expensive for large systems.
        """
        links = self
        # Get the move lines
        move_lines = self.move_line_ids
        # Add the move lines of associated moves
        move_lines |= move_lines.move_id.move_line_ids
        # Add the links of these move lines
        links |= move_lines.x_result_package_link_ids
        links._validate_links()

    def _validate_links(self):
        """Validate package links to ensure that no constraints are broken.
        Current constraints are package depth and package loops.
        """
        max_package_depth = self.env.user.get_user_warehouse().x_max_package_depth

        # Sanitize links, check for repeated children as we should not have any
        # Only exception may be moving a package from one package into another package. This will
        # create a 'un-link' (no-parent) and a 'link' (with parent).
        children_count = defaultdict(int)
        for link in self:
            children_count[link.child_id] += 1
        for child_id, count in children_count.items():
            if count == 2:
                repeated_links = self.filtered(lambda x: x.child_id == child_id)
                parent_ids = [link.parent_id.id for link in repeated_links]
                if parent_ids.count(False) != 1:
                    raise ValidationError(
                        _("Links are proposing to move package to several different packages.")
                    )
            elif count > 2:
                raise ValidationError(
                    _("Links are proposing to move package to several different packages.")
                )

        # Create chains from the links
        chains = self._return_chains()
        # Create a dict of links for efficient searching for unlinks later
        unlinks_from_child = {link.child_id: link for link in self if not link.parent_id}

        # Now need to check these chains against the current reality
        # NOTE: Currently this is done for a single chain at a time, if we wanted to be
        # thorough we should check for multiple chains within the same tree at once. This
        # would only occur for very complex moves so the computational effort may not be
        # worth it for a 'normal' system.
        for chain in chains:
            # Check for self-ancestors
            current_ancestors = chain[-1]._return_ancestors()
            if any(True for node in chain if node in current_ancestors):
                raise ValidationError(_("Proposed link(s) would result in a package loop"))

            # Check the depth of the proposed tree
            # Check if there is a relevant unlink
            if unlinks_from_child.get(chain[-1], False):
                length_above_chain = 0
            else:
                length_above_chain = chain[-1]._return_num_ancestors()
            # Check depth of each node in the current to see if there is a depth violation
            allowed_length_below = max_package_depth - length_above_chain
            for i, node in enumerate(chain):
                if len(chain) - i + node.x_depth - 1 > allowed_length_below:
                    raise ValidationError(
                        _(
                            "Proposed link(s) would cause package depth "
                            "to exceed maximum permitted"
                        )
                    )

    def _return_chains(self):
        """Create chains out of links in self.
        These are returned as a list of lists of records to ensure that they are ordered.
        """
        # 1 Get all terminal children and parents
        # (excluding unlinks as they do not impact the chains)
        max_package_depth = self.env.user.get_user_warehouse().x_max_package_depth

        links_excluding_unlinks = self.filtered(lambda l: l.parent_id)
        parents = links_excluding_unlinks.parent_id
        children = links_excluding_unlinks.child_id
        terminal_parents = parents - children
        terminal_children = children - parents

        # Create a dict of links for efficient searching later
        link_from_child = {link.child_id: link for link in links_excluding_unlinks}

        # Create a dict to keep track of links that have been checked
        links_to_check = links_excluding_unlinks

        chains = []
        # 2 Follow each terminal child up the chain via links until it reaches a terminal parent
        for child in terminal_children:
            chain_length = 2
            current_link = link_from_child[child]
            nodes = [child]
            while chain_length <= max_package_depth:
                links_to_check -= current_link
                parent = current_link.parent_id
                if parent in nodes:
                    raise ValidationError(_("Proposed link(s) would result in a package loop"))
                nodes.append(parent)
                if parent in terminal_parents:
                    # 3 Add the chain when the end has been reached
                    chains.append(nodes)
                    break
                else:
                    # Get next link in chain
                    current_link = link_from_child[parent]
                    chain_length += 1
            if chain_length > max_package_depth:
                raise ValidationError(
                    _("Proposed link(s) would cause package depth to exceed maximum permitted")
                )

        # 4 Make sure that we traverse every link during steps 2+3, if links are missed
        # it indicates that a loop is present
        if links_to_check:
            raise ValidationError(_("Proposed link(s) would result in a package loop"))

        return chains
