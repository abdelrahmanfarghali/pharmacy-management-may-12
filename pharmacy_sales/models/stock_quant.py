from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _quant_tasks(self):
        """
        SC5-UC-01: After any stock update, check if pending
        wishlist items can now be fulfilled.
        """
        res = super()._quant_tasks()
        try:
            self.env['pharmacy.wishlist'].action_check_stock_and_notify()
        except Exception as e:
            _logger.warning('pharmacy_wishlist stock check failed: %s', e)
        return res
