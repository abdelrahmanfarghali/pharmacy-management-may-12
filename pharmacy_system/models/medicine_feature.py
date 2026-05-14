from odoo import api, fields,models

class MedicineFeature(models.Model):
    _inherit="product.template"
    
    classification=fields.Selection(
        [('is_medicine','Medicine'),
        ('not_medicine','Not Medicine')]
        ,default="is_medicine")