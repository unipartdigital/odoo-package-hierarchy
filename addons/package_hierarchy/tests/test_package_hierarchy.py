"""Test odoo-package-hierarchy"""

from odoo.exceptions import ValidationError

from . import common

# Note that quant actually is being used; action_assign finds it.
class TestPackageHierarchy(common.BaseHierarchy):
    """Tests for odoo-package-hierarchy.

    These tests are oriented for coverage, but do some correctness checks."""
    def setUp(self):
        """Set up common prerequisites for testing odoo-package-hierarchy.

        This includes one product, a quant for that product,
        a picking, and start and end locations for the picking.
        The move is explicitly created, while move_lines are implicit.
        """
        super(TestPackageHierarchy, self).setUp()
        self.env.user.get_user_warehouse().write({
            'u_max_package_depth': 4,
        })
        Package = self.env['stock.quant.package']
        self.package = Package.create({})  # an empty package is enough
        self.pallet = Package.create({})
        apple_qty = 10
        self.quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                       apple_qty, package_id=self.package.id)
        self.picking = self.create_picking(self.picking_type_internal)
        self.create_move(self.apple, apple_qty, self.picking)

        # Confirm the picking to go from the draft state to the confirmed state
        self.picking.action_confirm()
        # Assign the stock to the picking (do the reservation).
        self.picking.action_assign()
        self.assertEqual(self.quant.reserved_quantity, apple_qty)

    def assert_lists_are_equivalent(self, list1, list2):
        """For when we only care that the elements in a list are the same, and not the order."""
        self.assertEqual(len(list1), len(list2))
        self.assertEqual(set(list1), set(list2))

    def test_compute_top_parent_id(self):
        """Test that the top_parent_id is correctly computed and
        is automatically re-computed (to correct value) on change to hierarchy"""
        Package = self.env['stock.quant.package']
        box = Package.create({})
        sub_box = Package.create({})
        box.parent_id = self.package
        sub_box.parent_id = box
        self.assertEqual(box.top_parent_id, self.package)
        self.package.parent_id = self.pallet
        self.assertEqual(self.package.top_parent_id, self.pallet)
        self.assertFalse(self.pallet.top_parent_id)
        self.assertEqual(box.top_parent_id, self.pallet)
        self.assertEqual(sub_box.top_parent_id, self.pallet)

    def test_compute_depth(self):
        """Test that the depth is correctly calulated and updated."""
        Package = self.env['stock.quant.package']
        box = Package.create({})
        self.package.parent_id = self.pallet
        self.assertEqual(self.pallet.depth, 2)
        self.assertEqual(self.package.depth, 1)
        box.parent_id = self.package
        self.assertEqual(self.pallet.depth, 3)
        self.assertEqual(self.package.depth, 2)
        self.assertEqual(box.depth, 1)

    def test_check_not_multi_location(self):
        """Test that the happy case where quants are in the same location
        doesn't raise an exception."""
        second_qty = 11
        self.create_quant(self.apple.id, self.test_location_01.id,
                          second_qty, package_id=self.package.id)
        self.package._check_not_multi_location()

    def test_check_not_multi_location_quant_not_colocated(self):
        """Make sure that one package's quants are in the same location."""
        # This test also provides coverage for _compute_childen_quant_ids
        second_qty = 11
        with self.assertRaises(ValidationError):
            self.create_quant(self.apple.id, self.test_location_02.id,
                              second_qty, package_id=self.package.id)

    def test_check_top_parent_not_multi_location(self):
        """Make sure that a parent package is not multi-location.

        This means checking that its children are in the same location."""
        Package = self.env['stock.quant.package']
        package2 = Package.create({})
        second_qty = 11
        self.create_quant(self.apple.id, self.test_location_02.id,
                          second_qty, package_id=package2.id)
        # This does not need to duplicate the checks that each child is valid;
        # _check_not_multi_location is called via aggregated_quant_ids.
        self.package.parent_id = self.pallet
        # Expect adding a package at another location to a pallet to fail
        with self.assertRaises(ValidationError):
            package2.parent_id = self.pallet

    def test_check_top_parent_not_multi_location_branched(self):
        """Make sure that a tree is not multi-location when a different branch
        of the package tree is located in a different location.

        This means checking that all quants descending from the top parent
        are in the same location."""
        Package = self.env['stock.quant.package']
        package2 = Package.create({})
        subpackage2 = Package.create({})
        package2.parent_id = self.pallet
        self.package.parent_id = self.pallet

        second_qty = 11
        self.create_quant(self.apple.id, self.test_location_02.id,
                          second_qty, package_id=subpackage2.id)

        # Expect adding a package from another location to the pallet to fail
        with self.assertRaises(ValidationError):
            subpackage2.parent_id = package2

    def test_return_num_ancestors(self):
        """Test that the correct number of ancestors is calculated"""
        Package = self.env['stock.quant.package']
        box = Package.create({})
        box.parent_id = self.package
        self.package.parent_id = self.pallet
        self.assertEqual(self.pallet._return_num_ancestors(), 0)
        self.assertEqual(self.package._return_num_ancestors(), 1)
        self.assertEqual(box._return_num_ancestors(), 2)

    def test_return_ancestors(self):
        """Test that all ancestors are returned by _return_ancestors()."""
        Package = self.env['stock.quant.package']
        box = Package.create({})
        box.parent_id = self.package
        self.package.parent_id = self.pallet
        self.assertFalse(self.pallet._return_ancestors())
        self.assertEqual(self.package._return_ancestors(), self.pallet)
        self.assertEqual(box._return_ancestors(), self.package + self.pallet)

    def test_aggregated_quant_ids(self):
        """Make sure _compute_aggregated_quant_ids includes child package quants and
           excludes zero quantity/reserved_quantity quants"""
        Package = self.env['stock.quant.package']

        qty_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                      5, package_id=self.pallet.id)
        zero_qty_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                           0, package_id=self.pallet.id)
        self.assertEqual(self.pallet.aggregated_quant_ids.ids, [qty_quant.id])

        self.package.parent_id = self.pallet
        package_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                          10, package_id=self.package.id)

        self.assert_lists_are_equivalent(self.pallet.aggregated_quant_ids.ids,
                                         [qty_quant.id, self.quant.id, package_quant.id])

        # Change parent of package to a new pallet and check the original pallet's
        # children quants are correct
        pallet2 = Package.create({})
        self.package.parent_id = pallet2
        self.assertEqual(self.pallet.aggregated_quant_ids.ids, [qty_quant.id])

    def test_aggregated_quant_ids_higher_depth(self):
        """Make sure _compute_aggregated_quant_ids for depths greater than 2"""
        Package = self.env['stock.quant.package']

        box = Package.create({})
        box.parent_id = self.package
        box_child = Package.create({})
        box_child.parent_id = box

        box_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                      5, package_id=box.id)
        box_child_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                            10, package_id=box_child.id)

        self.assert_lists_are_equivalent(self.package.aggregated_quant_ids.ids,
                                         [self.quant.id, box_quant.id, box_child_quant.id])

    def test_compute_package_info(self):
        """Make sure _compute_package_info runs on both packages and pallets."""
        # This just runs the code for coverage. Checking the logic would only
        # be a duplicate of the implementation, so isn't done.
        self.package._compute_package_info()
        self.package.parent_id = self.pallet
        self.pallet._compute_package_info()

    def test_compute_display_name(self):
        """Make sure _compute_display_name runs on both packages and pallets."""
        self.package._compute_display_name()
        self.assertEqual(self.package.display_name, self.package.name)

        self.package.parent_id = self.pallet
        self.package._compute_display_name()
        compound_name = "%s/%s" % (self.pallet.name, self.package.name)
        self.assertEqual(self.package.display_name, compound_name)

        self.pallet._compute_display_name()
        self.assertEqual(self.pallet.display_name, self.pallet.name)

    def test_get_contained_quants(self):
        """Make sure _get_contained_quants includes quands of child packages"""
        self.package_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                               5, package_id=self.package.id)

        self.pallet.parent_id = self.package
        self.pallet_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                              10, package_id=self.pallet.id)

        self.assertEqual(self.package._get_contained_quants().ids,
                         [self.quant.id, self.package_quant.id, self.pallet_quant.id])

    def test_get_move_lines_of_children(self):
        """Test that get_move_lines_of_children can return move-lines associated with the package,
        for when it is both the package_id and result_package_id for the moveline."""
        # Initially the package is associated with both package_id and result_package_id
        self.assertEqual(self.package.get_move_lines_of_children(), self.picking.move_line_ids[0])
        # Remove package from both to test that nothing is returned
        # if package is not associated with any mls
        self.picking.move_line_ids[0].package_id = None
        self.picking.move_line_ids[0].result_package_id = None
        self.assertFalse(self.package.get_move_lines_of_children())
        # Associate with package_id only
        self.picking.move_line_ids[0].package_id = self.package
        self.assertEqual(self.package.get_move_lines_of_children(), self.picking.move_line_ids[0])
        # Associate with result_package_id only
        self.picking.move_line_ids[0].package_id = None
        self.picking.move_line_ids[0].result_package_id = self.package
        self.assertEqual(self.package.get_move_lines_of_children(), self.picking.move_line_ids[0])

    def test_action_view_picking_domain(self):
        """Make sure the domain from the view picking action is correct"""
        Package = self.env['stock.quant.package']

        box = Package.create({})
        box.parent_id = self.package
        box_child = Package.create({})
        box_child.parent_id = box

        # Create another picking and ensure both picking and picking2 are in the domain
        picking2 = self.create_picking(self.picking_type_internal)
        move2 = self.create_move(self.banana, 2, picking2)

        # move_line2 should be included even though only result_package_id is set
        # and package_id is False
        move_line2_vals = {'picking_id': picking2.id,
                           'package_id': False,
                           'result_package_id': box.id}
        move_line2 = self.create_move_line(move2, 2, **move_line2_vals)

        action_res = self.package.action_view_picking()
        domain = action_res.get('domain', [])

        domain_first_arg = domain[0]
        domain_first_arg_field = domain_first_arg[0]
        domain_first_arg_operator = domain_first_arg[1]
        domain_first_arg_value = domain_first_arg[2]

        self.assertEqual(domain_first_arg_field, 'id')
        self.assertEqual(domain_first_arg_operator, 'in')
        self.assert_lists_are_equivalent(domain_first_arg_value, [picking2.id, self.picking.id])

    def test_is_fulfilled_by(self):
        """Test that is_fulfilled_by correctly identifies packages fulfilled
        by movelines."""
        # Test for a single package/moveline
        self.assertTrue(self.package.is_fulfilled_by(self.picking.move_line_ids))

        # Test for multiple packages/movelines
        Package = self.env['stock.quant.package']
        boxes = Package.create([{}, {}])
        quant1 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   1, package_id=boxes[0].id)
        quant2 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   1, package_id=boxes[1].id)

        picking2 = self.create_picking(self.picking_type_internal)
        move2 = self.create_move(self.banana, 2, picking2)
        picking2.action_confirm()
        picking2.action_assign()
        self.assertTrue(boxes.is_fulfilled_by(picking2.move_line_ids))
        # Test cases where it will not fulfill
        self.assertFalse(boxes.is_fulfilled_by(self.picking.move_line_ids))
        boxes += self.package
        self.assertFalse(boxes.is_fulfilled_by(picking2.move_line_ids))
        # Test for multiple moves
        self.assertTrue(boxes.is_fulfilled_by(picking2.move_line_ids + self.picking.move_line_ids))

    def test_is_fulfilled_by_incorrect_quantity(self):
        """Test that is_fulfilled_by correctly identifies when movelines do not fulfill
        packages due to incorrect quantities."""
        # Test the correct cases
        self.assertTrue(self.package.is_fulfilled_by(self.picking.move_line_ids))
        self.quant.quantity -= 1
        self.assertTrue(self.package.is_fulfilled_by(self.picking.move_line_ids))
        # Test incorrect case
        self.quant.quantity += 2
        self.assertFalse(self.package.is_fulfilled_by(self.picking.move_line_ids))

    def test_assert_moveline_link_not_created(self):
        """Assert package links not created when not unlinking"""
        Package = self.env['stock.quant.package']
        package1 = Package.create({})
        pallet1 = Package.create({})
        package1.parent_id = pallet1
        self.create_quant(self.apple.id, self.test_location_02.id,
                          7, package_id=package1.id)
        self.create_quant(self.banana.id, self.test_location_02.id,
                          8, package_id=package1.id)
        picking = self.create_picking(self.picking_type_internal)
        self.create_move(self.apple, 7, picking)
        self.create_move(self.banana, 8, picking)
        picking.action_confirm()
        picking.action_assign()

        self.assertFalse(picking.move_line_ids[0].u_result_package_link_ids)

    def test_action_done(self):
        """Test that action done works as expected with package hierarchies
        when moving entire packages."""
        Package = self.env['stock.quant.package']
        boxes = Package.create([{}, {}])
        pallet = Package.create({})
        boxes.parent_id = pallet
        quant1 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   1, package_id=boxes[0].id)
        quant2 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   1, package_id=boxes[1].id)

        picking2 = self.create_picking(self.picking_type_internal)
        picking2.location_dest_id = self.test_location_02
        move2 = self.create_move(self.banana, 2, picking2)
        picking2.action_confirm()
        picking2.action_assign()
        picking2.move_line_ids.qty_done = 1
        picking2.action_done()
        self.assertEqual(pallet.location_id, self.test_location_02)
        self.assertEqual(boxes.location_id, self.test_location_02)
        self.assertEqual(boxes.parent_id, pallet)

    def test_action_done_partial(self):
        """Test that action done works as expected with package hierarchies
        when moving a combination of an entire package out of a parent package and
        the partial contents of a package."""
        Package = self.env['stock.quant.package']
        box1 = Package.create({})
        box2 = Package.create({})
        pallet = Package.create({})
        box1.parent_id = pallet
        box2.parent_id = pallet
        quant1 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   2, package_id=box1.id)
        quant2 = self.create_quant(self.banana.id, self.test_location_01.id,
                                   3, package_id=box2.id)

        picking2 = self.create_picking(self.picking_type_internal)
        picking2.location_dest_id = self.test_location_02
        move2 = self.create_move(self.banana, 4, picking2)
        picking2.action_confirm()
        picking2.action_assign()
        links = picking2.move_line_ids.u_result_package_link_ids
        self.assertEqual(len(links), 1)
        self.assertFalse(links.parent_id)
        self.assertEqual(links.child_id, box1)
        for ml in picking2.move_line_ids:
            ml.qty_done = ml.product_qty
        picking2.action_done()
        self.assertEqual(pallet.location_id, self.test_location_01)
        self.assertEqual(box1.location_id, self.test_location_02)
        self.assertEqual(box2.location_id, self.test_location_01)
        self.assertFalse(box1.parent_id)
        self.assertEqual(box2.parent_id, pallet)


