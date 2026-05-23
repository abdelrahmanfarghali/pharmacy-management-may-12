# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestPharmacyCategorySync(TransactionCase):

    def setUp(self):
        super(TestPharmacyCategorySync, self).setUp()
        self.root_categ = self.env.ref('pharmacy_system.product_category_medicine')
        self.otc_categ = self.env.ref('pharmacy_system.product_category_medicine_otc')
        
        # Create a non-medicine category for testing constraints
        self.non_med_categ = self.env['product.category'].create({
            'name': 'Test Non-Medicine Category',
        })

    def test_medicine_category_sync_from_categ_id(self):
        """Test that setting a sub-category under Medicine on categ_id automatically syncs to medicine_category_id."""
        product = self.env['product.template'].create({
            'name': 'Test Paracetamol',
            'is_medicine': True,
            'categ_id': self.otc_categ.id,
        })
        self.assertEqual(product.medicine_category_id, self.otc_categ, "medicine_category_id did not sync from categ_id!")
        self.assertEqual(product.medicine_category_display, self.otc_categ.complete_name, "Category display mismatch!")

    def test_medicine_category_sync_from_medicine_category_id(self):
        """Test that setting medicine_category_id automatically syncs to categ_id."""
        product = self.env['product.template'].create({
            'name': 'Test Paracetamol',
            'is_medicine': True,
            'medicine_category_id': self.otc_categ.id,
        })
        self.assertEqual(product.categ_id, self.otc_categ, "categ_id did not sync from medicine_category_id!")

    def test_medicine_category_clearing(self):
        """Test that clearing medicine_category_id resets categ_id to root Medicine category."""
        product = self.env['product.template'].create({
            'name': 'Test Aspirin',
            'is_medicine': True,
            'medicine_category_id': self.otc_categ.id,
        })
        self.assertEqual(product.categ_id, self.otc_categ)
        
        # Clear medicine_category_id
        product.medicine_category_id = False
        
        # Verify categ_id reverted to root Medicine category
        self.assertEqual(product.categ_id, self.root_categ, "categ_id did not revert to root Medicine category on clearing medicine_category_id!")

    def test_medicine_category_constraint_valid_non_med(self):
        """Test that is_medicine=True blocks non-medicine category assignment."""
        product = self.env['product.template'].create({
            'name': 'Valid Medicine Product',
            'is_medicine': True,
            'categ_id': self.otc_categ.id,
        })
        
        with self.assertRaises(ValidationError):
            product.categ_id = self.non_med_categ

    def test_medicine_category_constraint_root_avoid(self):
        """Test that choosing root Medicine category in medicine_category_id raises ValidationError."""
        product = self.env['product.template'].create({
            'name': 'Valid Medicine Product',
            'is_medicine': True,
            'categ_id': self.otc_categ.id,
        })
        
        with self.assertRaises(ValidationError):
            product.medicine_category_id = self.root_categ
