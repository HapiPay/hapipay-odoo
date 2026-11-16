# HapiPay pour Odoo. Licence LGPL-3.

{
    'name': "Payment Provider: HapiPay",
    'version': '19.0.0.1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Mobile money, card and PayPal payments with HapiPay. The money goes straight to "
               "your own operator account.",
    'description': " ",  # Chaîne non vide : Odoo ne charge pas le README.
    'author': "HapiPay",
    'website': "https://github.com/HapiPay/hapipay-odoo",
    'depends': ['payment'],
    'data': [
        'views/payment_hapipay_templates.xml',
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