class TestPackageInheritance(common.BaseHierarchy):
    """Tests for inheritance and recursion."""

    def setUp(self):
        """Set up four packages."""
        super().setUp()

        # Set maximum package depth to 3
        self.env.user.get_user_warehouse().write({
            'u_max_package_depth': 3,
        })

        Package = self.env["stock.quant.package"]

        # Create four packages.
        self.package_a = Package.create({'name': 'A'})
        self.package_b = Package.create({'name': 'B'})
        self.package_c = Package.create({'name': 'C'})
        self.package_d = Package.create({'name': 'D'})

    def test_self_cannot_be_parent(self):
        """Test that a package cannot be set as its own parent."""
        with self.assertRaises(ValidationError):
            self.package_a.write({"parent_id": self.package_a.id})

    def test_child_cannot_be_parent(self):
        """Test that a package's child cannot be set as its parent."""
        self.package_b.write({"parent_id": self.package_a.id})
        with self.assertRaises(ValidationError):
            self.package_a.write({"parent_id": self.package_b.id})

    def test_gradchild_cannot_be_parent(self):
        """Test that a package's child's child cannot be set as its parent."""
        self.package_b.write({"parent_id": self.package_a.id})
        self.package_c.write({"parent_id": self.package_b.id})
        with self.assertRaises(ValidationError):
            self.package_a.write({"parent_id": self.package_c.id})

    def test_self_cannot_be_child(self):
        """Test that a package cannot be set as its own child."""
        with self.assertRaises(ValidationError):
            self.package_a.write({"children_ids": [(4, self.package_a.id, False)]})

    def test_parent_cannot_be_child(self):
        """Test that a package's parent cannot be set as its child."""
        self.package_a.write({"parent_id": self.package_b.id})
        with self.assertRaises(ValidationError):
            self.package_a.write({"children_ids": [(4, self.package_b.id, False)]})

    def test_grandparent_cannot_be_child(self):
        """Test that a package's parent's parent cannot be set as its child."""
        self.package_a.write({"parent_id": self.package_b.id})
        self.package_b.write({"parent_id": self.package_c.id})
        with self.assertRaises(ValidationError):
            self.package_a.write({"children_ids": [(4, self.package_c.id, False)]})

    def test_max_package_depth_cannot_be_exceeded(self):
        """Test that warehouse max package depth canoot be exceeded"""
        self.package_b.write({"parent_id": self.package_a.id})
        self.package_c.write({"parent_id": self.package_b.id})
        with self.assertRaises(ValidationError):
            self.package_d.write({"parent_id": self.package_c.id})


