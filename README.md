# Finivex Payment Gateway — Odoo Module

## Accept every payment in Zimbabwe

EcoCash, OneMoney, Visa, Mastercard, ZIPIT, InnBucks and more. One integration,
all payment methods. Start collecting payments in minutes and track everything
in real-time.

**Pay as you go**

- All payment methods included
- No setup or monthly fees
- Merchant portal access
- Webhook notifications

---

Adds **Finivex** as a redirect-based payment provider for Odoo 17. Customers are
sent to the Finivex hosted checkout to pay with EcoCash, OneMoney, Omari,
InnBucks, ZimSwitch POS, ZIPIT, Wallet, or Visa/Mastercard (MPGS). Orders are
confirmed from a **signed webhook** and re-verified against the status API
before fulfilment.

## How it maps to the gateway

| Odoo hook | Gateway call |
|-----------|--------------|
| `payment.transaction._get_specific_rendering_values` | `POST /v1/payments/hosted-checkout` → redirect customer to `redirectUrl` |
| `/payment/finivex/webhook` controller | Verifies `X-PG-Signature` (HMAC-SHA256 `v1`), then `GET /v1/payments/status` (belt-and-braces) |
| `payment.transaction._send_refund_request` | `POST /v1/payments/refund` |

The Odoo transaction `reference` is sent as the gateway `transactionId` — it is
unique per database, satisfying Finivex's global-uniqueness requirement.

## Installation

1. Copy the `payment_finivex/` folder into your Odoo `addons` path.
2. Update the apps list and install **Finivex Payment Gateway**.
3. Go to **Accounting → Configuration → Payment Providers → Finivex** and set:
   - **API Key** / **API Secret** — your merchant credentials.
   - **Webhook Secret** — the signing secret from merchant registration/rotation.
   - **Gateway Base URL** — leave blank for production
     (`https://gateway.finivex.online/api/pg`), or override for staging/local.
   - Optionally **Lock Payment Method** and **Checkout Expiry**.
4. Set the provider **State** to *Enabled* (or *Test mode*) and publish it.

## Webhook configuration

Point the merchant `callbackUrl` (in the Finivex portal, or per-session) at:

```
https://<your-odoo-host>/payment/finivex/webhook
```

The module sends this URL automatically as the per-session `callbackUrl`, but
configuring the merchant-level default as a fallback is recommended.

## Supported currencies

`USD` and `ZWG` only. Other store currencies are filtered out of the provider's
compatibility list automatically.

## Notes

- Refunds require the rail the customer actually paid with; this is captured
  from the webhook (`paymentMethod`) and stored on the transaction. A refund
  attempted before the payment webhook arrives is rejected with a clear error.
- The webhook handler always re-checks the status API, so a replayed-but-valid
  callback inside the 5-minute signature window cannot mis-fulfil an order.
