# HapiditPay pour Odoo. Licence LGPL-3.

import hashlib
import logging
from urllib.parse import urlencode

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from odoo.addons.payment_hapiditpay import const


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # === RÉFÉRENCES === #

    @api.model
    def _hapiditpay_instance_tag(self):
        """ Six caractères propres à cette base Odoo. """
        uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')
        return hashlib.sha1(uuid.encode()).hexdigest()[:6]

    def _hapiditpay_reference(self):
        """ Référence de la page HapiditPay : odoo-<base>-<référence Odoo>. """
        self.ensure_one()
        return f"{const.REFERENCE_PREFIX}{self._hapiditpay_instance_tag()}-{self.reference}"[:191]

    @api.model
    def _hapiditpay_odoo_reference(self, hapiditpay_reference):
        """ Référence Odoo d'une référence HapiditPay de cette base, sinon None. """
        prefix = f"{const.REFERENCE_PREFIX}{self._hapiditpay_instance_tag()}-"
        if hapiditpay_reference and hapiditpay_reference.startswith(prefix):
            return hapiditpay_reference[len(prefix):] or None
        return None

    # === PAIEMENT === #

    def _get_specific_rendering_values(self, processing_values):
        """ Crée la page de paiement HapiditPay à usage unique et y envoie le client. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'hapiditpay':
            return res

        # HapiditPay compte en unités entières de la devise (FCFA, ariary, francs congolais…).
        amount = round(self.amount)
        if float_compare(self.amount, amount, precision_digits=6) != 0:
            raise ValidationError("HapiditPay: " + _(
                "This amount has cents: HapiditPay only accepts whole amounts."
            ))

        lang = (self.partner_lang or self.env.lang or '')[:2]
        base_url = self.provider_id.get_base_url().rstrip('/')
        data = self.provider_id._hapiditpay_make_request('POST', 'liens', {
            'reference': self._hapiditpay_reference(),
            'titre': (self.reference or '')[:120],
            'description': self.company_id.name,
            'montant': int(amount),
            'devise': self.currency_id.name,
            'usage_unique': True,
            'url_retour': base_url + '/payment/hapiditpay/return?' + urlencode({'reference': self.reference}),
            'langue': lang if lang in const.LANGUAGES else None,
        })
        if not data.get('url') or not data.get('code'):
            raise ValidationError("HapiditPay: " + _("The payment page could not be created."))

        # Le code de la page sert à demander son état au retour du client.
        self.provider_reference = data['code']
        return {'api_url': data['url']}

    def _hapiditpay_check_link_state(self):
        """ Retour du client avant le webhook : l'état de la page est demandé à HapiditPay. """
        self.ensure_one()
        if not self.provider_reference:
            return
        try:
            link = self.provider_id._hapiditpay_make_request('GET', f'liens/{self.provider_reference}')
        except ValidationError:
            _logger.warning("HapiditPay : état de la page %s indisponible", self.provider_reference)
            return

        if link.get('etat') == 'paye':
            self._handle_notification_data('hapiditpay', {
                'evenement': 'paiement.reussi',
                'reference': link.get('reference'),
                'id': link.get('paiement'),
                'montant': link.get('montant'),
                'devise': link.get('devise'),
            })
        elif self.state == 'draft':
            # Le client a peut-être validé sur son téléphone : la confirmation va suivre.
            self._set_pending()

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'hapiditpay' or len(tx) == 1:
            return tx

        reference = self._hapiditpay_odoo_reference(notification_data.get('reference'))
        if not reference:
            raise ValidationError("HapiditPay: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'hapiditpay')])
        if not tx:
            raise ValidationError(
                "HapiditPay: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != 'hapiditpay':
            return

        event = notification_data.get('evenement')
        if event == 'paiement.reussi':
            # Le montant et la devise doivent être ceux de la transaction.
            amount_ok = int(notification_data.get('montant') or -1) == int(round(self.amount))
            currency_ok = (notification_data.get('devise') or '').upper() == self.currency_id.name
            if not (amount_ok and currency_ok):
                _logger.warning(
                    "HapiditPay : montant ou devise différent pour %s (%s %s)",
                    self.reference, notification_data.get('montant'), notification_data.get('devise'),
                )
                self._set_pending(state_message=_(
                    "HapiditPay confirmed a payment of %s, which does not match this transaction. "
                    "Check it in your HapiditPay space.",
                    const.format_amount(notification_data.get('montant') or 0, notification_data.get('devise')),
                ))
                return

            # Une fois payé, la référence fournisseur devient le numéro de transaction HapiditPay.
            if notification_data.get('id'):
                self.provider_reference = notification_data['id']
            self._set_done()
        elif event == 'paiement.a_verifier':
            self._set_pending(state_message=_(
                "The operator did not answer clearly: HapiditPay is checking this payment. Do not "
                "deliver until it is confirmed."
            ))
        elif event in ('paiement.echoue', 'paiement.expire'):
            # Rien n'est débité, et le client peut réessayer sur la même page HapiditPay.
            _logger.info("HapiditPay : %s pour %s", event, self.reference)
        else:
            _logger.info("HapiditPay : événement %s ignoré pour %s", event, self.reference)
