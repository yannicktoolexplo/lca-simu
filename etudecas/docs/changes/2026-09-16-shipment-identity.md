# Correction de l’identité des transactions fournisseur

Le smoke test du moteur échouait : le CSV fournisseur conservait les identifiants
`SHIP-*` créés pour chaque chunk, tandis que les événements de lots utilisaient
des identifiants `SHP-*` regroupant route et dates. Le registre ne pouvait pas
réconcilier ces deux clés.

Le moteur conserve maintenant l’identité de transaction du planning fournisseur
dans les deux journaux, la réception, la généalogie et le MRP. Plusieurs articles
ou chunks d’une même route/date ne sont pas fusionnés. Un événement de départ
n’est plus décrit comme une preuve de consolidation dans les liens structurels.
L’identité d’un véhicule reste inconnue sans données spécifiques.

Le contexte du risque est également transmis lors des départs différés : jour de
décision d’origine et identifiants d’incident. Enregistrer le départ d’un stock
réservé ne consomme pas le stock une seconde fois.

## Vérifications

- Échec du smoke test reproduit avant correction.
- Suite du registre : 18 tests réussis, incluant deux simulations de dix jours,
  une mono-article et une avec plusieurs articles sur une même route/date.
- Suite complète des dossiers `simulation` et `documentation` : 375 tests
  réussis, 2 ignorés et 4 sous-tests réussis, en 76,29 secondes.
- Vérification transversale unittest : 253 tests, aucun échec, 2 ignorés.
- Contrôle documentaire `check` et contrôle du diff : réussis. La suite pytest
  complète des prototypes n’a pas été relancée pour cette correction ciblée.
- Dans les deux simulations, identifiants réconciliés, quantités de prélèvement
  et de réception vérifiées, bundles distincts, couverture des lots sources et
  des réceptions dans l’horizon égale à 1.
- Départ différé testé sur le ledger : décision conservée à J1, départ à J4,
  quantité 40, stocks restants identiques avant/après l’enregistrement du départ.
- Comparaison du smoke test initial avant/après avec le même graphe, horizon de
  dix jours, sans warm-up et graine 320270 : tous les KPI du résumé sont identiques.
  Les quatre CSV `first_simulation_daily`, `production_input_stocks_daily`,
  `production_output_products_daily` et `production_demand_service_daily` sont
  identiques octet pour octet. Cette comparaison porte sur ce scénario court.

Commande reproductible pour les contrôles de traçabilité :

```powershell
python -m pytest etudecas/simulation/test_risk_lot_impact_registry.py -q
```

## Mise à jour documentaire et limites

`python -m etudecas.documentation check` a détecté le changement du moteur et du
test avant actualisation des règles. L’identité par transaction a été explicitée
dans la source métier et `TRACE-SHIPMENT-001`. `TRACE-TIME-001` couvre également
le maintien du contexte lors du départ différé. Les empreintes de ces sources
sont actualisées après cette relecture, pas par une acceptation automatique.

Cette correction n’est ni une validation externe du modèle métier ni une
revalidation des campagnes historiques. Les anciens runs ne sont pas modifiés.
Les empreintes figées de scripts dans des protocoles historiques peuvent rejeter
le moteur modifié : une nouvelle campagne doit utiliser une référence revue,
sans supprimer les contrôles de provenance.
