{
    'name': 'Pharmacy Expiry Lifecycle',
    'version': '18.0.1.0.0',
    'summary': 'SC2: Expiry Lifecycle End-to-End — UC-01 to UC-06',
    'description': """
        Pharmacy Expiry Lifecycle — Phase 2 Scenario 2
        ================================================
        SC2-UC-01: Configure Expired Product Location Type
        SC2-UC-02: Month/Year Expiry Date Input — UI & Purchase Receipt
        SC2-UC-03: Expiry Date Warning & Near-Expiry Alerts
        SC2-UC-04: Expired Lot Detection & Notification
        SC2-UC-05: Expired Medicines Page — Bulk Transfer to Expired Location
        SC2-UC-06: Expired Medicines Report per Branch with PDF Export
    """,
    'category': 'Pharmacy',
    'author': 'Pharmacy Team',
    'depends': ['stock', 'product', 'mail', 'purchase', 'product_expiry'],
    'data': [
        'security/ir.model.access.csv',
        'data/expiry_cron.xml',
        'views/stock_location_views.xml',
        'views/stock_lot_views.xml',
        'views/expired_medicines_views.xml',
        'report/expired_report_template.xml',
        'report/expired_report_action.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
