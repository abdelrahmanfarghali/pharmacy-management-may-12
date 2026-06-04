from odoo import models, fields, _


class ExpiredSaleWarningWizard(models.TransientModel):
    _name = 'expired.sale.warning.wizard'
    _description = 'Expired Product Warning'

    sale_order_id = fields.Many2one(
        'sale.order',
        required=True
    )

    message = fields.Text(
        readonly=True
    )

    def action_continue(self):

        self.sale_order_id.message_post(
            body=_(
                'Expired product warning overridden by %s on %s'
            ) % (
                self.env.user.name,
                fields.Datetime.now()
            )
        )

        return self.sale_order_id.with_context(
            expired_override=True
        ).action_confirm()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}