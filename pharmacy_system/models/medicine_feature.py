from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class MedicineFeature(models.Model):
    _inherit = "product.template"

    is_medicine = fields.Boolean(
        string='Is Medicine',
        store=True
    )

    max_qty_per_invoice = fields.Float(
        string='Max Quantity per Invoice',
        digits=(16, 2),
        default=0.0,
        help='Maximum quantity of this medicine that can be sold in a single transaction.'
    )

    @api.onchange('is_medicine')
    def _onchange_is_medicine(self):
        if self.is_medicine:
            # Enable availability in Point of Sale and set POS category
            self.available_in_pos = True
            pos_categ = self.env['pos.category'].search([('name', '=', 'Medicine')], limit=1)
            if not pos_categ:
                pos_categ = self.env['pos.category'].create({'name': 'Medicine'})
            if pos_categ and pos_categ.id not in self.pos_categ_ids.ids:
                self.pos_categ_ids = [(4, pos_categ.id)]

            # Dynamically set category to 'Medicine' if found
            medicine_categ = self.env.ref('pharmacy_system.product_category_medicine', raise_if_not_found=False)
            if not medicine_categ:
                medicine_categ = self.env['product.category'].search([('name', '=', 'Medicine')], limit=1)
            
            if medicine_categ:
                self.categ_id = medicine_categ.id
            
            # Return dynamic domain to restrict category to Medicine
            if medicine_categ:
                return {'domain': {'categ_id': [('id', '=', medicine_categ.id)]}}
        else:
            self.max_qty_per_invoice = 0.0
            
            # Reset category to default 'All'
            default_categ = self.env.ref('product.product_category_all', raise_if_not_found=False)
            if not default_categ:
                default_categ = self.env['product.category'].search([('name', '=', 'All')], limit=1)
            if default_categ:
                self.categ_id = default_categ.id
                
            # Remove domain restriction
            return {'domain': {'categ_id': []}}

    @api.constrains('max_qty_per_invoice')
    def _check_max_qty_per_invoice_positive(self):
        for rec in self:
            if rec.max_qty_per_invoice < 0:
                raise ValidationError(
                    _('Max Qty per Invoice cannot be negative for product "%s". '
                      'Use 0 to disable the restriction.') % rec.name
                )

    def init(self):
        super().init()
        # Ensure all existing and new template records have a default value of 0.0 instead of NULL
        self.env.cr.execute("""
            UPDATE product_template 
            SET max_qty_per_invoice = 0.0 
            WHERE max_qty_per_invoice IS NULL
        """)


class MaxQtyLog(models.Model):
    _name = 'max.qty.log'
    _description = 'Max Quantity'

    user_id = fields.Many2one('res.users', string="User")
    product_id = fields.Many2one('product.template', string="Product")
    attempted_qty = fields.Float("Attempted Qty")
    allowed_qty = fields.Float("Allowed Qty")
    date = fields.Datetime("Date", default=fields.Datetime.now)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('product_uom_qty', 'product_id')
    def _check_max_qty_limit(self):
        for line in self:
            if line.product_id and line.product_id.is_medicine:
                limit = line.product_id.max_qty_per_invoice
                if limit > 0:
                    # Convert selected UoM quantity to the product's reference UoM to ensure correct UoM limits
                    qty_in_product_uom = line.product_uom._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
                    if qty_in_product_uom > limit:
                        raise ValidationError(_(
                            "Cannot sell more than the maximum limit of %s %s for medicine '%s' (Requested: %s %s). "
                            "This limit is strictly enforced for all transactions."
                        ) % (limit, line.product_id.uom_id.name, line.product_id.name, line.product_uom_qty, line.product_uom.name))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('quantity', 'product_id')
    def _check_max_qty_limit(self):
        for line in self:
            # Enforce on customer invoices/refunds
            if line.move_id.move_type in ('out_invoice', 'out_refund') and line.product_id and line.product_id.is_medicine:
                limit = line.product_id.max_qty_per_invoice
                if limit > 0:
                    qty_in_product_uom = line.product_uom._compute_quantity(line.quantity, line.product_id.uom_id)
                    if qty_in_product_uom > limit:
                        raise ValidationError(_(
                            "Cannot invoice more than the maximum limit of %s %s for medicine '%s' (Requested: %s %s). "
                            "This limit is strictly enforced for all invoices."
                        ) % (limit, line.product_id.uom_id.name, line.product_id.name, line.quantity, line.product_uom.name))


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.constrains('qty', 'product_id')
    def _check_max_qty_limit(self):
        for line in self:
            if line.product_id and line.product_id.is_medicine:
                limit = line.product_id.max_qty_per_invoice
                if limit > 0:
                    qty_in_product_uom = line.product_uom._compute_quantity(line.qty, line.product_id.uom_id)
                    if qty_in_product_uom > limit:
                        raise ValidationError(_(
                            "Cannot sell more than the maximum limit of %s %s in Point of Sale for medicine '%s' (Requested: %s %s). "
                            "This limit is strictly enforced for all transactions."
                        ) % (limit, line.product_id.uom_id.name, line.product_id.name, line.qty, line.product_uom.name))


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.constrains('product_uom_qty', 'product_id')
    def _check_max_qty_limit(self):
        for move in self:
            # Enforce limit on outgoing inventory movements (customer deliveries)
            if move.picking_id and move.picking_id.picking_type_code == 'outgoing' and move.product_id and move.product_id.is_medicine:
                limit = move.product_id.max_qty_per_invoice
                if limit > 0:
                    qty_in_product_uom = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
                    if qty_in_product_uom > limit:
                        raise ValidationError(_(
                            "Cannot process stock delivery of more than the maximum limit of %s %s for medicine '%s' (Requested: %s %s)."
                        ) % (limit, move.product_id.uom_id.name, move.product_id.name, move.product_uom_qty, move.product_uom.name))



