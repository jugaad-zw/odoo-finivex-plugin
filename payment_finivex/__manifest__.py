# -*- coding: utf-8 -*-
{
    'name': "Finivex Payment Gateway",
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': "Accept every payment in Zimbabwe — EcoCash, OneMoney, Visa, "
               "Mastercard, ZIPIT, InnBucks and more. One integration, all "
               "payment methods.",
    'description': """
Accept every payment in Zimbabwe
================================

EcoCash, OneMoney, Visa, Mastercard, ZIPIT, InnBucks and more. One integration,
all payment methods. Start collecting payments in minutes.

Start collecting payments and track everything in real-time.

Pay as you go
-------------
* All payment methods included
* No setup or monthly fees
* Merchant portal access
* Webhook notifications

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
