# -*- coding: utf-8 -*-
{
    'name': "Finivex Payment Gateway",
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': "Accept EcoCash, OneMoney, Omari, InnBucks, ZimSwitch and card "
               "payments through the Finivex hosted checkout.",
    'description': """
Finivex Payment Gateway
======================

Adds Finivex as a redirect-based payment provider in Odoo. Customers are sent to
the Finivex hosted checkout page to pay with EcoCash, OneMoney, Omari, InnBucks,
ZimSwitch POS, Visa/Mastercard (MPGS) and more. The order is confirmed from a
signed webhook and re-verified against the status API before fulfilment.

Supported currencies: USD, ZWG.
    """,
    'author': "Finivex",
    'website': "https://gateway.finivex.online",
    'license': 'LGPL-3',
    'depends': ['payment'],
    'data': [
        'views/payment_finivex_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'installable': True,
    'images': ['static/description/icon.png'],
}
