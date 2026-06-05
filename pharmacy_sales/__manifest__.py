{
    'name': 'Pharmacy Sales',
    'version': '18.0.1.0.0',
    'summary': 'SC5-UC-01: Wishlist — Out-of-Stock Customer Request Management',
    'description': """
        Pharmacy Sales — Phase 2 Scenario 5
        =====================================
        SC5-UC-01: Wishlist (قائمة الأمنيات)
                   Customer requests for out-of-stock products.
                   - Record customer + product + qty requested
                   - Auto-notify customer when product is back in stock
                   - Link to Sales Order when available
                   - Dashboard view with status tracking
    """,
    'category': 'Pharmacy',
    'author': 'Pharmacy Team',
    'depends': ['sale', 'stock', 'product', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/wishlist_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
