# Audit critique des fournisseurs - 29 septembre 2026

## Conclusion

La topologie actuelle est une hypothese de simulation, pas une chaine d'achats
industrielle validee. T4, T3, T2 et T1 codent des fonctions de procede ; ils ne
prouvent pas la distance commerciale a l'OEM. Un groupe peut couvrir plusieurs
fonctions. Un distributeur n'est pas automatiquement un lamineur, et un procede
interne n'est pas un fournisseur independant.

L'audit structurel couvre les 103 identifiants de sites et les 172 chemins.
17 dossiers prioritaires ont une conclusion individuelle : 7 roles a revoir,
7 identites a revoir, 3 fonctions plausibles. Les 86 autres restent a documenter,
pas valides par defaut. La detection par libelle signale 35 noeuds comme processus
ou hypotheses ; c'est une heuristique. L'examen des metadonnees source trouve
30 sites explicitement virtuels et 45 porteurs d'une hypothese : definitions
differentes, compteurs non interchangeables.

## Points prioritaires

| Priorite | Cas | Diagnostic et suite |
|---|---|---|
| 1 | Mitsubishi Chemical | Un UID reunit 7 occurrences Tielt/BE, 16 Hiratsuka/JP et 1 position japonaise historique. Le site agrege est en Belgique. Separer les implantations avant de recalculer climat et transports. |
| 1 | Toray | Nagoya et Masaki partagent un UID ; 34 occurrences pour 32 chemins distincts. Ne pas compter les occurrences comme des fournisseurs differents. |
| 1 | Euralliage | Activite de negoce, stockage et decoupe ; le T3 premiere transformation masque potentiellement un laminoir/extrudeur inconnu. |
| 1 | thyssenkrupp Materials France | Centre de service et transformation selon produit ; ne pas lui attribuer automatiquement la production primaire ou le laminage. |
| 1 | KYDEX | Les plaques de marque sont fabriquees par SEKISUI KYDEX. La chaine Shandong-Toray-Ensinger de R103-R109 ne documente pas correctement cette etape ; usine, distributeur et transformateur restent a identifier. |
| 1 | Krohne | Instrumentation industrielle documentee, affectee a trois ecrans et une powerbox. Rattachement produit non etabli, a desambiguiser. |
| 1 | Etapes internes / paniers electroniques | Ne pas les presenter comme des etablissements industriels verifies ou des secours independants. |
| 2 | Alcoa-AMAG | Fonctions primaire puis laminage plausibles ; flux commercial non prouve. Alcoa a cede le laminoir de Warrick a Kaiser, tout en conservant la fonderie dans la transaction 2021. AMAG dispose aussi d'une filiere primaire Alouette et de recyclage. |
| 2 | Chalco-Euralliage | Production primaire Qinghai documentee historiquement ; producteur du demi-produit et lien au distributeur non etablis. |
| 2 | Saarstahl / Aurubis | Groupes couvrant plusieurs procedes ; rang a determiner par produit et site, sans dupliquer artificiellement la production amont. |
| 2 | SABIC | Riyad identifie le siege, pas une usine de plaques LEXAN verifiee. |
| 2 | Ensinger / DuPont | Activite polymere ou fibre ne prouve ni tissage de sangle, ni assemblage de telecommande, ni filiere complete du velcro. |
| 2 | OEM unique | Site de reception et d'assemblage du programme a confirmer ; le groupe OEM ne suffit pas a etablir la destination industrielle. |

Les sources et la portee de chaque conclusion figurent dans
[le registre de decisions](config/supplier_role_review.yml).
La verification d'une activite ne constitue pas une verification de livraison.
Le contexte conserve 290 elements documentaires, dont aucun n'est classe comme
preuve verifiee de crise ; ce statut historique n'est pas modifie par cet audit
des fonctions industrielles.

## Effets sur les calculs

- La confusion usine/siege et les collisions geographiques peuvent fausser les
  profils climatiques, les distances et les facteurs d'electricite.
- Les fonctions mal attribuees peuvent fausser sensibilites meteo, capacite,
  rebut, maintenance et raccordement aux procedes ACV.
- Des noeuds internes dupliques peuvent surestimer l'independance des risques
  ou des capacites de secours. Leur suppression sans registre physique peut
  aussi retirer un procede necessaire : ne pas simplement effacer les noeuds.
- Les 688 lignes de transport examinees proviennent d'inferences geographiques,
  pas de preuves d'achat. Les 142 liaisons de sites ne sont donc pas 142 relations
  commerciales certifiees.
- Les masses de sites additionnent cinq passages dans la chaine : environ
  649,75 kg, contre 129,95 kg de masse allouee aux chemins. Ne pas les interpreter
  comme une masse de siege. Cette base supply est aussi a rapprocher de la masse
  OPERA de 109,967 kg avant toute conclusion quantitative globale.

## Livraison et limites

La carte existante affiche la fiche d'audit au clic sur le noeud et un tableau
recherchable dans Dashboard KPI. Le survol indique le role suppose et la reserve.
L'export exhaustif est `outputs/data/supplier_role_audit.csv`.

**Aucun role, flux, coefficient, score de criticite ni resultat SDD/ACV n'est
recalcule ou remplace par cette livraison.** Elle rend les reserves visibles
et conserve le nominal comme reference. La correction industrielle doit ensuite
etre faite par chemin : entite, usine, produit/grade, fonction, preuve du flux.

Priorite de recalcul : separer les sites Mitsubishi/Toray ; distinguer noeuds
physiques et processus internes ; retablir les producteurs de demi-produits
derriere les distributeurs ; puis rejouer les trois climats et les scenarios
France/Europe/monde avec comparaison a la reference conservee.

## Reproduction

```powershell
python -B POC2026/supply_geo_case/tools/audit_supplier_roles.py
python -B POC2026/supply_geo_case/tools/refresh_map_display.py
python -B -m pytest POC2026/tests/test_supplier_role_audit.py -q -p no:cacheprovider
python -B POC2026/supply_geo_case/tools/check_supplier_role_audit.py
```

Tests de calcul en memoire et navigateur hors ligne ; aucune alteration
volontaire des entrees. Les manifestes d'audit et de navigateur sont ecrits dans
de nouveaux dossiers `outputs/checks`. Ils ne certifient pas la chaine reelle.
