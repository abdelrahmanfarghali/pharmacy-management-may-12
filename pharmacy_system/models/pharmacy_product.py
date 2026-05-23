from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class PharmacyProduct(models.Model):
    _inherit = 'product.template'
    _description = 'Pharmacy Product'

    medicine_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Medicine Category',
        compute='_compute_medicine_category_id',
        inverse='_inverse_medicine_category_id',
        store=True,
        ondelete='restrict',
        tracking=True,
        help='Select specific medicine sub-category.',
    )

    medicine_category_display = fields.Char(
        string='Category Path',
        compute='_compute_medicine_category_display',
        store=False,
    )

    def _get_medicine_category_domain(self):
        """
        Returns domain filtering only direct children of the root
        'Medicine' category. Fails gracefully if the ref is missing
        (e.g. module partially installed or demo data not loaded).
        """
        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        if not root:
            return []  # Degrade gracefully — show all categories
        return [('parent_id', '=', root.id)]

    @api.depends('medicine_category_id.complete_name')
    def _compute_medicine_category_display(self):
        for record in self:
            cat = record.medicine_category_id
            if cat:
                record.medicine_category_display = cat.complete_name  # e.g. "Medicine / OTC"
            else:
                record.medicine_category_display = False

    @api.constrains('medicine_category_id', 'categ_id', 'is_medicine')
    def _check_medicine_category(self):
        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        if not root:
            return

        for record in self:
            if record.is_medicine:
                if not record.categ_id:
                    raise ValidationError(_("A medicine product must have a product category."))
                
                # Check if categ_id is child of root (using child_of)
                is_valid_categ = record.categ_id.id == root.id or record.env['product.category'].search_count([
                    ('id', '=', record.categ_id.id),
                    ('id', 'child_of', root.id),
                ])
                if not is_valid_categ:
                    raise ValidationError(_(
                        "Product category '%s' must be under the Medicine category hierarchy."
                    ) % record.categ_id.name)

            if record.medicine_category_id:
                if record.medicine_category_id.id == root.id:
                    raise ValidationError(_("Please select a sub-category under Medicine, not the root."))
                
                is_valid = record.env['product.category'].search_count([
                    ('id', '=', record.medicine_category_id.id),
                    ('id', 'child_of', root.id),
                ])
                if not is_valid:
                    raise ValidationError(_(
                        "Medicine sub-category '%s' is not under the Medicine category."
                    ) % record.medicine_category_id.name)

    @api.depends('categ_id')
    def _compute_medicine_category_id(self):
        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        if not root:
            for record in self:
                record.medicine_category_id = False
            return

        # Optimization: Map all unique categ_ids to check their subcategory status in a single query
        categ_ids = self.mapped('categ_id').filtered(bool)
        medicine_children = self.env['product.category'].search([
            ('id', 'in', categ_ids.ids),
            ('id', 'child_of', root.id),
            ('id', '!=', root.id),
        ])
        medicine_child_ids = set(medicine_children.ids)

        for record in self:
            if record.categ_id.id in medicine_child_ids:
                record.medicine_category_id = record.categ_id
            else:
                record.medicine_category_id = False

    def _inverse_medicine_category_id(self):
        """Allow manual set of medicine_category_id to update categ_id."""
        if self.env.context.get('skip_inverse'):
            return
        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        for record in self:
            if record.medicine_category_id:
                record.with_context(skip_inverse=True).categ_id = record.medicine_category_id
            elif record.is_medicine and root:
                # If cleared, revert product category to the root Medicine category
                record.with_context(skip_inverse=True).categ_id = root

    @api.onchange('medicine_category_id')
    def _onchange_medicine_category_id(self):
        if not self.medicine_category_id:
            return

        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        if not root:
            return

        if self.medicine_category_id.id == root.id:
            self.medicine_category_id = False
            return {
                'warning': {
                    'title': _('Select a Sub-category'),
                    'message': _('Please select a specific sub-category under Medicine, not the root.'),
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        for vals in vals_list:
            if vals.get('is_medicine'):
                # Determine what category to use
                target_categ = vals.get('medicine_category_id') or vals.get('categ_id')
                
                # Check if target_categ is valid (i.e. under Medicine root)
                is_valid = False
                if target_categ:
                    category = self.env['product.category'].browse(target_categ)
                    if category.exists():
                        is_valid = category.id == root.id or self.env['product.category'].search_count([
                            ('id', '=', category.id),
                            ('id', 'child_of', root.id),
                        ])
                
                if not is_valid and root:
                    # Default to root Medicine category
                    vals['categ_id'] = root.id
                    if 'medicine_category_id' not in vals:
                        vals['medicine_category_id'] = False
                elif is_valid:
                    # Sync them
                    if vals.get('medicine_category_id') and not vals.get('categ_id'):
                        vals['categ_id'] = vals['medicine_category_id']
                    elif vals.get('categ_id') and not vals.get('medicine_category_id') and vals['categ_id'] != root.id:
                        vals['medicine_category_id'] = vals['categ_id']
        records = super(PharmacyProduct, self.with_context(skip_inverse=True)).create(vals_list)
        return records.with_env(self.env)

    def write(self, vals):
        if self.env.context.get('skip_inverse'):
            return super(PharmacyProduct, self).write(vals)

        root = self.env.ref(
            'pharmacy_system.product_category_medicine',
            raise_if_not_found=False
        )
        
        # If is_medicine is being enabled, or categ_id / medicine_category_id are changing
        if 'is_medicine' in vals or 'categ_id' in vals or 'medicine_category_id' in vals:
            for record in self:
                is_med = vals.get('is_medicine', record.is_medicine)
                if is_med:
                    # Sync medicine_category_id -> categ_id
                    if 'medicine_category_id' in vals and 'categ_id' not in vals:
                        if vals['medicine_category_id']:
                            vals['categ_id'] = vals['medicine_category_id']
                        elif root:
                            vals['categ_id'] = root.id
                    
                    # Sync categ_id -> medicine_category_id
                    elif 'categ_id' in vals and 'medicine_category_id' not in vals:
                        if root and vals['categ_id'] != root.id:
                            # Verify it is child of root
                            is_child = self.env['product.category'].search_count([
                                ('id', '=', vals['categ_id']),
                                ('id', 'child_of', root.id),
                            ])
                            if is_child:
                                vals['medicine_category_id'] = vals['categ_id']
                            else:
                                vals['medicine_category_id'] = False
                        else:
                            vals['medicine_category_id'] = False
                            
        return super(PharmacyProduct, self.with_context(skip_inverse=True)).write(vals)