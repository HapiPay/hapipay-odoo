# HapiditPay pour Odoo

Fournisseur de paiement Odoo pour encaisser par mobile money, carte bancaire et PayPal avec HapiditPay : factures et devis payés en ligne depuis le portail client. La boutique en ligne (Site web) utilise le même formulaire de paiement d'Odoo, mais n'a pas encore été essayée. L'argent va directement du client au compte opérateur de l'entreprise : HapiditPay ne le touche jamais.

Une branche par version d'Odoo, comme pour les modules d'Odoo : `18.0` et `19.0`.

## Fonctionnement

1. Le client choisit « HapiditPay (mobile money) » parmi les moyens de paiement d'Odoo (bouton « Payer maintenant » d'une facture, paiement d'un devis, caisse de la boutique).
2. Le module crée une page de paiement HapiditPay à usage unique (`POST /api/v1/liens`) : référence `odoo-<base>-<référence Odoo>`, montant, devise, adresse de retour. Puis il y envoie le client.
3. Le client paie sur la page HapiditPay, puis revient sur Odoo (`/payment/hapiditpay/return`), qui affiche l'état du paiement.
4. HapiditPay envoie le webhook signé `paiement.reussi` à `/payment/hapiditpay/webhook`. Le module vérifie la signature, le montant et la devise, puis confirme la transaction : Odoo crée le paiement et lettre la facture, ou confirme la commande. Le numéro de transaction HapiditPay devient la référence du fournisseur.
5. Si le webhook n'est pas encore arrivé au retour du client, le module demande l'état de la page à HapiditPay.

Un paiement d'un montant ou d'une devise différente n'est pas confirmé : Odoo 19 passe la transaction en erreur (contrôle d'Odoo lui-même), Odoo 18 la laisse « En attente » avec un message. Un paiement « à vérifier » aussi. Un paiement échoué laisse la transaction ouverte : le client peut réessayer sur la même page HapiditPay. Les références d'une autre boutique branchée sur le même compte HapiditPay sont ignorées.

Aucun secret dans ce dépôt : chaque entreprise saisit sa propre clé d'API et le secret de son webhook.

## Installation

Odoo installé chez vous, chez un intégrateur ou sur Odoo.sh. Odoo Online (l'offre hébergée par Odoo SA) n'accepte pas les modules extérieurs.

1. Téléchargez l'archive de votre version d'Odoo depuis les [versions publiées](https://github.com/HapiditPay/hapiditpay-odoo/releases), et décompressez le dossier `payment_hapiditpay` dans un dossier de modules d'Odoo (`addons_path`).
2. Mettez à jour la liste des applications, puis installez « Payment Provider: HapiditPay ».
3. Facturation (ou Ventes, ou Site web) → Configuration → Fournisseurs de paiement → HapiditPay :
   - **Clé d'API** : `hdp_test_…` pour les essais (avec l'état « Mode test »), `hdp_…` pour encaisser (avec l'état « Activé »).
   - **Secret du webhook** : déclarez dans votre espace HapiditPay (Développeurs → Webhooks) l'adresse du webhook affichée, puis copiez son secret.
   - **Adresse de l'API** : laissez vide pour `https://hapiditpay.com/api/v1`.
   - « Vérifier la clé » confirme le compte HapiditPay et le mode.
4. Publiez le fournisseur.

La devise doit être le franc CFA (XAF, XOF), l'ariary (MGA), le franc congolais (CDF), l'euro ou le dollar. HapiditPay encaisse des montants entiers.

## Essais

Testé de bout en bout avec une instance HapiditPay locale, en mode test :

- **Odoo 19** : facture payée depuis le portail client (paiement créé, facture lettrée), devis accepté et payé en ligne (commande confirmée), faux webhook refusé (401), webhook rejoué sans second paiement, référence d'une autre boutique ignorée.
- **Odoo 18** : facture payée depuis le portail client, faux webhook refusé, webhook rejoué sans second paiement, montant différent laissé en attente, référence d'une autre boutique ignorée, clé vérifiée depuis la fiche du fournisseur.

Les tests du module passent sur les deux versions avec la 0.1.0 : `odoo -i payment_hapiditpay --test-enable --test-tags /payment_hapiditpay`. Les versions 0.2.0 et 0.2.1 n'ont pas encore été rejouées dans Odoo : syntaxe Python et XML vérifiées seulement.

## Versions

Le numéro d'Odoo précède celui du module : `19.0.0.2.1` et `18.0.0.2.1` sont la version 0.2.1 pour Odoo 19 et Odoo 18.

- **0.2.1** : retrait du code de reprise des réglages d'une version antérieure : une installation précédente se reconfigure depuis la page de réglages.
- **0.2.0** : changement de nom : le module s'appelle désormais HapiditPay. Module `payment_hapiditpay`, fournisseur et moyen de paiement de code `hapiditpay`, champs `hapiditpay_*`, adresses `/payment/hapiditpay/return` et `/payment/hapiditpay/webhook`, en-tête de webhook `HapiditPay-Signature`, clés d'API `hdp_…` et `hdp_test_…`, service sur `https://hapiditpay.com`.
- **0.1.0** : première version. Factures et devis payés depuis le portail client ; Odoo 18 et Odoo 19.

## Licence

LGPL-3.
