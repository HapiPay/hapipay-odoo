# HapiPay pour Odoo. Licence LGPL-3.

import hashlib
import hmac
import json
import time
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_hapipay import const

MAKE_REQUEST = 'odoo.addons.payment_hapipay.models.payment_provider.PaymentProvider._hapipay_make_request'
SECRET = 'whsec_essai'


def signature(body, secret=SECRET, timestamp=None):
    timestamp = str(timestamp or int(time.time()))
    digest = hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return f't={timestamp},v1={digest}'


class HapiPayCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls._prepare_provider('hapipay', update_values={
            'hapipay_api_key': 'hpc_test_abcdefghijkl_' + 'x' * 40,
            'hapipay_webhook_secret': SECRET,
        })
        cls.currency = cls._prepare_currency('XAF')
        cls.amount = 25000
        cls.payment_method_id = cls.env.ref('payment_hapipay.payment_method_hapipay').id

    def _paid(self, tx, **values):
        return dict({
            'evenement': 'paiement.reussi',
            'reference': tx._hapipay_reference(),
            'id': 'TX123',
            'montant': 25000,
            'devise': 'XAF',
            'operateur': 'airtel',
        }, **values)


@tagged('post_install', '-at_install')
class TestHapiPay(HapiPayCommon):

    def test_signature(self):
        body = b'{"evenement":"paiement.reussi"}'
        now = int(time.time())
        self.assertTrue(const.valid_signature(signature(body), body, SECRET))
        self.assertFalse(const.valid_signature(signature(body), body, 'autre'))
        self.assertFalse(const.valid_signature(signature(body), body + b' ', SECRET))
        self.assertFalse(const.valid_signature(signature(body, timestamp=now - 600), body, SECRET))
        self.assertFalse(const.valid_signature('', body, SECRET))
        self.assertFalse(const.valid_signature(signature(body), body, ''))
        # Deux v1 après un changement de secret : l'un suffit.
        both = signature(body, 'nouveau') + ',v1=' + signature(body).split('v1=')[1]
        self.assertTrue(const.valid_signature(both, body, SECRET))

    def test_format_amount(self):
        self.assertEqual(const.format_amount(25000, 'XAF'), '25 000 FCFA')
        self.assertEqual(const.format_amount(5000, 'MGA'), '5 000 MGA')

    def test_reference_round_trip(self):
        tx = self._create_transaction(flow='redirect')
        hapipay_reference = tx._hapipay_reference()
        self.assertTrue(hapipay_reference.startswith('odoo-'))
        self.assertEqual(tx._hapipay_odoo_reference(hapipay_reference), tx.reference)
        self.assertIsNone(tx._hapipay_odoo_reference('ps-42'))
        self.assertIsNone(tx._hapipay_odoo_reference('odoo-zzzzzz-' + tx.reference))

    def test_rendering_values_create_the_page(self):
        tx = self._create_transaction(flow='redirect')
        with patch(MAKE_REQUEST, return_value={'url': 'https://pay.test/payer/abc', 'code': 'abc'}) as request:
            values = tx._get_specific_rendering_values(None)
        self.assertEqual(values, {'api_url': 'https://pay.test/payer/abc'})
        self.assertEqual(tx.provider_reference, 'abc')
        method, endpoint, payload = request.call_args.args
        self.assertEqual((method, endpoint), ('POST', 'liens'))
        self.assertEqual(payload['montant'], 25000)
        self.assertEqual(payload['devise'], 'XAF')
        self.assertTrue(payload['usage_unique'])
        self.assertEqual(payload['reference'], tx._hapipay_reference())
        self.assertIn('/payment/hapipay/return?reference=', payload['url_retour'])

    def test_amount_with_cents_is_refused(self):
        # En FCFA, Odoo arrondit déjà à l'unité : seuls l'euro et le dollar ont des centimes.
        euro = self._prepare_currency('EUR')
        tx = self._create_transaction(flow='redirect', amount=1111.5, currency_id=euro.id)
        with patch(MAKE_REQUEST) as request, self.assertRaises(ValidationError):
            tx._get_specific_rendering_values(None)
        request.assert_not_called()

    def test_paid_notification_confirms(self):
        tx = self._create_transaction(flow='redirect')
        tx._handle_notification_data('hapipay', self._paid(tx))
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, 'TX123')

    @mute_logger('odoo.addons.payment_hapipay.models.payment_transaction')
    def test_other_amount_stays_pending(self):
        tx = self._create_transaction(flow='redirect')
        tx._handle_notification_data('hapipay', self._paid(tx, montant=24000))
        self.assertEqual(tx.state, 'pending')
        self.assertIn('24', tx.state_message)

    def test_payment_to_check_stays_pending(self):
        tx = self._create_transaction(flow='redirect')
        tx._handle_notification_data('hapipay', self._paid(tx, evenement='paiement.a_verifier'))
        self.assertEqual(tx.state, 'pending')

    def test_failed_payment_keeps_the_transaction_open(self):
        tx = self._create_transaction(flow='redirect')
        tx._handle_notification_data('hapipay', self._paid(tx, evenement='paiement.echoue'))
        self.assertEqual(tx.state, 'draft')

    def test_return_asks_hapipay(self):
        tx = self._create_transaction(flow='redirect', provider_reference='abc')
        link = {'etat': 'paye', 'reference': tx._hapipay_reference(), 'paiement': 'TX9', 'montant': 25000, 'devise': 'XAF'}
        with patch(MAKE_REQUEST, return_value=link):
            tx._hapipay_check_link_state()
        self.assertEqual(tx.state, 'done')

    def test_return_before_payment_sets_pending(self):
        tx = self._create_transaction(flow='redirect', provider_reference='abc')
        with patch(MAKE_REQUEST, return_value={'etat': 'ouvert'}):
            tx._hapipay_check_link_state()
        self.assertEqual(tx.state, 'pending')

    def test_no_validation_operation(self):
        providers = self.env['payment.provider']._get_compatible_providers(
            self.company.id, self.partner.id, 0., is_validation=True
        )
        self.assertNotIn(self.provider, providers)


@tagged('post_install', '-at_install')
class TestHapiPayWebhook(HapiPayCommon, PaymentHttpCommon):

    def _post(self, body, header):
        return self.url_open(
            '/payment/hapipay/webhook', data=body,
            headers={'Content-Type': 'application/json', 'HapiPay-Signature': header},
        )

    @mute_logger('odoo.addons.payment_hapipay.controllers.main')
    def test_forged_webhook_is_refused(self):
        tx = self._create_transaction(flow='redirect')
        body = json.dumps({'evenement': 'paiement.reussi', 'data': self._paid(tx)}).encode()
        response = self._post(body, signature(body, 'faux'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(tx.state, 'draft')

    def test_signed_webhook_confirms(self):
        tx = self._create_transaction(flow='redirect')
        data = self._paid(tx)
        data.pop('evenement')
        body = json.dumps({'evenement': 'paiement.reussi', 'data': data}).encode()
        response = self._post(body, signature(body))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')

    def test_foreign_reference_is_acknowledged(self):
        body = json.dumps({'evenement': 'paiement.reussi', 'data': {'reference': 'ps-42'}}).encode()
        response = self._post(body, signature(body))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ignore': True})
