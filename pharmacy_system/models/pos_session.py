# -*- coding: utf-8 -*-
from odoo import api, models


class PosSession(models.Model):
    """Obsolete for Odoo 18.

    Odoo 18 has migrated point_of_sale fields loading from the POS session
    loader params (such as `_loader_params_product_product`) to the new
    `pos.load.mixin` model-level `_load_pos_data_fields` interface.

    Custom product/variant fields for the POS front-end are now correctly injected
    by overriding `_load_pos_data_fields` in `product.product`.
    """

    _inherit = 'pos.session'

