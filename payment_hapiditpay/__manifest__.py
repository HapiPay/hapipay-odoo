# HapiditPay pour Odoo. Licence LGPL-3.

{
    'name': "Payment Provider: HapiditPay",
    'version': '18.0.0.2.1',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Mobile money, card and PayPal payments with HapiditPay. The money goes straight to "
               "your own operator account.",
    'description': " ",  # Chaîne non vide : Odoo ne charge pas le README.
    'author': "Hapidit Group",
    'website': "https://github.com/HapiditPay/hapiditpay-odoo",
    'depends': ['payment'],
    'data': [
        'views/payment_hapiditpay_templates.xml',
        'views/payment_provider_views.xml',

        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'images': ['static/description/icon.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'external_dependencies': {'python': ['requests']},
    'installable': True,
    'license': 'LGPL-3',
}
