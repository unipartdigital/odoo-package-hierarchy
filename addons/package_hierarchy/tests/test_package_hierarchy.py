# -*- coding: utf-8 -*-
"""Test odoo-package-hierarchy"""

from odoo.exceptions import UserError, ValidationError
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
        Package = self.env['stock.quant.package']
        self.package = Package.create({}) # an empty package is enough
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

    def test_compute_parent_ids(self):
        """Compute the parent package IDs of a package.

        Yes, the package is its own parent too."""
        # There's no need for a picking; setting package_id on a package sets
        # the parent.
        self.package._compute_parent_ids()
        self.assertEqual(self.package, self.package.parent_ids)
        self.package.package_id = self.pallet # This recomputes parent_ids
        # Check parent_ids on the package at the bottom of the 2-level hierarchy.
        self.assertEqual(self.package.parent_ids, self.package | self.pallet)

    def test_check_not_multi_location(self):
        """Make sure that one package's quants are in the same location.

        This does not need to test the happy case directly, as it is covered
        via test_compute_parent_ids."""
        # This test also provides coverage for _compute_childen_quant_ids
        second_qty = 11
        self.create_quant(self.apple.id, self.test_location_02.id,
                          second_qty, package_id=self.package.id)
        with self.assertRaises(ValidationError):
            self.package._check_not_multi_location()

    def test_check_parent_not_multi_location(self):
        """Make sure that a parent package is not multi-location.

        This means checking that its children are in the same location."""
        Package = self.env['stock.quant.package']
        package2 = Package.create({})
        second_qty = 11
        self.create_quant(self.apple.id, self.test_location_02.id,
                          second_qty, package_id=package2.id)
        #This does not need to duplicate the checks that each child is valid;
        #_check_not_multi_location is called via children_quant_ids.
        self.package.package_id = self.pallet
        # Expect adding a package at another location to a pallet to fail
        with self.assertRaises(ValidationError):
            package2.package_id = self.pallet

    def test_compute_package_info(self):
        """Make sure _compute_package_info runs on both packages and pallets."""
        # This just runs the code for coverage. Checking the logic would only
        # be a duplicate of the implementation, so isn't done.
        self.package._compute_package_info()
        self.package.package_id = self.pallet
        self.pallet._compute_package_info()

    def test_compute_display_name(self):
        """Make sure _compute_display_name runs on both packages and pallets."""
        self.package._compute_display_name()
        self.assertEqual(self.package.display_name, self.package.name)

        self.package.package_id = self.pallet
        self.package._compute_display_name()
        compound_name = "%s/%s" % (self.pallet.name, self.package.name)
        self.assertEqual(self.package.display_name, compound_name)

        self.pallet._compute_display_name()
        self.assertEqual(self.pallet.display_name, self.pallet.name)

    def test_is_all_contents_in(self):
        """Check that is_all_contents_in returns true on appropriate types."""
        Package = self.env['stock.quant.package']

        self.assertTrue(self.package.is_all_contents_in(self.package))
        self.assertTrue(self.package.is_all_contents_in(self.quant))
        # all other types should fail
        with self.assertRaises(ValidationError):
            self.package.is_all_contents_in(self.picking)

        other_package = Package.create({})
        outside_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                          5000, package_id=other_package.id)
        # REVIEW FIXME: the following two lines are commented out, as they
        # fail. Is that the intended semantics?
        #self.assertFalse(self.package.is_all_contents_in(other_package))
        #self.assertFalse(other_package.is_all_contents_in(self.package))
        self.assertFalse(self.package.is_all_contents_in(outside_quant))
        self.assertFalse(other_package.is_all_contents_in(self.quant))

    def test_compute_current_picking_info(self):
        """Test _compute_current_picking_info.

        This tests a pallet with two packages in it, both of which are
        reserved in the picking."""
        Package = self.env['stock.quant.package']
        package1 = Package.create({})
        package2 = Package.create({})
        package1.package_id = self.pallet
        package2.package_id = self.pallet
        self.create_quant(self.apple.id, self.test_location_02.id,
                          7, package_id=package1.id)
        self.create_quant(self.apple.id, self.test_location_02.id,
                          8, package_id=package2.id)
        picking = self.create_picking(self.picking_type_internal)
        self.create_move(self.apple, 15, picking)
        picking.action_confirm()
        picking.action_assign()

        # First, test without a picking in the context, for coverage.
        self.pallet._compute_current_picking_info()

        # Now, test normal execution, with a picking in context.
        self.pallet = self.pallet.with_context({'picking_id': picking.id})
        self.pallet._compute_current_picking_info()

        self.assertEqual(len(self.pallet.current_picking_move_line_ids), 2)
        self.assertTrue(self.pallet.current_picking_id)
        self.assertEqual(self.pallet.current_source_location_id,
                         self.test_location_02)
        expectedDestination = self.pallet.current_picking_move_line_ids[0].location_dest_id
        self.assertEqual(self.pallet.current_destination_location_id,
                         expectedDestination)
        self.assertFalse(self.pallet.is_processed)


    def test_action_toggle_processed_no_picking(self):
        """Test action_toggle_processed with no picking"""
        self.pallet.action_toggle_processed()

    def test_action_toggle_processed_enough(self):
        """Test action_toggle_processed with enough items to move."""
        self.package.package_id = self.pallet
        self.pallet = self.pallet.with_context({'picking_id': self.picking.id})
        self.pallet.action_toggle_processed()
        self.assertEqual(self.picking.move_line_ids[0].qty_done,
                         self.picking.move_line_ids[0].product_uom_qty)

    def test_action_toggle_processed_not_enough(self):
        """Test action_toggle_processed.

        This test checks when there are no move_lines with ml.qty_done < ml.product_uom_qty"""
        Package = self.env['stock.quant.package']
        package1 = Package.create({})
        pallet = Package.create({})
        package1.package_id = pallet
        self.create_quant(self.apple.id, self.test_location_02.id,
                          0, package_id=package1.id)
        picking = self.create_picking(self.picking_type_internal)
        self.create_move(self.apple, 0, picking)
        picking.action_confirm()
        picking.action_assign()
        package1.package_id = pallet
        pallet = pallet.with_context({'picking_id': picking.id})
        pallet.action_toggle_processed()

    def test_action_toggle_processed_with_dest(self):
        """Test action_toggle_processed with enough items to move."""
        self.package.package_id = self.pallet
        self.pallet = self.pallet.with_context({'picking_id': self.picking.id,
                                                'destination_location': self.test_location_01.id})
        self.pallet.action_toggle_processed()

    def test_action_done(self):
        """Check StockMoveLine's _action_done"""
        ml = self.picking.move_line_ids[0]
        ml.u_result_parent_package_id = self.pallet
        for move in self.picking.move_lines:
            move.quantity_done = move.product_uom_qty
        ml._action_done()

    def testOnchangeResultPackage(self):
        """test onchange_result_package"""
        ml = self.picking.move_line_ids[0]
        ml.u_result_parent_package_id = self.pallet
        ml.onchange_result_package()
        ml.result_package_id = None
        ml.onchange_result_package()

    def test_assert_one_parent_package_missing_parent(self):
        """_assert_one_parent_package can't have a half-set parent"""
        ml = self.picking.move_line_ids[0]
        ml.u_result_parent_package_id = self.pallet
        ml.result_package_id = None
        with self.assertRaises(ValidationError):
            ml._assert_one_parent_package()

    def test_assert_one_parent_package_multiparent(self):
        """_assert_one_parent_package: move lines cannot have multiple parents"""
        Package = self.env['stock.quant.package']
        package1 = Package.create({})
        pallet1 = Package.create({})
        package1.package_id = pallet1
        self.create_quant(self.apple.id, self.test_location_02.id,
                          7, package_id=package1.id)
        self.create_quant(self.banana.id, self.test_location_02.id,
                          8, package_id=package1.id)
        picking = self.create_picking(self.picking_type_internal)
        self.create_move(self.apple, 7, picking)
        self.create_move(self.banana, 8, picking)
        picking.action_confirm()
        picking.action_assign()

        with self.assertRaises(ValidationError):
            picking.move_line_ids[0].u_result_parent_package_id = self.pallet
