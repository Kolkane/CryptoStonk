PRÉCISIONS D'IMPLÉMENTATION, figées avant la première fiche.
- Métrique d'adoption : TVL prise au jour près. Volume DEX et frais en moyenne sur 7 jours. Fenêtres symétriques : 7 jours finissant à J0, 7 jours finissant à J+90.
- Prix d'entrée : clôture CoinGecko de J0. Le prix noté dans la fiche est indicatif.
- Sortie sur invalidation : enregistrée le jour même dans forward/sorties.csv, en citant la condition d'invalidation de la fiche. Prix de sortie : clôture CoinGecko du jour. La position passe en cash et sa performance se compare au BTC sur tout l'horizon.
- Token sans cotation depuis 14 jours : -100 %.
- Journal : une semaine ne compte comme faite ou vide que si rituel.py a laissé une trace commitée pendant cette semaine du protocole. Sans trace, elle est manquée, même journalisée après coup.
- Q1 positif et Q2 non concluant : même décision que Q1 positif et Q2 négatif. Prolonger Q2 exige un nouveau protocole figé avant toute nouvelle position.
- Suivi descriptif des solutions pré-token dont le token sort pendant le test : manuel, hors verdict.
