from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ExpiredMedicinesWizard(models.TransientModel):
    """
    SC2-UC-05: Wizard for bulk transfer of expired medicines
    to the expired products location.
    """
    _name        = 'pharmacy.expired.medicines.wizard'
    _description = 'Bulk Transfer Expired Medicines'

    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination (Expired Location)',
        domain=[('is_expired_location', '=', True)],
        required=True,
    )

    expired_lot_ids = fields.Many2many(
        'stock.lot',
        string='Expired Lots to Transfer',
        domain=[('near_expiry_status', '=', 'expired')],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Auto-fill expired lots
        expired = self.env['stock.lot'].search([
            ('near_expiry_status', '=', 'expired')
        ])
        res['expired_lot_ids'] = [(6, 0, expired.ids)]
        # Auto-fill expired location
        expired_loc = self.env['stock.location'].get_expired_location()
        if expired_loc:
            res['location_dest_id'] = expired_loc.id
        return res

    def action_transfer_expired(self):
        """SC2-UC-05: Create stock picking to move all expired lots."""
        if not self.expired_lot_ids:
            raise UserError('No expired lots selected for transfer.')
        if not self.location_dest_id:
            raise UserError(
                'Please configure an Expired Products Location first.\n'
                'Go to Inventory → Configuration → Locations and enable '
                '"Expired Products Location" on the target location.'
            )

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal')
        ], limit=1)

        if not picking_type:
            raise UserError('No internal transfer operation type found.')

        # Group by source location
        move_lines = []
        for lot in self.expired_lot_ids:
            quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
                ('location_id.is_expired_location', '=', False),
            ])
            for quant in quants:
                move_lines.append({
                    'name': f'Expired: {lot.name}',
                    'product_id': quant.product_id.id,
                    'product_uom_qty': quant.quantity,
                    'product_uom': quant.product_id.uom_id.id,
                    'location_id': quant.location_id.id,
                    'location_dest_id': self.location_dest_id.id,
                    'lot_id': lot.id,
                })

        if not move_lines:
            raise UserError('No stock found for the selected expired lots.')

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': move_lines[0]['location_id'],
            'location_dest_id': self.location_dest_id.id,
            'origin': 'Expired Medicines Bulk Transfer',
            'move_ids': [(0, 0, move) for move in move_lines],
        })

        picking.action_confirm()
        picking.action_assign()

        _logger.info(
            'pharmacy_expiry: Bulk transfer created — picking %s with %d moves.',
            picking.name, len(move_lines)
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Expired Medicines Transfer',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ExpiredMedicinesReport(models.Model):
    """
    SC2-UC-06: Expired Medicines Report — read-only SQL view
    grouped by branch (stock location).
    """
    _name        = 'pharmacy.expired.report'
    _description = 'Expired Medicines Report'
    _auto        = False
    _order       = 'expiration_date asc'

    lot_id          = fields.Many2one('stock.lot',      string='Lot / Serial',  readonly=True)
    lot_name        = fields.Char(                      string='Lot Name',      readonly=True)
    product_id      = fields.Many2one('product.product',string='Product',       readonly=True)
    product_name    = fields.Char(                      string='Product Name',  readonly=True)
    location_id     = fields.Many2one('stock.location', string='Branch / Location', readonly=True)
    location_name   = fields.Char(                      string='Location',      readonly=True)
    expiration_date = fields.Datetime(                  string='Expiry Date',   readonly=True)
    days_to_expiry  = fields.Integer(                   string='Days Expired',  readonly=True)
    qty_on_hand     = fields.Float(                     string='Qty on Hand',   readonly=True)
    near_expiry_status = fields.Selection([
        ('expired',     'Expired'),
        ('near_expiry', 'Near Expiry'),
        ('ok',          'OK'),
    ], string='Status', readonly=True)

    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS pharmacy_expired_report;
            CREATE OR REPLACE VIEW pharmacy_expired_report AS (
                SELECT
                    sq.id                                               AS id,
                    sl.id                                               AS lot_id,
                    sl.name                                             AS lot_name,
                    pp.id                                               AS product_id,
                    COALESCE(pt.name->>'en_US', pt.name::text)          AS product_name,
                    loc.id                                              AS location_id,
                    loc.complete_name                                   AS location_name,
                    sl.expiration_date                                  AS expiration_date,
                    CAST(
                        EXTRACT(DAY FROM sl.expiration_date - NOW())
                    AS INTEGER)                                         AS days_to_expiry,
                    sq.quantity                                         AS qty_on_hand,
                    CASE
                        WHEN sl.expiration_date <= NOW()
                            THEN 'expired'
                        WHEN sl.expiration_date <= NOW() + INTERVAL '90 days'
                            THEN 'near_expiry'
                        ELSE 'ok'
                    END                                                 AS near_expiry_status
                FROM stock_quant sq
                JOIN stock_lot       sl  ON sl.id  = sq.lot_id
                JOIN product_product pp  ON pp.id  = sq.product_id
                JOIN product_template pt ON pt.id  = pp.product_tmpl_id
                JOIN stock_location  loc ON loc.id = sq.location_id
                WHERE sq.quantity > 0
                  AND loc.usage = 'internal'
                  AND sl.expiration_date IS NOT NULL
                  AND sl.expiration_date <= NOW() + INTERVAL '90 days'
            )
        """)
