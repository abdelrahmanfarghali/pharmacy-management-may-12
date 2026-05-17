from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # UC-09: Company-level enable/disable commission
    use_commission = fields.Boolean(
        string='Enable Commission on Sales',
        config_parameter='pharmacy_system.use_commission',
        help='When enabled, commission % is calculated on every sale order line.',
    )
