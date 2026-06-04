from odoo import models, api, _
from odoo.exceptions import ValidationError
from datetime import date


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):

        today = date.today()

        expired_lines = []

        for order in self:
            for line in order.order_line:

                expired_lots = self.env['stock.lot'].search([
                    ('product_id', '=', line.product_id.id),
                    ('expiration_date', '<=', today),
                ], limit=1)

                if expired_lots:
                    expired_lines.append(
                        "%s - Lot %s - Exp %s"
                        % (
                            line.product_id.display_name,
                            expired_lots.name,
                            expired_lots.expiration_date.strftime('%m/%Y')
                        )
                    )

        if expired_lines and not self.env.context.get('expired_override'):

            return {
                'type': 'ir.actions.act_window',
                'name': _('Expired Product Warning'),
                'res_model': 'expired.sale.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.id,
                    'default_message': '\n'.join(expired_lines),
                }
            }

        return super().action_confirm()
    # def action_confirm(self):
    #     today = date.today()

    #     for order in self:
    #         for line in order.order_line:

    #             lots = self.env['stock.lot'].search([
    #                 ('product_id', '=', line.product_id.id),
    #                 ('expiration_date', '<=', today)
    #             ])

    #             if lots:
    #                 raise ValidationError(_(
    #                     "Cannot confirm sale.\n"
    #                     "Product %s contains expired lots."
    #                 ) % line.product_id.display_name)

    #     return super().action_confirm()