from odoo import api, fields, models

class MedicineFeature(models.Model):
    _inherit = "product.template"

    is_medicine = fields.Boolean(
        string='Is Medicine',
        store=True
    )

    commission = fields.Float(
        string='Commission (%)',
        digits=(16, 2),
        default=0.0,
        help='Commission percentage for medicine products.'
    )

    @api.onchange('is_medicine')
    def _onchange_is_medicine(self):
        if self.is_medicine:
            # Dynamically set category to 'Medicine' if found
            medicine_categ = self.env.ref('pharmacy_system.product_category_medicine', raise_if_not_found=False)
            if not medicine_categ:
                medicine_categ = self.env['product.category'].search([('name', '=', 'Medicine')], limit=1)
            
            if medicine_categ:
                self.categ_id = medicine_categ.id
            
            # Set default commission to 10%
            self.commission = 10.0
            
            # Return dynamic domain to restrict category to Medicine
            if medicine_categ:
                return {'domain': {'categ_id': [('id', '=', medicine_categ.id)]}}
        else:
            # Clear commission
            self.commission = 0.0
            
            # Reset category to default 'All'
            default_categ = self.env.ref('product.product_category_all', raise_if_not_found=False)
            if not default_categ:
                default_categ = self.env['product.category'].search([('name', '=', 'All')], limit=1)
            if default_categ:
                self.categ_id = default_categ.id
                
            # Remove domain restriction
            return {'domain': {'categ_id': []}}