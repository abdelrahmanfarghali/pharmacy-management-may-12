from odoo import models, fields, api, _

class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_all_barcodes = fields.Boolean(
        string="Print All Product Barcodes",
        default=False,
        help="If checked, prints all barcodes associated with the pharmacy medicine list."
    )

    is_medicine = fields.Boolean(
        string="Is Medicine",
        compute="_compute_is_medicine",
        store=False,
    )

    @api.depends('product_tmpl_ids.is_medicine', 'product_ids.is_medicine')
    def _compute_is_medicine(self):
        for rec in self:
            tmpl_med = any(rec.product_tmpl_ids.mapped('is_medicine'))
            prod_med = any(rec.product_ids.mapped('is_medicine'))
            rec.is_medicine = tmpl_med or prod_med

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        
        if self.print_all_barcodes:
            custom_barcodes = {}
            active_model = data.get('active_model')
            seen_barcodes = set()
            
            # Helper to gather unique SECONDARY barcodes for a product
            def get_secondary_uniques(item):
                res = []
                # Record the primary barcode so we don't repeat it in secondary lines
                primary_barcode = item.barcode
                if primary_barcode:
                    seen_barcodes.add(primary_barcode)
                
                tmpl = item if active_model == 'product.template' else item.product_tmpl_id
                for line in tmpl.barcode_line_ids:
                    if line.barcode and line.barcode not in seen_barcodes:
                        res.append((line.barcode, 1))
                        seen_barcodes.add(line.barcode)
                return res

            if active_model == 'product.template':
                for tmpl in self.product_tmpl_ids:
                    barcodes = get_secondary_uniques(tmpl)
                    if barcodes:
                        custom_barcodes[str(tmpl.id)] = barcodes
            elif active_model == 'product.product':
                for product in self.product_ids:
                    barcodes = get_secondary_uniques(product)
                    if barcodes:
                        custom_barcodes[str(product.id)] = barcodes
            
            if custom_barcodes:
                data['custom_barcodes'] = custom_barcodes
                
            # To print the primary barcode exactly once, we set its qty to 1.
            # We must NOT set it to 0 because Odoo 18's sheet report has a bug 
            # where qty 0 causes an infinite loop (-1, -2...) that fills the page.
            if 'quantity_by_product' in data:
                for product_id in data['quantity_by_product']:
                    data['quantity_by_product'][product_id] = 1

            # Recalculate total for page numbers
            total = len(seen_barcodes)
            if self.rows and self.columns:
                data['page_numbers'] = (total - 1) // (self.rows * self.columns) + 1

        return xml_id, data