class TestPackageHierarchyLinks(common.BaseHierarchy):
    """Tests for package hierarchy links."""

    def setUp(self):
        """Set up four packages."""
        super().setUp()

        # Set maximum package depth to 4
        self.env.user.get_user_warehouse().write({
            'u_max_package_depth': 4,
        })

        Package = self.env["stock.quant.package"]

        self.other_package = Package.create({'name': 'Other'})

        # Create packages
        self.package_a = Package.create({'name': 'A'})
        self.package_b = Package.create({'name': 'B'})
        self.package_c = Package.create({'name': 'C'})
        self.package_d = Package.create({'name': 'D'})
        self.package_e = Package.create({'name': 'E'})
        self.package_f = Package.create({'name': 'F'})

        # Create parent/child relationship with packages
        self.package_b.parent_id = self.package_a
        self.package_c.parent_id = self.package_a
        self.package_d.parent_id = self.package_b

    def test_create_unlinks(self):
        """Make sure that top level unlinks are constructed correctly"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        apply_qty = 2

        # Create quant for top level parent package_a
        quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                  apply_qty, package_id=self.package_a.id)
        picking = self.create_picking(self.picking_type_internal)

        move = self.create_move(self.apple, apply_qty, picking)
        move_line_vals = {'picking_id': picking.id,
                          'package_id': self.package_a.id,
                          'result_package_id': self.package_a.id}
        move_line = self.create_move_line(move, 2, **move_line_vals)

        # Should not create an unlink as package_a is the top level package so no unlink is required
        package_a_unlinks = PackageHierarchyLink.create_unlinks(self.package_a, move_line)
        self.assertEqual(len(package_a_unlinks), 0)

        # Create quant with package_d which is a child of package_b,
        # which in turn is a child of package_a
        quant2 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_d.id)
        picking2 = self.create_picking(self.picking_type_internal)

        move2 = self.create_move(self.apple, apply_qty, picking2)
        move_line2_vals = {'picking_id': picking2.id,
                           'package_id': self.package_d.id,
                           'result_package_id': self.package_d.id}
        move_line2 = self.create_move_line(move2, 2, **move_line2_vals)

        # Should create an unlink as package_b has a parent (package_a)
        # which should include the previously created move line
        package_b_unlinks = PackageHierarchyLink.create_unlinks(self.package_b,
                                                                          move_line2)
        self.assertEqual(len(package_b_unlinks), 1)
        self.assertEqual(package_b_unlinks.move_line_ids[0].id, move_line2.id)

    def test_compute_name(self):
        """Make sure the package link name is correctly computed"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]

        # Create a link between package_d (parent) and package_e (child)
        link = PackageHierarchyLink.create({
            'parent_id': self.package_d.id,
            'child_id': self.package_e.id,
        })
        self.assertEqual(link.name, "Link D and E")

        # Update link so that is now a link between D and F and ensure name is updated
        link.child_id = self.package_f
        self.assertEqual(link.name, "Link D and F")

        # Update link so that package_f is now unlinked and ensure name is updated
        link.parent_id = False
        self.assertEqual(link.name, "Unlink parent of F")

    def test_construct_package_hierarchy_links(self):
        """Make sure that unlinks for fulfilled non-top level packages are constructed correctly"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]

        apply_qty = 2

        # Create quants for package_b and it's child package_d
        quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                  apply_qty, package_id=self.package_b.id)
        quant2 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_d.id)

        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, apply_qty, picking)
        picking.action_confirm()

        move_line_vals = {'picking_id': picking.id,
                          'package_id': self.package_d.id,
                          'result_package_id': self.package_d.id}

        package_d_link_domain = [('parent_id', '=', False), ('child_id', '=', self.package_d.id)]

        # Create move line with quantity that is less than the package has
        # and check that no unlink is created as package_d will not be fulfilled
        move_line = self.create_move_line(move, apply_qty - 1, **move_line_vals)
        move_line.construct_package_hierarchy_links()
        package_d_link_recs = PackageHierarchyLink.search(package_d_link_domain)
        self.assertEqual(len(package_d_link_recs), 0)

        # Set move line to quantity that is more than the package has
        # and check that a unlink is created as package_d will not be fulfilled
        move_line.product_uom_qty = apply_qty + 1
        move_line.construct_package_hierarchy_links()
        package_d_link_recs = PackageHierarchyLink.search(package_d_link_domain)
        self.assertEqual(len(package_d_link_recs), 1)

        # Set move line to quantity that is equal to the move
        # and check if unlink for package_d is created
        package_d_link_recs.unlink()
        move_line.product_uom_qty = apply_qty
        move_line.construct_package_hierarchy_links()
        package_d_link_recs = PackageHierarchyLink.search(package_d_link_domain)
        self.assertEqual(len(package_d_link_recs), 1)

    def test_construct_package_hierarchy_links_correct(self):
        """Make sure that unlinks for multi-level packages are identified correctly."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        Package = self.env["stock.quant.package"]

        pallet = Package.create({'name': 'Pallet'})
        self.package_a.parent_id = pallet
        self.package_b.parent_id = pallet

        self.package_c.parent_id = self.package_a
        self.package_d.parent_id = self.package_a
        self.package_e.parent_id = self.package_b
        self.package_f.parent_id = self.package_b

        apply_qty = 1
        quant1 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_c.id)
        quant2 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_d.id)
        quant3 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_e.id)
        quant4 = self.create_quant(self.apple.id, self.test_location_01.id,
                                   apply_qty, package_id=self.package_f.id)

        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, apply_qty * 3, picking)
        picking.action_confirm()
        move_line_vals = [{'picking_id': picking.id,
                           'package_id': self.package_c.id,
                           'result_package_id': self.package_c.id},
                          {'picking_id': picking.id,
                           'package_id': self.package_d.id,
                           'result_package_id': self.package_d.id},
                          {'picking_id': picking.id,
                           'package_id': self.package_e.id,
                           'result_package_id': self.package_e.id}
                          ]
        move_lines = [self.create_move_line(move, apply_qty, **vals) for vals in move_line_vals]
        lines = move_lines[0] + move_lines[1] + move_lines[2]
        lines.construct_package_hierarchy_links()
        unlinks = PackageHierarchyLink.search([('parent_id', '=', False)])
        children = unlinks.child_id
        self.assertEqual(len(unlinks), 2)
        self.assertEqual(self.package_a + self.package_e, children)

    def test_return_chains(self):
        """Tests that chains are constructed correctly."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package_b.parent_id = False
        self.package_c.parent_id = False
        self.package_d.parent_id = False
        vals = [
            {"parent_id": self.package_a.id, "child_id": self.package_b.id},
            {"parent_id": self.package_b.id, "child_id": self.package_c.id},
        ]
        links = PackageHierarchyLink.create(vals)
        returned_chain = links._return_chains()
        expected_chain = [[self.package_c, self.package_b, self.package_a]]
        self.assertEqual(returned_chain, expected_chain)

    def test_return_chains_unlink(self):
        """Tests that no chains are construced for a unconnected unlink."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        vals = [
            {"parent_id": False, "child_id": self.package_b.id},
        ]
        links = PackageHierarchyLink.create(vals)
        returned_chains = links._return_chains()
        expected_chains = []
        self.assertEqual(returned_chains, expected_chains)

    def test_return_chains_self_ancestor(self):
        """Tests that self ancestors are caught when constructing chains."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package_b.parent_id = False
        self.package_c.parent_id = False
        # Need to create invalid links in 2 parts or they will (correctly)
        # raise validation errors on creation.
        vals = [
            {"parent_id": self.package_a.id, "child_id": self.package_b.id},
            {"parent_id": self.package_b.id, "child_id": self.package_c.id},
        ]
        links = PackageHierarchyLink.create(vals)
        loop_link = PackageHierarchyLink.create({"parent_id": self.package_c.id,
                                                 "child_id": self.package_a.id})
        combined_links = links + loop_link
        with self.assertRaises(ValidationError):
            combined_links._return_chains()

    def test_return_chains_maximum_length(self):
        """Tests that we cannot construct chains that are longer than the maximum depth"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package_b.parent_id = False
        self.package_c.parent_id = False
        self.package_d.parent_id = False
        # Need to create invalid links in 2 parts or they will (correctly)
        # raise validation errors on creation.
        vals = [
            {"parent_id": self.package_a.id, "child_id": self.package_b.id},
            {"parent_id": self.package_b.id, "child_id": self.package_c.id},
            {"parent_id": self.package_c.id, "child_id": self.package_d.id},
        ]
        links = PackageHierarchyLink.create(vals)
        extra_link = PackageHierarchyLink.create({"parent_id": self.package_c.id,
                                                 "child_id": self.package_a.id})
        combined_links = links + extra_link
        with self.assertRaises(ValidationError):
            combined_links._return_chains()


