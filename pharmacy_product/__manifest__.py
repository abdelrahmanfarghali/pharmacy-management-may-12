{
    'name': 'Pharmacy Product',
    'version': '18.0.4.0.0',
    'summary': 'UC-01 | UC-02 | UC-07 | UC-08 | UC-09',
    'description': """
        Pharmacy Product Customization
        ================================
        UC-01: Generic/Scientific Name + Search by generic name
        UC-02: Sell As (Unit/Package) + Auto UoM + Price per Unit + Stock Display
        UC-07: Public Price validation + Below-cost warning + Gov Lock + Price History
        UC-08: AVCO cost visibility + Hide if no purchase history
        UC-09: Commission % + Discount-aware + Reverse on returns + Report
    """,
    'category': 'Pharmacy',
    'author': 'Pharmacy Team',
    'depends': ['product', 'stock', 'uom', 'sale', 'account', 'sales_team'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/pricing_views.xml',
        'views/commission_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
