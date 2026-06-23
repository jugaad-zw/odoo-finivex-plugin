# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlsplit, parse_qsl, urlunsplit

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_finivex import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    finivex_reference = fields.Char(
        string="Finivex Session Reference",
        help="The opaque hosted-checkout session reference returned by Finivex.",
        readonly=True,
    )
    finivex_payment_method = fields.Char(
        string="Finivex Payment Method",
        help="The rail the customer actually paid with, reported by the "
             "webhook. Required to route refunds.",
        readonly=True,
    )

    # === Rendering ==========================================================

    def _get_specific_rendering_values(self, processing_values):
        """Create a hosted-checkout session and return the redirect details.

        The Odoo transaction ``reference`` is used directly as the gateway
        ``transactionId`` (it is globally unique within the database, which
        satisfies Finivex's uniqueness requirement).
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'finivex':
            return res

        base_url = self.provider_id.get_base_url()
        payload = {
            'transactionId': self.reference,
            'amount': f"{self.amount:.4f}".rstrip('0').rstrip('.'),
            'currency': self.currency_id.name,
            'description': self.reference,
            'callbackUrl': base_url + '/payment/finivex/webhook',
            'returnUrl': base_url + '/payment/status',
            'cancelUrl': base_url + '/payment/status',
            'expiresInMinutes': self.provider_id.finivex_expires_in_minutes or 30,
        }
        if self.partner_phone:
            payload['customerPhone'] = self.partner_phone
        lock = self.provider_id.finivex_payment_method_lock
        if lock:
            payload['paymentMethod'] = lock

        session = self.provider_id._finivex_make_request(
            '/v1/payments/hosted-checkout', payload=payload,
        )
        redirect_url = session.get('redirectUrl')
        if not redirect_url:
            raise ValidationError(
                _("Finivex: The gateway did not return a redirect URL.")
            )

        # Persist the session reference for later reconciliation/debugging.
        self.finivex_reference = session.get('reference')

        # The hosted page reads its query string (e.g. ``?reference=...``).
        # A GET form would drop that query, so split it out into hidden inputs
        # that the auto-submitted redirect form re-appends.
        split = urlsplit(redirect_url)
        form_action = urlunsplit((split.scheme, split.netloc, split.path, '', ''))
        return {
            'api_url': form_action,
            'url_params': dict(parse_qsl(split.query)),
        }

    # === Notification handling ==============================================

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction matching a webhook / status payload."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'finivex' or len(tx) == 1:
            return tx

        reference = notification_data.get('transactionId')
        if not reference:
            raise ValidationError(_("Finivex: Received data with missing reference."))

        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'finivex'),
        ])
        if not tx:
            raise ValidationError(
                _("Finivex: No transaction found matching reference %s.", reference)
            )

        # The gateway reports a refund against the *original* transactionId, so
        # a REFUNDED callback initially matches the (already done) source
        # transaction. Redirect it to the pending refund child it settles.
        status = (notification_data.get('status') or '').upper()
        if status in const.STATUS_REFUNDED and tx.operation != 'refund':
            refund_tx = self.search([
                ('source_transaction_id', '=', tx.id),
                ('operation', '=', 'refund'),
                ('state', 'in', ('draft', 'pending')),
            ], limit=1, order='create_date desc')
            if refund_tx:
                return refund_tx
        return tx

    def _process_notification_data(self, notification_data):
        """Resolve the transaction state from a verified webhook/status payload.

        Webhook payloads carry an upper-case lifecycle status (``COMPLETED``,
        ``FAILED``, ``CANCELLED``, ``EXPIRED``, ``REFUNDED``). The status API
        instead reports ``SUCCESS``/``PENDING``/``FAILED``/``CANCELLED``; both
        spellings are normalised here.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'finivex':
            return

        # Record the actual rail and provider reference when reported.
        payment_method = notification_data.get('paymentMethod')
        if payment_method:
            self.finivex_payment_method = payment_method
        external_ref = notification_data.get('externalRef')
        if external_ref:
            self.provider_reference = external_ref

        status = (notification_data.get('status') or '').upper()
        description = notification_data.get('statusDescription') or status

        if status in const.STATUS_DONE or status == 'SUCCESS':
            self._set_done()
        elif status in const.STATUS_ERROR or status == 'FAILED':
            self._set_error(_("Finivex: %s", description))
        elif status in const.STATUS_CANCEL:
            self._set_canceled(_("Finivex: %s", description))
        elif status in const.STATUS_REFUNDED:
            self._set_done()  # refund transactions resolve as done
        elif status == 'PENDING':
            self._set_pending()
        else:
            _logger.info(
                "Finivex: received unhandled status '%s' for tx %s",
                status, self.reference,
            )
            self._set_pending()

    # === Refunds ============================================================

    def _send_refund_request(self, amount_to_refund=None):
        """Issue a refund through the gateway.

        Called on the *source* (original) transaction; ``super()`` creates and
        returns the refund child transaction.
        """
        if self.provider_code != 'finivex':
            return super()._send_refund_request(amount_to_refund=amount_to_refund)

        # The refund must be routed to the rail the customer actually paid with,
        # which is only known once the payment webhook has been received.
        payment_method = self.finivex_payment_method
        if not payment_method:
            raise ValidationError(
                _("Finivex: The payment method is unknown for this transaction, "
                  "so the refund cannot be routed. It is recorded once the "
                  "payment webhook is received.")
            )

        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)

        self.provider_id._finivex_make_request(
            '/v1/payments/refund',
            params={
                'transactionId': self.reference,
                'paymentMethod': payment_method,
                'reason': refund_tx.reference,
            },
        )
        # The terminal REFUNDED webhook will flip the refund tx to done; mark it
        # pending in the meantime so it is not left in draft.
        refund_tx._set_pending()
        return refund_tx
