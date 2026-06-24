# -*- coding: utf-8 -*-
import hashlib
import hmac
import logging
import time

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_finivex import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('finivex', "Finivex")],
        ondelete={'finivex': 'set default'},
    )
    finivex_api_key = fields.Char(
        string="API Key",
        help="Your Finivex merchant API key.",
        required_if_provider='finivex',
        groups='base.group_system',
    )
    finivex_api_secret = fields.Char(
        string="API Secret",
        help="Your Finivex merchant API secret (shown only once at key creation).",
        required_if_provider='finivex',
        groups='base.group_system',
    )
    finivex_webhook_secret = fields.Char(
        string="Webhook Secret",
        help="Webhook signing secret, from merchant registration or rotation. "
             "Used to verify the authenticity of incoming callbacks.",
        required_if_provider='finivex',
        groups='base.group_system',
    )
    finivex_base_url = fields.Char(
        string="Gateway Base URL",
        help="Override for staging/local testing. Leave blank to use production.",
        groups='base.group_system',
    )
    finivex_payment_method_lock = fields.Selection(
        selection=const.PAYMENT_METHODS,
        string="Lock Payment Method",
        default='',
        help="Optionally force the hosted page to a single payment rail. "
             "Leave empty to let the shopper choose.",
    )
    finivex_expires_in_minutes = fields.Integer(
        string="Checkout Expiry (minutes)",
        default=30,
        help="Lifetime of the hosted checkout session before it expires.",
    )

    # === Business helpers ===================================================

    def _finivex_get_base_url(self):
        """Return the configured gateway base URL without a trailing slash."""
        self.ensure_one()
        return (self.finivex_base_url or const.DEFAULT_BASE_URL).rstrip('/')

    def _finivex_make_request(self, endpoint, payload=None, params=None, method='POST'):
        """Make an authenticated request to the Finivex gateway and return the
        ``data`` envelope of the JSON response.

        :param str endpoint: The path appended to the base URL, e.g.
            ``/v1/payments/hosted-checkout``.
        :param dict payload: The JSON body for POST requests.
        :param dict params: The query-string parameters.
        :param str method: ``GET`` or ``POST``.
        :return: The decoded ``data`` object (or the whole body if absent).
        :rtype: dict
        :raise ValidationError: If the request fails or the gateway returns an
            error envelope.
        """
        self.ensure_one()
        url = self._finivex_get_base_url() + endpoint
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-API-Key': self.finivex_api_key or '',
            'X-API-Secret': self.finivex_api_secret or '',
        }
        try:
            response = requests.request(
                method, url, json=payload, params=params, headers=headers, timeout=30,
            )
            data = response.json()
        except requests.exceptions.RequestException as e:
            _logger.exception("Finivex: unable to reach %s", url)
            raise ValidationError(
                _("Finivex: Could not contact the payment gateway. Please try again.")
            ) from e
        except ValueError as e:
            _logger.exception("Finivex: invalid JSON from %s", url)
            raise ValidationError(
                _("Finivex: The payment gateway returned an invalid response.")
            ) from e

        # The gateway signals failure via HTTP status >= 400 and/or
        # ``success: false`` in the envelope.
        if response.status_code >= 400 or data.get('success') is False:
            error_message = data.get('errorMessage') or data.get('message') \
                or _("The payment gateway rejected the request.")
            _logger.warning(
                "Finivex: error from %s (HTTP %s): %s",
                url, response.status_code, error_message,
            )
            raise ValidationError(_("Finivex: %s", error_message))

        # Unwrap the ``data`` envelope when present.
        if isinstance(data.get('data'), dict):
            return data['data']
        return data

    def _finivex_verify_signature(self, raw_body, timestamp, signature_header):
        """Verify a webhook's HMAC-SHA256 signature.

        Mirrors the ``v1`` scheme documented in docs/webhooks.md:
        ``signature = hex(HMAC_SHA256(secret, "{timestamp}.{rawBody}"))``.

        :param bytes raw_body: The raw request body bytes (never re-serialised).
        :param str timestamp: The ``X-PG-Timestamp`` header value.
        :param str signature_header: The ``X-PG-Signature`` header value,
            e.g. ``v1=3f9a...``.
        :return: Whether the signature is valid and within the replay window.
        :rtype: bool
        """
        self.ensure_one()
        secret = self.finivex_webhook_secret
        if not secret or not timestamp or not signature_header:
            return False

        prefix = const.SIGNATURE_VERSION + '='
        if not signature_header.startswith(prefix):
            return False
        provided_hex = signature_header[len(prefix):]

        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            return False
        if abs(int(time.time()) - ts) > const.SIGNATURE_TOLERANCE_SECONDS:
            return False

        signed_payload = str(ts).encode() + b'.' + raw_body
        expected = hmac.new(
            secret.encode(), signed_payload, hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, provided_hex)

    # === Framework overrides ================================================

    def _compute_feature_support_fields(self):
        """Enable refund support for Finivex providers.

        The refund flow (``_send_refund_request``) is gated by this feature
        flag; without it the framework never surfaces the refund action.
        Finivex supports partial refunds, so ``'partial'`` is declared.
        """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'finivex').update({
            'support_refund': 'partial',
        })

    def _get_supported_currencies(self):
        """Restrict Finivex to the currencies it can actually settle."""
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'finivex':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """The generic 'finivex' payment method is the only one bound here; the
        actual rail is chosen by the shopper on the hosted page."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'finivex':
            return default_codes
        return ['finivex']
