# -*- coding: utf-8 -*-
{
    'name': 'Pharmacy Consignment Purchase',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Consignment Purchase Order tracking for pharmacies',
    'description': """
        SC3-UC-02 — Consignment Purchase (التصريف تحت بضاعة)
        =========================================================
        Adds consignment purchase workflow:
        - Consignment flag on Purchase Orders
        - Track Stock pop-up with sold vs paid quantities
        - Partial payment (vendor bill) locked to payable-now quantity
        - Unsold stock return via standard Odoo transfers
    """,
    'author': 'Pharmacy System',
    'depends': [
        'purchase',
        'stock',
        'account',
        'sale_management',
        'point_of_sale',
        
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/consignment_data.xml',
        'views/purchase_order_views.xml',
        'views/purchase_order_list_views.xml',
        'views/sale_order_consignment_views.xml',
        'wizard/track_stock_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pharmacy_consignment/static/src/scss/consignment.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
