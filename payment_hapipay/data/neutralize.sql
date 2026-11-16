-- Copie neutralisée d'une base (essais) : clés HapiPay retirées.
UPDATE payment_provider
   SET hapipay_api_key = NULL,
       hapipay_webhook_secret = NULL;
