-- Copie neutralisée d'une base (essais) : clés HapiditPay retirées.
UPDATE payment_provider
   SET hapiditpay_api_key = NULL,
       hapiditpay_webhook_secret = NULL;
