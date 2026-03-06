# Synthese 1 page - robustesse du modele supply

## A dire en ouverture
Le modele actuel est **utile pour raisonner** sur la supply, mais il ne faut pas le presenter comme une copie fidele de l'operationnel.  
Il capte bien la structure reseau, les dependances matieres, les effets delai / revue / capacite / stock.  
En revanche, une partie importante de la performance baseline depend encore d'**hypotheses de preparation**.

## Ce qui est solide
- `item:042342` sur `M-1430` est une **fragilite structurelle robuste**:
  - mono-source
  - plus forte criticite
  - fort volume
- `M-1810` ressort comme **goulot service / backlog**.
- `M-1430` ressort comme **driver principal de cout**.
- La **frequence de revue / pilotage** est un levier majeur:
  - baseline: fill rate `0.945`
  - revue `7 jours`: fill rate `0.539`
- Les delais, la fiabilite amont et le stock fournisseur restent des leviers structurants.

## Ce qui depend fortement des hypotheses
- `item:693710` est bien dans la BOM, mais **son fournisseur est suppose**:
  - hypothese conservee: `693710 -> SDC-1450 / Gaillac`
- Le niveau de performance baseline depend fortement de:
  - l'**appro externe**
  - le **bootstrap de stock initial**
  - certaines hypotheses de completion du reseau
- Le **niveau absolu des couts** reste moins robuste que les tendances relatives.

## Chiffres cles a retenir
- Baseline actuelle:
  - fill rate `0.945`
  - backlog final `81.9`
  - cout total `28.7k`
- Sans mapping fournisseur pour `693710`:
  - fill rate `0.777`
  - backlog `334.4`
- Sans appro externe:
  - fill rate `0.808`
  - backlog `288.2`
- Mode strict "donnee brute seulement":
  - fill rate `0.274`
  - backlog `1089.0`

## Lecture simple
- La baseline est **bonne**, mais elle est aussi **protectrice**.
- Elle n'est pas uniquement portee par une supply "intrinsequement robuste":
  - elle est aussi soutenue par des stocks initiaux et des mecanismes de secours.
- Donc:
  - les **tendances** du modele sont utiles
  - les **niveaux absolus** doivent encore etre pris avec prudence

## Ce que montrent les tests cibles
- Rupture 5 jours sur `042342`:
  - fill rate `0.921`
  - backlog `119.0`
- Rupture 5 jours sur `773474`:
  - fill rate `0.913`
  - backlog `131.0`
- Rupture 5 jours sur `693710` (hypothese Gaillac):
  - fill rate `0.886`
  - backlog `170.4`
- Baisse de capacite `M-1810` de 30%:
  - fill rate `0.836`
  - backlog `245.5`

Conclusion:
- les intrants critiques mono-source et `M-1810` sont les points les plus sensibles
- les tests packaging `730384` / `333362` sont aujourd'hui plus des sujets de **qualite de donnee** que de risque operationnel majeur

## Message prudent mais utile pour l'industriel
On peut dire:

> Le modele est deja utile pour identifier les dependances critiques, les matieres les plus sensibles, l'effet du pilotage MRP/revue et les zones de fragilite.
> En revanche, une partie importante de la performance actuelle depend encore d'hypotheses de preparation, notamment autour de `693710`, de l'appro externe et des stocks initiaux.

## Les 5 messages les plus importants
1. `042342` est la fragilite la plus robuste du modele.
2. `M-1810` est le principal goulot service.
3. `693710` est important, mais sa lecture depend de l'hypothese Gaillac.
4. La revue/pilotage change enormement le resultat.
5. La baseline est credible comme scenario de travail, pas encore comme verite operationnelle.
