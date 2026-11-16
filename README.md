# HapiPay pour Odoo

Fournisseur de paiement Odoo pour encaisser par mobile money, carte bancaire et PayPal avec HapiPay : factures payées depuis le portail client, devis et boutique en ligne. L'argent va directement du client au compte opérateur de l'entreprise : HapiPay ne le touche jamais.

Une branche par version d'Odoo, comme pour les modules d'Odoo : `18.0` et `19.0`.

## Fonctionnement

1. Le client choisit « HapiPay (mobile money) » parmi les moyens de paiement d'Odoo (bouton « Payer maintenant » d'une facture, paiement d'un devis, caisse de la boutique).
2. Le module crée une page de paiement HapiPay à usage unique (`POST /api/v1/liens`) : référence `odoo-<base>-<référence Odoo>`, montant, devise, adresse de retour. Puis il y envoie le client.
3. Le client paie sur la page HapiPay, puis revient sur Odoo (`/payment/hapipay/return`), qui affiche l'état du paiement.
4. HapiPay envoie le webhook signé `paiement.reussi` à `/payment/hapipay/webhook`. Le module vérifie la signature, le montant et la devise, puis confirme la transaction : Odoo crée le paiement et lettre la facture, ou confirme la commande. Le numéro de transaction HapiPay devient la référence du fournisseur.
5. Si le webhook n'est pas encore arrivé au retour du client, le module demande l'état de la page à HapiPay.

Un paiement d'un montant ou d'une devise différente laisse la transaction « En attente », avec un message. Un paiement « à vérifier » aussi. Un paiement échoué laisse la transaction ouverte : le client peut réessayer sur la même page HapiPay. Les références d'une autre boutique branchée sur le même compte HapiPay sont ignorées.

Aucun secret dans ce dépôt : chaque entreprise saisit sa propre clé d'API et le secret de son webhook.

## Installation

Odoo installé chez vous, chez un intégrateur ou sur Odoo.sh. Odoo Online (l'offre hébergée par Odoo SA) n'accepte pas les modules extérieurs.

1. Téléchargez l'archive de votre version d'Odoo depuis les [versions publiées](https://github.com/HapiPay/hapipay-odoo/releases), et décompressez le dossier `payment_hapipay` dans un dossier de modules d'Odoo (`addons_path`).
2. Mettez à jour la liste des applications, puis installez « Payment Provider: HapiPay ».
3. Facturation (ou Ventes, ou Site web) → Configuration → Fournisseurs de paiement → HapiPay :
   - **Clé d'API** : `hpc_test_…` pour les essais (avec l'état « Mode test »), `hpc_…` pour encaisser (avec l'état « Activé »).
   - **Secret du webhook** : déclarez dans votre espace HapiPay (Développeurs → Webhooks) l'adresse du webhook affichée, puis copiez son secret.
   - **Adresse de l'API** : laissez vide pour `https://pay.scigroup.td/api/v1`.
   - « Vérifier la clé » confirme le compte HapiPay et le mode.
4. Publiez le fournisseur.

La devise doit être le franc CFA (XAF, XOF), l'ariary (MGA), le franc congolais (CDF), l'euro ou le dollar. HapiPay encaisse des montants entiers.

## Essais

Testé de bout en bout avec Odoo 18 et une instance HapiPay locale, en mode test : facture payée depuis le portail client (transaction confirmée, paiement créé et facture lettrée), webhook signé reçu, faux webhook refusé (401), webhook rejoué sans second paiement, montant différent laissé en attente, référence d'une autre boutique ignorée, clé vérifiée depuis la fiche du fournisseur. Les tests du module (`--test-tags /payment_hapipay`) passent.

## Licence

LGPL-3.
