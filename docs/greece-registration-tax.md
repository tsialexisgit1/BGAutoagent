# Taxe d'immatriculation grecque — première approximation

**Établi le :** 6 août 2026
**Statut :** approximation de travail, issue de sources secondaires accessibles.
**À remplacer par** les tables officielles de l'ΑΑΔΕ, chargées manuellement.

> Ce document sert à **tester le moteur de calcul**, pas à décider d'un achat.
> Aucune ligne marquée `?` ne doit entrer dans une décision.

## Légende de fiabilité

| Marque | Sens | Utilisable pour décider ? |
|---|---|---|
| ✓ | Vérifié — source officielle, avec date | Oui |
| ~ | Estimé — source secondaire crédible ou échantillon réel partiel | Oui, avec la marge de sécurité |
| ? | Indicatif — ordre de grandeur non vérifié | **Non — affichage seulement** |
| ✗ | Manquant — identifié, à collecter | — |

---

## Structure de la taxe

La taxe d'immatriculation (*τέλος ταξινόμησης*) se calcule en trois temps :

1. Une **valeur taxable**, construite à partir du prix d'achat, de l'assurance et du transport
2. Un **taux de base**, fonction de la cylindrée et de la norme Euro
3. Des **ajustements**, selon les émissions de CO₂, puis une **dépréciation** selon l'âge du véhicule

| Élément | Valeur | Fiabilité |
|---|---|---|
| Assiette | prix d'achat + assurance + transport | ~ |
| Taux de base | table par cylindrée × norme Euro | ✗ **manquant** |
| Ajustement CO₂ | voir table ci-dessous | ~ |
| Dépréciation par âge | table officielle | ✗ **manquant — le plus critique** |
| Charge totale, essence/diesel | 30 à 50 % de la valeur du véhicule | ? |
| TVA | 24 % ; véhicule d'occasion UE avec TVA déjà acquittée : non redue en principe | ~ |

## Ajustement CO₂ — véhicules immatriculés dans l'UE depuis 2021 (WLTP)

| Émissions CO₂ (g/km) | Effet sur le taux | Fiabilité |
|---|---|---|
| ≤ 130 | −5 % | ~ |
| > 156 et ≤ 182 | +10 % | ~ |
| > 182 et ≤ 208 | +20 % | ~ |
| > 208 et ≤ 234 | +30 % | ~ |
| > 234 et ≤ 260 | +40 % | ~ |
| > 260 et ≤ 325 | +60 % | ~ |
| > 325 | +100 % | ~ |

La tranche entre 130 et 156 g/km n'apparaît pas dans les sources consultées — vraisemblablement neutre, à confirmer. ✗

## Hybrides — changement de régime au 1er janvier 2027

| Période | Régime | Fiabilité |
|---|---|---|
| Jusqu'au **31/12/2026** | Réduction de **75 %** pour les hybrides ≤ 50 g CO₂/km | ~ |
| À partir du **01/01/2027** | Réduction **uniforme de 50 %** pour tous les hybrides | ~ |
| Transitoire | 75 % maintenus pour ≤ 75 g, importés entre le 01/11/2025 et le 31/05/2026 — **fenêtre fermée** | ~ |

**Conséquence directe :** la taxe des hybrides les plus sobres **double** au 1er janvier 2027.
Il reste environ cinq mois sous le régime favorable à la date d'établissement de ce document.

C'est le cas d'école qui impose de calculer la taxe **à la date d'immatriculation prévue**
et non à la date d'achat, et d'alerter lorsqu'une opération chevauche l'échéance.

## Ce qui manque, par ordre d'importance

1. **La table de dépréciation par âge** ✗ — sans elle, aucun calcul sur de l'occasion n'est possible. C'est le premier document à récupérer.
2. **La table des taux de base** (cylindrée × norme Euro) ✗
3. La tranche CO₂ 130–156 g/km ✗
4. Le traitement exact de la TVA sur l'occasion intracommunautaire selon le régime du vendeur — marge ou TVA déductible ✗

## Pourquoi ces tables sont absentes

Le site de l'ΑΑΔΕ, y compris ses PDF, renvoie un **403** aux requêtes automatisées
(vérifié le 6 août 2026 sur `/en/customs/motor-vehicles-taxation` et sur
`CAR_TAXATION_Feb_2016.pdf`). Le guide d'importation d'eCarsTrade décrit la structure
sans publier un seul barème.

Ce blocage n'est pas un obstacle mais une confirmation : **ces tables doivent être
récupérées par un humain et chargées dans l'application**, datées et versionnées.
Sur une donnée qui engage plusieurs milliers d'euros par véhicule, la vérification
humaine vaut son coût, et elle ne casse pas quand le site est redessiné.

## Sources consultées

- [ΑΑΔΕ — Motor Vehicles Taxation](https://www.aade.gr/en/customs/motor-vehicles-taxation) — 403 sur requête automatisée
- [ΑΑΔΕ — Registration fees](https://www.aade.gr/en/greeks-abroad-non-residents/private-passenger-vehicles/registration-fees-immobility-vehicles)
- [Athens Times — hausse de la taxe hybride en 2027](https://athens-times.com/hybrid-cars-registration-tax-to-double-from-2027-who-will-pay-more/)
- [eCarsTrade — importer une voiture en Grèce](https://ecarstrade.com/blog/how-to-import-a-car-to-greece)
- [ExpatLaw — importer et immatriculer une occasion en Grèce](https://www.expatlaw.gr/post/import-register-used-car-greece)
