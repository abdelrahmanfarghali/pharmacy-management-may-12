# -*- coding: utf-8 -*-
from odoo import api, models


class PosSession(models.Model):
    """Ensure ``generic_name`` is included in the product payload that the
    POS front-end loads on session open.

    Odoo 18 POS uses ``_loader_params_product_product`` (and the analogous
    template variant) to declare which fields are fetched via JSON-RPC when
    the session initialises. Extending ``fields`` here is the canonical,
    upgrade-safe way to add custom fields to the POS product object without
    touching core JS.
    """

    _inherit = 'pos.session'

    @api.model
    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('generic_name')
        return result
