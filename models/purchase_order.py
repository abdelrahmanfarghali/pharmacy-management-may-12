# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_consignment = fields.Boolean(
        string='Consignment (التصريف تحت بضاعة)',
        default=False,
        copy=False,
        tracking=True,
    )

    consignment_banner_visible = fields.Boolean(
        compute='_compute_consignment_banner_visible',
        store=False,
    )

    @api.depends('is_consignment')
    def _compute_consignment_banner_visible(self):
        for rec in self:
            rec.consignment_banner_visible = rec.is_consignment

    def write(self, vals):
        if 'is_consignment' in vals:
            for rec in self:
                if rec.state in ('purchase', 'done'):
                    raise UserError(
                        _('The Consignment flag cannot be changed after the PO is confirmed.')
                    )
        result = super().write(vals)
        if 'is_consignment' in vals:
            for rec in self:
                if vals['is_consignment']:
                    msg = _('PO marked as <b>Consignment (التصريف تحت بضاعة)</b> by %s on %s.') % (
                        self.env.user.name, fields.Date.today(),
                    )
                else:
                    msg = _('Consignment flag <b>removed</b> by %s on %s.') % (
                        self.env.user.name, fields.Date.today(),
                    )
                rec.message_post(body=msg)
        return result

    def action_track_consignment_stock(self):
        self.ensure_one()
        if not self.is_consignment:
            raise UserError(_('Track Stock is only available for Consignment POs.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Track Stock — التصريف تحت بضاعة'),
            'res_model': 'consignment.track.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'dialog_size': 'large',
            },
        }

    def _log_consignment_return(self, picking_ref):
        self.ensure_one()
        msg = _('Return transfer <b>%s</b> created — Remaining Quantity updated.') % picking_ref
        self.message_post(body=msg)

    def order_lines_for_consignment(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: l.product_id and l.state != 'cancel'
        )


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    line_vendor_id = fields.Many2one(
    'res.partner',
    string='Vendor',
    )

    consignment_batch_name = fields.Char(
        string='Batch Reference'
    )
    consignment_payment_ids = fields.One2many(
        'purchase.order.line.consignment.payment',
        'purchase_order_line_id',
        string='Consignment Payments',
    )

    consignment_received_qty = fields.Float(
        string='Received Qty (Consignment)',
        compute='_compute_consignment_quantities',
        digits='Product Unit of Measure',
    )
    consignment_sold_qty = fields.Float(
        string='Sold Qty (Consignment)',
        compute='_compute_consignment_quantities',
        digits='Product Unit of Measure',
    )
    consignment_paid_qty = fields.Float(
        string='Already Paid Qty',
        compute='_compute_consignment_quantities',
        digits='Product Unit of Measure',
    )
    consignment_payable_now = fields.Float(
        string='Payable Now',
        compute='_compute_consignment_quantities',
        digits='Product Unit of Measure',
    )
    # purchase_line_id = fields.Many2one(
    #         'purchase.order.line'
    #     )
    @api.depends(
        'qty_received',
        'product_id',
        'order_id.is_consignment',
        'consignment_payment_ids.already_paid_qty',
    )
    def _compute_consignment_quantities(self):
        for line in self:
            if not line.order_id.is_consignment:
                line.consignment_received_qty = 0.0
                line.consignment_sold_qty = 0.0
                line.consignment_paid_qty = 0.0
                line.consignment_payable_now = 0.0
                continue

            received = line.qty_received
            sold = line._get_sold_qty()
            paid_rec = self.env['purchase.order.line.consignment.payment'].search(
                [('purchase_order_line_id', '=', line.id)], limit=1
            )
            paid = paid_rec.already_paid_qty if paid_rec else 0.0
            payable = max(0.0, sold - paid)

            line.consignment_received_qty = received
            line.consignment_sold_qty = sold
            line.consignment_paid_qty = paid
            line.consignment_payable_now = payable
    def _get_sold_qty(self):
        """
        حساب الكمية المباعة المرتبطة بهذا الـ PO line تحديداً.
        
        الربط الصحيح في Odoo:
        - sale.order.line لها حقل purchase_line_id بيربطها بـ PO line
        - بنفلتر عليه بدل ما نبحث بالمنتج فقط (اللي يخلط vendors)
        """
        self.ensure_one()
        if not self.product_id:
            return 0.0

        po_uom = self.product_uom

        # ── Sale Order lines — مرتبطة بالـ PO line مباشرة ──────────────────
        # purchase_line_id هو native Odoo field موجود في sale.order.line
        
        # so_lines = self.env['sale.order.line'].search([
        #             ('product_id', '=', self.product_id.id),
        #             ('order_id.state', 'in', ('sale', 'done')),
        #         ])
        so_lines = self.env['sale.order.line'].search([
        ('consignment_po_line_id', '=', self.id),
        ('order_id.state', 'in', ('sale', 'done')),
            ])
        _logger.warning(
        "CHECK PO=%s FOUND SO=%s",
        self.id,
        self.env['sale.order.line'].search([
            ('consignment_po_line_id', '=', self.id),
        ]).ids
    )
        so_qty = 0.0
        for sol in so_lines:
            qty = sol.product_uom_qty
            if sol.product_uom and po_uom and sol.product_uom.id != po_uom.id:
                try:
                    qty = sol.product_uom._compute_quantity(qty, po_uom)
                except Exception:
                    pass
            so_qty += qty

        # ── POS lines — POS مافيهاش purchase_line_id، هنفلتر بالمنتج + التاريخ ──
        # بنقيد بتاريخ الاستلام عشان نربطها بالشحنة دي تحديداً
        receipt_date = self._get_receipt_date()
        pos_domain = [
            ('product_id', '=', self.product_id.id),
            ('order_id.state', 'in', ('done', 'invoiced')),
        ]
        if receipt_date:
            pos_domain.append(('order_id.date_order', '>=', receipt_date))

        pos_lines = self.env['pos.order.line'].search(pos_domain)
        pos_qty = 0.0
        for pol in pos_lines:
            qty = pol.qty
            line_uom = getattr(pol, 'product_uom_id', False)
            if line_uom and po_uom and line_uom.id != po_uom.id:
                try:
                    qty = line_uom._compute_quantity(qty, po_uom)
                except Exception:
                    pass
            pos_qty += qty

        total = so_qty + pos_qty

        _logger.info(
            'Consignment sold_qty | product: %s | PO Line: %s | '
            'SO (by purchase_line_id): %s | POS: %s | TOTAL: %s',
            self.product_id.display_name, self.id,
            so_qty, pos_qty, total,
        )
        return total
    # def _get_sold_qty(self):
        
    #     self.ensure_one()
    #     if not self.product_id:
    #         return 0.0

    #     product = self.product_id
    #     po_uom = self.product_uom

    #     # ── Sale Order lines ──────────────────────────────────────────────────
    #     # state 'sale' = confirmed, state 'done' = locked
    #     # بنحسب product_uom_qty مش qty_delivered عشان مش لازم ينتظر الشحن
    #     so_domain = [
    #         ('product_id', '=', product.id),
    #         ('order_id.state', 'in', ('sale', 'done')),
    #     ]

    #     so_lines = self.env['sale.order.line'].search(so_domain)
    #     so_qty = 0.0
    #     for sol in so_lines:
    #         qty = sol.product_uom_qty
    #         line_uom = sol.product_uom
    #         if line_uom and po_uom and line_uom.id != po_uom.id:
    #             try:
    #                 qty = line_uom._compute_quantity(qty, po_uom)
    #             except Exception:
    #                 pass
    #         so_qty += qty

    #     # ── POS Order lines ───────────────────────────────────────────────────
    #     pos_domain = [
    #         ('product_id', '=', product.id),
    #         ('order_id.state', 'in', ('done', 'invoiced')),
    #     ]

    #     pos_lines = self.env['pos.order.line'].search(pos_domain)
    #     pos_qty = 0.0
    #     for pol in pos_lines:
    #         qty = pol.qty
    #         line_uom = getattr(pol, 'product_uom_id', False)
    #         if line_uom and po_uom and line_uom.id != po_uom.id:
    #             try:
    #                 qty = line_uom._compute_quantity(qty, po_uom)
    #             except Exception:
    #                 pass
    #         pos_qty += qty

    #     total = so_qty + pos_qty

    #     _logger.info(
    #         'Consignment sold_qty | product: %s | PO: %s | SO lines found: %s | '
    #         'SO qty: %s | POS qty: %s | TOTAL: %s',
    #         product.display_name,
    #         self.order_id.name,
    #         len(so_lines),
    #         so_qty,
    #         pos_qty,
    #         total,
    #     )
    #     return total

    def _get_receipt_date(self):
        pickings = self.order_id.picking_ids.filtered(
            lambda p: p.state == 'done'
        )
        if not pickings:
            return False
        dates = [p.date_done for p in pickings if p.date_done]
        return min(dates) if dates else False

    def _get_product_display_name(self):
        self.ensure_one()
        ref = self.product_id.default_code
        name = self.product_id.display_name
        return '%s [%s]' % (name, ref) if ref else name

    def _get_billing_account(self):
        self.ensure_one()
        product = self.product_id
        accounts = product.product_tmpl_id.get_product_accounts()
        account = accounts.get('expense')
        if not account:
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        return account.id if account else False
    # def _get_line_vendor(self):
    
    #     self.ensure_one()
    #     if not self.product_id:
    #         return self.order_id.partner_id

    #     # Check product supplierinfo for an explicit vendor override
    #     supplier_info = self.env['product.supplierinfo'].search([
    #         ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
    #     ], limit=1)
    #     if supplier_info and supplier_info.partner_id:
    #         return supplier_info.partner_id

    #     # Default: the PO's partner
    #     return self.order_id.partner_id
    def _get_line_vendor(self):
        self.ensure_one()

        if self.line_vendor_id:
            return self.line_vendor_id

        return self.order_id.partner_id
