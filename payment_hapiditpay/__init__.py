# HapiditPay pour Odoo. Licence LGPL-3.

import logging

from odoo.tools.sql import column_exists

from . import controllers
from . import models

from odoo.addons.payment import setup_provider, reset_payment_provider


_logger = logging.getLogger(__name__)

# Code du fournisseur de l'ancien module (payment_hapipay, versions 0.1.x),
# dont les réglages sont repris à l'installation de ce module.
PREVIOUS_CODE = 'hapipay'


def post_init_hook(env):
    setup_provider(env, 'hapiditpay')
    _take_over_previous_provider(env)


def uninstall_hook(env):
    reset_payment_provider(env, 'hapiditpay')


def _take_over_previous_provider(env):
    """ Reprise des réglages de l'ancien module payment_hapipay, s'il est encore installé.

    Odoo ne sait pas renommer un module : payment_hapiditpay s'installe à côté de
    l'ancien, puis l'ancien est désinstallé (voir le README). Ici, pour chaque
    fournisseur de l'ancien module, celui de ce module dans la même société reçoit
    l'adresse de l'API, la clé, le secret du webhook, l'état et la publication ;
    l'ancien fournisseur est ensuite désactivé et dépublié, pour que le client ne
    voie qu'un seul moyen de paiement. Un fournisseur déjà configuré n'est pas
    touché. Sans ancien module (colonnes absentes), rien n'est fait.
    """
    cr = env.cr
    old_columns = [f'{PREVIOUS_CODE}_api_url', f'{PREVIOUS_CODE}_api_key', f'{PREVIOUS_CODE}_webhook_secret']
    if not all(column_exists(cr, 'payment_provider', column) for column in old_columns):
        return

    # Colonnes lues en SQL : elles appartiennent à l'ancien module.
    cr.execute(
        f"SELECT id, company_id, state, is_published, {', '.join(old_columns)}"
        " FROM payment_provider WHERE code = %s ORDER BY id",
        [PREVIOUS_CODE],
    )
    Provider = env['payment.provider'].sudo()
    for old_id, company_id, state, is_published, api_url, api_key, webhook_secret in cr.fetchall():
        provider = Provider.search([('code', '=', 'hapiditpay'), ('company_id', '=', company_id)], limit=1)
        if not provider:
            _logger.warning(
                "HapiditPay : pas de fournisseur pour la société %s, réglages du fournisseur %s "
                "à reprendre à la main", company_id, old_id,
            )
            continue
        if provider.hapiditpay_api_key:
            continue

        values = {
            'hapiditpay_api_url': api_url,
            'hapiditpay_api_key': api_key,
            'hapiditpay_webhook_secret': webhook_secret,
        }
        if api_key and webhook_secret and state in ('enabled', 'test'):
            values.update(state=state, is_published=bool(is_published))
        provider.write(values)

        cr.execute(
            "UPDATE payment_provider SET state = 'disabled', is_published = false WHERE id = %s",
            [old_id],
        )
        _logger.info(
            "HapiditPay : réglages du fournisseur %s repris dans le fournisseur %s (état %s)",
            old_id, provider.id, provider.state,
        )
    Provider.invalidate_model(['state', 'is_published'])
