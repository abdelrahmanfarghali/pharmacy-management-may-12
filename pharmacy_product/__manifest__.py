{
    'name': 'Pharmacy Product',
    'version': '18.0.1.0.0',
    'summary': 'UC-01: Generic Name | UC-02: Product Type (Unit/Package)',
    'description': """
        Pharmacy Product Customization
        ================================
        UC-01: Adds generic/scientific name field (optional) alongside product name (mandatory)
                + Search by generic name support
        UC-02: Adds product_type field (Unit / Package)
                + units_per_package field
                + auto UoM configuration
                + Prevents type change after stock moves
    """,
    'category': 'Pharmacy',
    'author': 'Pharmacy Team',
    'depends': ['product', 'stock', 'uom'],
    'data': [
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
