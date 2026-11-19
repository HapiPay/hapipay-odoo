# HapiditPay pour Odoo. Licence LGPL-3.

import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.const import REPORT_REASONS_MAPPING
from odoo.addons.payment_hapiditpay import const


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('hapiditpay', "HapiditPay")], ondelete={'hapiditpay': 'set default'}
    )
    hapiditpay_api_url = fields.Char(
        string="HapiditPay API address",
        help="Leave empty to use https://hapiditpay.com/api/v1. The address must be HTTPS: "
             "a redirected address is refused.",
    )
    hapiditpay_api_key = fields.Char(
        string="HapiditPay API key",
        help="Created in your HapiditPay space, Developers > API keys. An hdp_test_ key simulates "
             "payments; an hdp_ key collects real money.",
        required_if_provider='hapiditpay',
        groups='base.group_system',
    )
    hapiditpay_webhook_secret = fields.Char(
        string="HapiditPay webhook secret",
        help="In your HapiditPay space, Developers > Webhooks, add the webhook address shown here, "
             "then copy its secret.",
        required_if_provider='hapiditpay',
        groups='base.group_system',
    )
    hapiditpay_webhook_url = fields.Char(
        string="HapiditPay webhook address", compute='_compute_hapiditpay_webhook_url',
    )

    # === CALCULS === #

    def _compute_hapiditpay_webhook_url(self):
        for provider in self:
            provider.hapiditpay_webhook_url = provider.get_base_url().rstrip('/') + '/payment/hapiditpay/webhook'

    # === MÉTHODES MÉTIER === #

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, report=None, **kwargs):
        """ HapiditPay n'enregistre pas de moyen de paiement : pas d'opération de validation. """
        providers = super()._get_compatible_providers(
            *args, is_validation=is_validation, report=report, **kwargs
        )
        if is_validation:
            unfiltered_providers = providers
            providers = providers.filtered(lambda p: p.code != 'hapiditpay')
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=REPORT_REASONS_MAPPING['validation_not_supported'],
            )
        return providers

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'hapiditpay':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'hapiditpay':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _hapiditpay_base_url(self):
        url = (self.hapiditpay_api_url or '').strip() or const.DEFAULT_API_URL
        return url.rstrip('/')

    def _hapiditpay_site_url(self, path=''):
        """ Page du site HapiditPay (inscription, espace), déduite de l'adresse de l'API. """
        root = re.sub(r'/api/v\d+$', '', self._hapiditpay_base_url())
        return root + ('/' + path.lstrip('/') if path else '')

    def _hapiditpay_is_test(self):
        return (self.sudo().hapiditpay_api_key or '').startswith('hdp_test_')

    def _hapiditpay_make_request(self, method, endpoint, payload=None):
        """ Appel à l'API HapiditPay. Renvoie les données (`data`) de la réponse.

        Note: self.ensure_one()

        :raise ValidationError: si HapiditPay est injoignable ou refuse la demande.
        """
        self.ensure_one()
        url = self._hapiditpay_base_url() + '/' + endpoint.lstrip('/')
        headers = {
            'Authorization': f'Bearer {self.sudo().hapiditpay_api_key or ""}',
            'Accept': 'application/json',
            'User-Agent': f'HapiditPay-Odoo/{const.VERSION}',
        }
        try:
            # Jamais de redirection suivie : la clé ne part pas ailleurs que là où elle est envoyée.
            response = requests.request(
                method, url, json=payload, headers=headers, timeout=20, allow_redirects=False
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("HapiditPay injoignable : %s", url)
            raise ValidationError("HapiditPay: " + _("Could not establish the connection to the API."))

        if 300 <= response.status_code < 400:
            raise ValidationError("HapiditPay: " + _(
                "The API answered with a redirection (%(status)s): check the API address, in "
                "HTTPS, for example %(url)s.", status=response.status_code, url=const.DEFAULT_API_URL,
            ))

        try:
            content = response.json()
        except ValueError:
            content = {}

        if not response.ok:
            message = content.get('message') if isinstance(content, dict) else None
            _logger.warning("HapiditPay a répondu %s à %s %s : %s", response.status_code, method, url, message)
            raise ValidationError("HapiditPay: " + (message or _("The API answered %s.", response.status_code)))

        return content.get('data', {}) if isinstance(content, dict) else {}

    def action_hapiditpay_check_key(self):
        """ Bouton « Vérifier la clé » : demande à HapiditPay quel compte ouvre la clé. """
        self.ensure_one()
        try:
            account = self._hapiditpay_make_request('GET', 'plateforme')
        except ValidationError as error:
            reason = str(error.args[0]).removeprefix("HapiditPay: ")
            return self._hapiditpay_notify(_("The key could not be checked: %s", reason), 'danger')

        mode = _("test (simulated payments)") if self._hapiditpay_is_test() else _("live")
        return self._hapiditpay_notify(
            _("Key recognised for \"%(name)s\", in %(mode)s mode.", name=account.get('name', '?'), mode=mode),
            'success',
        )

    def _hapiditpay_notify(self, message, kind):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': "HapiditPay", 'message': message, 'type': kind, 'sticky': False},
        }
