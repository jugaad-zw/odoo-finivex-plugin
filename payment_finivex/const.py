# -*- coding: utf-8 -*-

# Default production gateway base URL. The provider record may override this for
# staging/local testing via the ``finivex_base_url`` field.
DEFAULT_BASE_URL = 'https://gateway.finivex.online/api/pg'

# Finivex only settles in these currencies. Other store currencies are filtered
# out of the provider's compatibility list.
SUPPORTED_CURRENCIES = ('USD', 'ZWG')

# Webhook signature scheme (see docs/webhooks.md).
SIGNATURE_VERSION = 'v1'
SIGNATURE_TOLERANCE_SECONDS = 300

# Payment methods the hosted page can be locked to. Keys are the gateway enum
# values; the empty value lets the shopper choose on the hosted page.
PAYMENT_METHODS = [
    ('', "Let the shopper choose"),
    ('ECOCASH', "EcoCash"),
    ('ONEMONEY', "OneMoney"),
    ('OMARI', "Omari"),
    ('INNBUCKS', "InnBucks"),
    ('POS', "ZimSwitch POS"),
    ('VISA', "Visa"),
    ('MASTERCARD', "Mastercard"),
    ('ZIPIT', "ZIPIT"),
    ('WALLET', "Wallet"),
    ('MPGS', "Visa/Mastercard (MPGS)"),
]

# Terminal webhook statuses → how the Odoo transaction should resolve.
# 'done' / 'error' / 'cancel' are handled in payment_transaction.py.
STATUS_DONE = ('COMPLETED',)
STATUS_CANCEL = ('CANCELLED', 'EXPIRED')
STATUS_ERROR = ('FAILED',)
STATUS_REFUNDED = ('REFUNDED',)
