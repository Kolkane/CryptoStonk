PROTOCOLE FORWARD v1, figé au commit de ce fichier.

Objet : tester la thèse centrale de CryptoStonk, non testée par la phase backtest : repérer les problèmes que le marché fait remonter, les solutions qui s'y positionnent, juger leur adéquation (taille du problème, part captée par la solution) et se positionner en avance.

Production
- 12 semaines de rituel à partir de la date de ce commit. Objectif : 2 fiches par semaine.
- Pour chaque problème retenu, une fiche par solution concurrente quand il en existe plusieurs.
- Solutions pré-token : suivies pour Q1 uniquement. Si leur token sort pendant le test, son parcours est noté à titre descriptif, hors verdict.

Règles
- Une fiche est figée à son enregistrement (registre de hash). Toute correction passe par une nouvelle fiche qui référence l'ancienne.
- Chaque semaine est journalisée, même vide. 3 semaines manquées sur 12 : test déclaré invalide.
- Métrique d'adoption : une seule par fiche, mesurable gratuitement sur DefiLlama (TVL, volume DEX ou frais), déclarée dans la fiche avec sa valeur à J0. Sans métrique mesurable, la fiche ne compte pas pour Q1.
- Positions papier uniquement : entrée au prix de clôture du jour d'enregistrement, aucune sortie hors condition d'invalidation écrite dans la fiche. Aucun capital réel engagé sur la base de ce test avant verdict.
- Les fiches d'adéquation moyenne sont suivies mais exclues des contrastes.

Questions et seuils
- Q1, adéquation : la croissance de la métrique d'adoption entre J0 et J+90 est-elle plus forte pour les fiches d'adéquation forte que pour les fiches d'adéquation faible ? Lisible avec au moins 8 fiches évaluables par groupe. Signal si l'écart des médianes atteint +20 points. Sinon pas de signal. Sous les minimums : non concluant.
- Q2, positionnement : les positions papier (adéquation forte, conviction haute, token coté à J0) battent-elles BTC ? Issue principale à J+90, secondaire à J+180. Lisible avec au moins 10 positions évaluables. Signal si la médiane de perf vs BTC est positive.

Calendrier
- Lecture Q1 : 90 jours après la dernière fiche de la semaine 12.
- Lecture Q2 : 90 puis 180 jours après la dernière position.

Décision
- Q1 et Q2 positifs : l'outil peut servir à se positionner, la question du capital réel est alors ouverte.
- Q1 positif, Q2 négatif : l'analyse fonctionne mais ne se monétise pas par le token. Le radar reste comme outil d'analyse.
- Q1 négatif ou non concluant : arrêt de CryptoStonk comme outil de positionnement.
