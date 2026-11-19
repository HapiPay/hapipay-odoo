# HapiditPay pour Odoo. Licence LGPL-3.

import json
import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment_hapiditpay import const


_logger = logging.getLogger(__name__)


class HapiditPayController(http.Controller):
    _return_url = '/payment/hapiditpay/return'
    _webhook_url = '/payment/hapiditpay/webhook'

    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def hapiditpay_return(self, reference=None, **kwargs):
        """ Retour du client après la page HapiditPay.

        Les paramètres ajoutés par HapiditPay (?paiement=…&statut=…) ne sont qu'une
        indication : l'état est demandé à HapiditPay, de serveur à serveur.
        """
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference or ''), ('provider_code', '=', 'hapiditpay'),
        ], limit=1)
        if tx_sudo and tx_sudo.state in ('draft', 'pending'):
            tx_sudo._hapiditpay_check_link_state()
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def hapiditpay_webhook(self):
        """ Webhooks HapiditPay. La signature HapiditPay-Signature tient lieu d'authentification. """
        raw = request.httprequest.get_data()
        header = request.httprequest.headers.get('HapiditPay-Signature', '')

        secrets = request.env['payment.provider'].sudo().search([
            ('code', '=', 'hapiditpay'), ('hapiditpay_webhook_secret', '!=', False),
        ]).mapped('hapiditpay_webhook_secret')
        if not any(const.valid_signature(header, raw, secret) for secret in secrets):
            _logger.warning("HapiditPay : webhook à la signature invalide")
            return request.make_json_response({'message': "Signature invalide."}, status=401)

        try:
            event = json.loads(raw or b'{}')
        except ValueError:
            return request.make_json_response({'message': "JSON attendu."}, status=400)

        name = event.get('evenement') if isinstance(event, dict) else None
        data = event.get('data') if isinstance(event, dict) and isinstance(event.get('data'), dict) else {}

        if name == 'test.ping':
            return request.make_json_response({'ok': True})

        transactions = request.env['payment.transaction'].sudo()
        if not transactions._hapiditpay_odoo_reference(data.get('reference')):
            # Pas une transaction de cet Odoo (une boutique sur le même compte, par exemple) :
            # on accuse réception pour éviter les relances.
            return request.make_json_response({'ignore': True})

        try:
            transactions._handle_notification_data('hapiditpay', dict(data, evenement=name))
        except ValidationError:
            _logger.exception("HapiditPay : webhook non traité ; accusé de réception quand même")
            return request.make_json_response({'ignore': True})

        return request.make_json_response({'ok': True})