class TestPackageHierarchyLinksValidation(common.BaseHierarchy):
    """Tests for validation of links."""
    def setUp(self):
        """Set up common prerequisites for testing the validation of links.

        A pallet with a package (package1) is created as well as two loose packages.
        An unlink and a link are created for testing purposes. These are not associated with
        moves/movelines as these are not required for testing the validation.
        """
        super(TestPackageHierarchyLinksValidation, self).setUp()
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.env.user.get_user_warehouse().write({
            'u_max_package_depth': 3,
        })
        Package = self.env['stock.quant.package']
        self.package1 = Package.create({})
        self.package2 = Package.create({})
        self.package3 = Package.create({})
        self.package4 = Package.create({})
        self.pallet = Package.create({})
        apple_qty_per_quant = 10
        self.quant1 = self.create_quant(self.apple.id, self.test_location_01.id,
                                        apple_qty_per_quant, package_id=self.package1.id)
        self.quant2 = self.create_quant(self.apple.id, self.test_location_01.id,
                                        apple_qty_per_quant, package_id=self.package2.id)

        self.package1.parent_id = self.pallet
        self.unlink = PackageHierarchyLink.create({'parent_id': False,
                                                   'child_id': self.package1.id})
        self.link = PackageHierarchyLink.create({'parent_id': self.pallet.id,
                                                 'child_id': self.package2.id})

    def test_validate_links_unlink(self):
        """Test that unlinks are permitted"""
        self.unlink._validate_links()

    def test_validate_links_valid_link(self):
        """Test that valid links are allowed"""
        self.link._validate_links()

    def test_validate_links_multiple_links(self):
        """Test that multiple valid links that do not conflict are allowed"""
        links = self.unlink + self.link
        links._validate_links()

    def test_validate_links_chain_with_unlink(self):
        """Check that a chain with an unlink is allowed."""
        self.link.parent_id = self.unlink.child_id
        links = self.unlink + self.link
        links._validate_links()

    def test_validate_links_same_parent_and_child(self):
        """Test that links with the same parent_id and child_id are not permitted"""
        with self.assertRaises(ValidationError):
            self.link.parent_id = self.link.child_id

    def test_validate_links_self_ancestor(self):
        """"Test that a chain that causes a package to be it's own ancestor is not allowed"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        vals = {
            "parent_id": self.package2.id,
            "child_id": self.pallet.id,
        }
        new_link = PackageHierarchyLink.create(vals)
        links = self.link + new_link
        with self.assertRaises(ValidationError):
            links._validate_links()

    def test_validate_links_no_child(self):
        """Test that a child id has to be present."""
        with self.assertRaises(ValidationError):
            self.link.child_id = False

    def test_validate_links_to_multiple_packages(self):
        """Test that it will not allow links to move packages to multiple different packages."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        vals = [
            {"parent_id": self.pallet.id, "child_id": self.package2.id},
            {"parent_id": self.package3.id, "child_id": self.package2.id},
        ]

        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)

    def test_validate_links_switch_parent(self):
        """Make sure that an unlink and link for the same package is allowed."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        vals = [
            {"parent_id": self.pallet.id, "child_id": self.package2.id},
            {"parent_id": False, "child_id": self.package2.id},
        ]
        links = PackageHierarchyLink.create(vals)
        links._validate_links()

    def test_repeated_links_not_allowed(self):
        """Make sure that repeated links are not allowed"""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        n_repeats = 2
        vals = [
            {"parent_id": self.pallet.id, "child_id": self.package2.id}
            for i in range(n_repeats)
        ]
        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)

    def test_validate_links_maximum_length(self):
        """Make sure that links do not result in exceeding maximum depth."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package1.parent_id = False
        vals = [
            {"parent_id": self.pallet.id, "child_id": self.package1.id},
            {"parent_id": self.package1.id, "child_id": self.package2.id},
            {"parent_id": self.package2.id, "child_id": self.package3.id},
        ]
        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)

    def test_validate_links_maximum_length_existing_hierarchy(self):
        """Make sure that links do not result in exceeding maximum depth
        with existing hierarchy.
        """
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package1.parent_id = self.pallet
        self.package2.parent_id = self.package1
        vals = [
            {"parent_id": self.package2.id, "child_id": self.package3.id},
        ]
        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)

    def test_validate_links_maximum_length_existing_hierarchy_not_terminal(self):
        """Make sure that links do not result in exceeding maximum depth
        with existing hierarchy when the violating link is not to the terminal child.
        - Depth will be exceeded by pallet > package1 > package2 > package3
        - Chain that will be checked is pallet > package1 > package4
        - Check that it still checks for this violation.
        """
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package1.parent_id = False
        self.package2.parent_id = self.package1
        self.package3.parent_id = self.package2
        vals = [
            {"parent_id": self.package1.id, "child_id": self.package4.id},
            {"parent_id": self.pallet.id, "child_id": self.package1.id},
        ]
        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)

    def test_validate_links_self_ancestor_existing_hierarchy(self):
        """Make sure that links do not cause self-ancestors with existing hierarchy."""
        PackageHierarchyLink = self.env["package.hierarchy.link"]
        self.package1.parent_id = self.pallet
        vals = [
            {"parent_id": self.package1.id, "child_id": self.pallet.id},
        ]
        with self.assertRaises(ValidationError):
            PackageHierarchyLink.create(vals)