class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def action_open_pos_medicine(self):
        # 1. Find or dynamically create standard POS category 'Medicine'
        pos_categ = self.env['pos.category'].search([('name', '=', 'Medicine')], limit=1)
        if not pos_categ:
            pos_categ = self.env['pos.category'].create({'name': 'Medicine'})

        # 2. Automatically link all Medicine products to the Medicine POS category and make them available in POS
        medicines = self.env['product.template'].search([('is_medicine', '=', True)])
        for product in medicines:
            vals = {}
            if pos_categ.id not in product.pos_categ_ids.ids:
                vals['pos_categ_ids'] = [(4, pos_categ.id)]
            if not product.available_in_pos:
                vals['available_in_pos'] = True
            if vals:
                product.write(vals)

        # 3. Find default/active POS configuration and configure it for Medicine
        config = self.env['pos.config'].search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.env['pos.config'].search([], limit=1)

        if not config:
            # Dynamically create a brand new POS config called "Pharmacy" to make it work instantly
            create_vals = {
                'name': 'Pharmacy',
            }
            # Add default picking type if available to comply with Odoo's required fields
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', self.env.company.id)
            ], limit=1)
            if picking_type:
                create_vals['picking_type_id'] = picking_type.id
            config = self.env['pos.config'].create(create_vals)

        if config:
            config.write({
                'limit_categories': True,
                'iface_available_categ_ids': [(6, 0, [pos_categ.id])],
            })
            return config.open_ui()

    def init(self):
        super().init()
        # Find or programmatically create/update the server action record during init
        # so it is registered before XML data files are parsed!
        xmlid_data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pharmacy_system_programmatic'),
            ('name', '=', 'ui_pos_config')
        ], limit=1)
        
        vals = {
            'name': 'POS Cashier UI',
            'model_id': self.env['ir.model'].sudo()._get('pos.config').id,
            'state': 'code',
            'code': "action = env['pos.config'].action_open_pos_medicine()",
        }
        
        if xmlid_data:
            action = self.env['ir.actions.server'].sudo().browse(xmlid_data.res_id)
            if action.exists():
                action.write(vals)
            else:
                action = self.env['ir.actions.server'].sudo().create(vals)
                xmlid_data.write({'res_id': action.id})
        else:
            action = self.env['ir.actions.server'].sudo().create(vals)
            self.env['ir.model.data'].sudo().create({
                'module': 'pharmacy_system_programmatic',
                'name': 'ui_pos_config',
                'model': 'ir.actions.server',
                'res_id': action.id,
                'noupdate': False,
            })