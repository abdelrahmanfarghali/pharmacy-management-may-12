# -*- coding: utf-8 -*-
# Copyright (c) 2025
# License LGPL-3: https://www.gnu.org/licenses/lgpl-3.0-standalone.html
{
    'name': 'Pharmacy System',
    'version': '18.0.1.0.0',
    'author': 'Petra Software',
    'website': 'https://www.t-petra.com/',
    'category': 'Inventory',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'sale',
        'account',
        'stock',
        'point_of_sale',
        'barcodes'],
    'data': [
        "security/ir.model.access.csv",
        'data/barcode_sequence_data.xml',
        'data/product_category_data.xml',
        'report/report_invoice.xml',
        'report/report_saleorder.xml',
        'report/report_delivery.xml',
        'report/report_pos_receipt.xml',
        'report/report_product_label.xml',
        'views/product_barcode_views.xml',
        'views/pos_product_xpath.xml',
        'views/medicine_feature.xml',
        'views/base_view.xml',
        'views/product_template_views.xml',
        'views/product_label_layout_views.xml',
        'views/product_product_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pharmacy_system/static/src/js/pos_product_search_patch.js',
            'pharmacy_system/static/src/js/barcode_handler.js',
        ],
    },
    'price': 10.0,
    'currency': 'USD',
    'installable': True,
    'auto_install': True,
    'application': True
}