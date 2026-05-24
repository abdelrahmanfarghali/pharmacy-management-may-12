# -*- coding: utf-8 -*-
{
    'name': 'Pharmacy — Expired Product Location',
    'version': '18.0.1.0.0',
    'summary': 'INV-UC-01 — Dedicated Expired location type with POS exclusion and transfer rules',
    'description': """
        Implements a dedicated "Expired" warehouse location type for pharmacy operations.

        Features:
        - New "Expired" location type in Odoo warehouse configuration
        - POS & Sales exclusion: expired stock never appears in POS available quantity
        - Inventory visibility: expired stock visible in reports with red label
        - Transfer rules: stock can only leave Expired → Scrap or another Expired location
        - Mandatory transfer note when moving to/from Expired locations
        - Full traceability of who moved stock to/from Expired locations
    """,
    'category': 'Inventory/Inventory',
    'author': 'Pharmacy System',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'point_of_sale',
        'sale_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_location_data.xml',
        'views/stock_location_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_quant_views.xml',
        'views/product_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pharmacy_expired_location/static/src/css/expired_location.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
