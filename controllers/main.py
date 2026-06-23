# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class FinivexController(http.Controller):
    _webhook_url = '/payment/finivex/webhook'

    @http.route(
        _webhook_url, type='http', auth='public', methods=['POST'],
        csrf=False, save_session=False,
    )
    def finivex_webhook(self, **kwargs):
        """Receive a signed terminal-state callback from Finivex.

        The signature is verified against the receiving provider's webhook
        secret before the payload is trusted. After verifying, the transaction
        is re-fetched from the status API (belt-and-braces) before the state is
        committed, guarding against replayed-but-valid callbacks.
        """
        raw_body = request.httprequest.get_data()  # raw bytes, never re-encoded
        headers = request.httprequest.headers
        timestamp = headers.get('X-PG-Timestamp')
        signature = headers.get('X-PG-Signature')

        try:
            payload = json.loads(raw_body or b'{}')
        except (ValueError, TypeError):
            _logger.warning("Finivex: webhook with invalid JSON body")
            return request.make_json_response({'error': 'invalid json'}, status=400)

        reference = payload.get('transactionId')
        if not reference:
            return request.make_json_response(
                {'error': 'missing transactionId'}, status=400,
            )

        # Locate the transaction first so we can resolve which provider's secret
        # to verify against (a DB may hold several Finivex providers).
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'finivex'),
        ], limit=1)
        if not tx_sudo:
            _logger.warning("Finivex: webhook for unknown reference %s", reference)
            return request.make_json_response({'error': 'unknown reference'}, status=404)

        provider_sudo = tx_sudo.provider_id
        if not provider_sudo._finivex_verify_signature(raw_body, timestamp, signature):
            _logger.warning(
                "Finivex: webhook signature verification failed for %s", reference,
            )
            return request.make_json_response({'error': 'bad signature'}, status=400)

        # Belt-and-braces: confirm against the status API before fulfilling.
        verified = self._finivex_confirm_via_status(provider_sudo, payload)

        try:
            tx_sudo._handle_notification_data('finivex', verified)
        except ValidationError:
            _logger.exception("Finivex: error handling webhook for %s", reference)
            return request.make_json_response({'error': 'processing failed'}, status=500)

        return request.make_json_response({'received': True}, status=200)

    @staticmethod
    def _finivex_confirm_via_status(provider_sudo, payload):
        """Re-fetch the transaction from the status API and merge the
        authoritative status back over the webhook payload.

        Falls back to the (already signature-verified) webhook payload if the
        status call fails, so a transient status-API outage doesn't drop a
        valid callback.
        """
        reference = payload.get('transactionId')
        payment_method = payload.get('paymentMethod')
        try:
            params = {'transactionId': reference}
            if payment_method:
                params['paymentMethod'] = payment_method
            if payload.get('externalRef'):
                params['externalRef'] = payload['externalRef']
            status_data = provider_sudo._finivex_make_request(
                '/v1/payments/status', params=params, method='GET',
            )
        except ValidationError:
            _logger.warning(
                "Finivex: status re-check failed for %s; trusting signed webhook",
                reference,
            )
            return payload

        # Map the status-API status onto the webhook lifecycle vocabulary the
        # transaction model understands.
        status_map = {
            'SUCCESS': 'COMPLETED',
            'FAILED': 'FAILED',
            'CANCELLED': 'CANCELLED',
            'REVERSED': 'REFUNDED',
            'PENDING': 'PENDING',
        }
        merged = dict(payload)
        api_status = (status_data.get('status') or '').upper()
        merged['status'] = status_map.get(api_status, payload.get('status'))
        if status_data.get('paymentMethod'):
            merged['paymentMethod'] = status_data['paymentMethod']
        if status_data.get('externalRef'):
            merged['externalRef'] = status_data['externalRef']
        return merged
