---
# Copier vers forward/fiches/fiche_AAAA-MM-JJ_NN.md (date du jour, NN = 01, 02…), remplir,
# puis le jour même : python forward/enregistrer.py forward/fiches/fiche_AAAA-MM-JJ_NN.md
# Une fiche enregistrée est figée (registre de hash) : toute correction passe par une
# nouvelle fiche dont le champ « remplace » donne l'id de l'ancienne.
id: AAAA-MM-JJ_NN            # nom du fichier sans « fiche_ » ni « .md »
date: AAAA-MM-JJ             # jour d'enregistrement = J0 (refusé s'il diffère du jour même)
semaine:                     # 1 à 12, comptée depuis le 2026-10-01
remplace:                    # id de la fiche corrigée, sinon vide

probleme:
  id:                        # P-NN, commun aux fiches des solutions concurrentes d'un même problème
  origine:                   # collecte (forums, inbox X) | derivation (limite d'un gagnant, addendum 01)
  gagnant_reference:         # si derivation : protocole gagnant (forward/gagnants/AAAA-MM-JJ.md)
  gagnant_slug_defillama:    # si derivation : son slug DefiLlama
  enonce:                    # une phrase
  sources:                   # au moins 3, datées et distinctes
    - {date: , url: , qui: }
    - {date: , url: , qui: }
    - {date: , url: , qui: }
  premiere_mention: {date: , url: }
  qui_le_subit:
  argent_en_jeu_usd:
  methode_estimation:        # comment l'argent en jeu est estimé

solution:
  nom:
  lien:
  stade:                     # pre_token | token_cote
  date_lancement:            # AAAA-MM-JJ
  id_coingecko:              # obligatoire si token_cote
  distribution:              # accès aux utilisateurs en une ligne : écosystème, exchange, partenariats

metrique:                    # une seule, gratuite sur DefiLlama ; tout vide = fiche hors Q1
  nature:                    # tvl | volume_dex | frais
  slug_defillama:            # slug du protocole ; « chain:Nom » pour la TVL d'une chaîne
  valeur_j0:                 # en dollars : TVL du jour, ou moyenne des 7 derniers jours pour volume et frais

part_captee_pct:             # part du problème captée par la solution, estimée (0 à 100)

adequation:                  # forte | moyenne | faible
justification_adequation:    # 3 lignes
  -
  -
  -
conviction:                  # haute | basse

position:
  type:                      # achat_papier si adéquation forte + conviction haute + token coté ;
                             # suivi_pre_token si pré-token ; aucune sinon
  token:                     # id CoinGecko, si achat_papier
  prix_j0:                   # indicatif : l'évaluation retient la clôture CoinGecko de J0
condition_invalidation:      # seule cause de sortie d'une position papier avant l'horizon
changerait_avis:
---

Notes libres (non évaluées).
