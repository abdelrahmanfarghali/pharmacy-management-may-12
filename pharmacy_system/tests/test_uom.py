# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestPharmacyUom(TransactionCase):

    def setUp(self):
        super(TestPharmacyUom, self).setUp()
        self.unit_categ = self.env.ref('uom.product_uom_categ_unit', raise_if_not_found=False)
        if not self.unit_categ:
            self.unit_categ = self.env['uom.category'].search([('name', 'ilike', 'Unit')], limit=1)

    def test_package_uom_creation(self):
        """Test that when a box package product template is created, 
        its UoM is created using the mathematically correct stored 'factor' 
        and standard 'rounding=0.01', and is correctly assigned."""
        
        # Define target box size
        units_per_box = 12
        uom_name = f"Box of {units_per_box} TEST"
        
        # Clean up any prior test UoMs
        existing = self.env['uom.uom'].search([
            ('name', '=', uom_name),
            ('category_id', '=', self.unit_categ.id)
        ])
        if existing:
            existing.unlink()

        # Create a new product template
        product_tmpl = self.env['product.template'].create({
            'name': 'Test Medicine Box Product',
            'pharmacy_product_type': 'package',
            'units_per_package': units_per_box,
            'list_price': 120.0,
        })
        
        # Trigger the UoM computation onchange manually
        product_tmpl._onchange_auto_create_uom()
        
        # Verify the UoM was created and is set on the template
        created_uom = product_tmpl.uom_id
        self.assertTrue(created_uom, "UoM should have been successfully created and set!")
        self.assertEqual(created_uom.name, f"Box of {units_per_box}")
        
        # Verify the stored database values
        expected_factor = 1.0 / units_per_box
        self.assertAlmostEqual(created_uom.factor, expected_factor, places=7, msg="Stored factor mismatch!")
        self.assertEqual(created_uom.rounding, 0.01, "Stored rounding mismatch!")
        
        # Verify the Odoo computed value
        self.assertAlmostEqual(created_uom.factor_inv, float(units_per_box), places=7, msg="Computed factor_inv mismatch!")
