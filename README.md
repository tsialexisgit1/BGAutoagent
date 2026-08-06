# BG Auto Agent

Trouve des véhicules rentables à acheter en Belgique pour les revendre en Grèce.
L'objectif n'est pas la marge unitaire mais le **rendement annuel du capital** :
mieux vaut 3 000 € en dix jours que 5 000 € en soixante.

Le système ne répond qu'à une question : **acheter, oui ou non.**

## Démarrer

```bash
python3 -m unittest discover -s tests    # 38 tests
PYTHONPATH=src python3 -m bgautoagent.app  # → http://localhost:8765
```

Aucune dépendance à installer. Python 3.9 suffit.

## La thèse, en une commande

```bash
python3 examples/thesis.py
```

Classe les mêmes voitures deux fois — par marge, puis par rendement annuel — et
montre que l'ordre change. C'est la raison d'être du produit, et un test échoue
si l'inversion cesse d'être possible.

## Ce qui est construit

| Module | Rôle |
|---|---|
| `money.py` | `Decimal` partout ; `euro()` refuse un `float` |
| `reliability.py` | Marques ✓ ~ ? ✗, plancher, et le verrou décisionnel |
| `vehicle.py` | Le véhicule, sa carrosserie, sa source B2B/C2C |
| `greek_tax.py` | Taxe grecque, datée, avec la table de dépréciation |
| `financials.py` | Coût de revient, marges, ROI, rendement du capital |
| `scoring.py` | BG Score, cinq composantes, poids ajustables |
| `decision.py` | Le verdict et ses deux verrous |
| `app.py` | Saisie manuelle et les deux classements |

## Trois principes

**Zéro dépendance dans le moteur.** Du code qui engage des milliers d'euros par
véhicule doit être lisible en entier et reproductible dans cinq ans. La collecte
et l'interface auront des dépendances ; le moteur, non.

**Le LLM n'est pas dans le chemin de décision.** Il lit du texte libre — un
historique, un rapport d'expertise — et produit une donnée *marquée* qui entre
dans le moteur. Il ne calcule jamais, il ne décide jamais. Un pipeline, pas des
agents : les étapes sont connues d'avance, il n'y a rien à explorer.

**Le moteur refuse de décider sur une donnée qu'il sait fausse.** Chaque entrée
porte sa fiabilité ; si le plancher tombe sous `~ ESTIMÉ`, le verdict sort
`NON DÉCISIONNEL` quel que soit le score. Sans cette règle, la légende de
fiabilité serait décorative.

## Ce qui est encore faux, et volontairement visible

- Le **taux de base** de la taxe grecque est un curseur provisoire à 35 %, faute
  de la table officielle par cylindrée et norme Euro.
- La **dépréciation kilométrique** manque — un véhicule très kilométré est
  surtaxé par l'approximation actuelle.
- La **valeur de référence grecque** est dérivée du prix de marché par un ratio
  provisoire.

Conséquence assumée : par défaut, **aucun verdict n'est décisionnel.** Le moteur
calcule, affiche, se laisse tester — et ne dit pas ACHETER tant que ces trois
trous ne sont pas comblés.

Détail et sources : [`docs/greece-registration-tax.md`](docs/greece-registration-tax.md)

## Prochaines étapes

1. Récupérer les tables officielles de l'ΑΑΔΕ (taux de base, kilométrage)
2. Confirmer que la table de dépréciation de 2017 est toujours en vigueur
3. Amorcer l'historisation du marché grec — c'est le seul retard qui ne se
   rattrape pas à l'argent
4. Négocier l'accès aux plateformes B2B (eCarsTrade, Autorola, Auto1, Ayvens)

## Attention particulière

**Échéance fiscale au 1er janvier 2027** : la réduction de taxe des hybrides
sobres passe de 75 % à 50 %, soit un doublement de la taxe. Le moteur calcule à
la date d'immatriculation prévue et alerte quand une affaire chevauche
l'échéance.

**2ememain** est identifiée comme source mais reste à valider juridiquement —
conditions d'utilisation, droit des bases de données, données de vendeurs
particuliers. Décision à prendre avec un juriste, pas avec un développeur.
