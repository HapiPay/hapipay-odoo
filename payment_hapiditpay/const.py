# HapiditPay pour Odoo. Licence LGPL-3.

import hashlib
import hmac
import time

# Adresse de l'API de production, utilisée quand le réglage est vide.
DEFAULT_API_URL = 'https://hapiditpay.com/api/v1'

# Version du module, envoyée dans l'en-tête User-Agent.
VERSION = '0.2.0'

# Devises des pages HapiditPay : celles des pays servis (FCFA, ariary, francs
# congolais), plus l'euro et le dollar. Montants entiers seulement.
SUPPORTED_CURRENCIES = ['XAF', 'XOF', 'MGA', 'CDF', 'EUR', 'USD']

# Langues de la page HapiditPay.
LANGUAGES = ['fr', 'en', 'ar', 'mg', 'es']

# Moyen de paiement créé par le module, activé avec HapiditPay.
DEFAULT_PAYMENT_METHOD_CODES = {'hapiditpay'}

# Préfixe des références envoyées à HapiditPay : un même compte HapiditPay peut
# servir une boutique et un Odoo sans que leurs références se mêlent.
REFERENCE_PREFIX = 'odoo-'

# Tolérance sur l'horodatage des webhooks, en secondes.
SIGNATURE_TOLERANCE = 300


def valid_signature(header, raw_body, secret, tolerance=SIGNATURE_TOLERANCE, now=None):
    """Vérifie l'en-tête HapiditPay-Signature : t=<horodatage>,v1=<hmac>[,v1=<hmac>].

    Deux v1 pendant les 24 h qui suivent un changement de secret : l'un suffit.

    :param str header: valeur de l'en-tête HapiditPay-Signature
    :param bytes raw_body: corps brut de la requête
    :param str secret: secret du webhook
    :rtype: bool
    """
    if not secret or not header:
        return False

    timestamp = None
    signatures = []
    for part in header.split(','):
        key, sep, value = part.strip().partition('=')
        if not sep:
            continue
        if key == 't':
            timestamp = value
        elif key == 'v1':
            signatures.append(value)

    if timestamp is None or not timestamp.isdigit():
        return False
    if abs((now if now is not None else time.time()) - int(timestamp)) > tolerance:
        return False

    if isinstance(raw_body, str):
        raw_body = raw_body.encode()
    expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + raw_body, hashlib.sha256).hexdigest()

    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def format_amount(amount, currency):
    """Montant écrit pour une personne : « 25 000 FCFA » pour XAF et XOF."""
    currency = (currency or '').upper()
    label = 'FCFA' if currency in ('XAF', 'XOF') else currency
    return f"{int(amount):,}".replace(',', ' ') + ' ' + label
