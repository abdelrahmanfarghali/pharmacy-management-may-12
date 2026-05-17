{
    'name': 'Pharmacy Product',
    'version': '18.0.2.0.0',
    'summary': 'UC-01: Generic Name | UC-02: Product Type | UC-09: Commission',
    'description': """
        Pharmacy Product Customization
        ================================
        UC-01: Generic/Scientific Name + Search by generic name
        UC-02: Sell As (Unit/Package) + Auto UoM + Price per Unit + Stock Display
        UC-09: Commission % per product + Discount-aware calc + Reversal on returns
               + Commission Report
    """,
    'category': 'Pharmacy',
    'author': 'Pharmacy Team',
    'depends': ['product', 'stock', 'uom', 'sale', 'account'],
    'data': [
        'views/product_template_views.xml',
        'views/commission_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
