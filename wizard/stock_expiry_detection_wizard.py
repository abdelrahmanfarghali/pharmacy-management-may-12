# -*- coding: utf-8 -*-
"""
INV-UC-02 — On-Demand Expiry Detection Wizard
Allows Inventory Managers to trigger the expiry scan manually from
Inventory > Operations > Run Expiry Detection.

No stock movements are created — detection and notification only.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockExpiryDetectionWizard(models.TransientModel):
    _name = 'stock.expiry.detection.wizard'
    _description = 'Run Expiry Detection — On Demand (INV-UC-02)'

    # ─────────────────────────────────────────────
    # Input fields
    # ─────────────────────────────────────────────
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        domain="[('company_id', '=', company_id)]",
        help='Select a specific warehouse to scan, or leave blank to scan all warehouses.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    scan_all_warehouses = fields.Boolean(
        string='Scan All Warehouses',
        default=True,
        help='When checked, all warehouses of the selected company are scanned.',
    )

    @api.onchange('scan_all_warehouses')
    def _onchange_scan_all_warehouses(self):
        if self.scan_all_warehouses:
            self.warehouse_id = False

    # ─────────────────────────────────────────────
    # Action: run detection
    # ─────────────────────────────────────────────
    def action_run_detection(self):
        self.ensure_one()

        warehouse_id = False if self.scan_all_warehouses else (self.warehouse_id.id or False)

        # Switch company context if needed
        detection_model = self.env['stock.expiry.detection'].with_company(self.company_id)

        detection = detection_model._run_expiry_detection(
            warehouse_id=warehouse_id,
            trigger_type='manual',
        )

        # Build result message
        if detection.state == 'no_results':
            warehouse_label = (
                self.warehouse_id.name if self.warehouse_id
                else _('all warehouses')
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Expired Lots Found'),
                    'message': _(
                        'No newly expired lots detected for %s.'
                    ) % warehouse_label,
                    'type': 'success',
                    'sticky': False,
                },
            }

        # Open the detection result record
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expiry Detection Results'),
            'res_model': 'stock.expiry.detection',
            'res_id': detection.id,
            'view_mode': 'form',
            'target': 'current',
        }
