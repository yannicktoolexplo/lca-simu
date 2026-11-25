"""Build the supervision note using the primary runtime Python and python-docx."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path(__file__).resolve().parent
BASE='https://github.com/yannicktoolexplo/lca-simu/blob/main/docs/provenance-revisions.md?fichier=ICs/#rev-0415'

def source(lines):
    return f'[Cahiers métier lignes {lines}]({BASE}Cahiers-metier.md#L{lines.replace(" à ","-L")})'

def rich(p,text):
    pos=0
    for m in re.finditer(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',text):
        if m.start()>pos:p.add_run(text[pos:m.start()])
        h=OxmlElement('w:hyperlink');h.set(qn('r:id'),p.part.relate_to(m.group(2),RT.HYPERLINK,is_external=True))
        r=OxmlElement('w:r');pr=OxmlElement('w:rPr')
        c=OxmlElement('w:color');c.set(qn('w:val'),'174E71');pr.append(c)
        u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u)
        r.append(pr);t=OxmlElement('w:t');t.text=m.group(1);r.append(t);h.append(r);p._p.append(h)
        pos=m.end()
    if pos<len(text):p.add_run(text[pos:])

def para(label,text):
    p=doc.add_paragraph()
    if label:p.add_run(label+' ').bold=True
    rich(p,text)
    return p

themes=[
('01 Choisir cinq dossiers fournisseurs','7 à 11',[
('Acquis.', 'Sur 27 fournisseurs simulés, un tirage uniforme manque tous les six cas de baisse dans 25,21 % des listes. Le plan quatre mono-source et un autre ramène ce taux à 9,09 %.'),
('Lecture métier.', '[Statistique Canada sur le tirage probabiliste](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/prob/5214899-eng.htm), mise à jour du 2 septembre 2021, aide à définir les groupes avant sélection. Demander une preuve de qualification de la seconde source. L’[étude automobile de Simchi-Levi et al.](https://doi.org/10.1287/inte.2015.0804), 2015, invite à examiner les conséquences opérationnelles d’une rupture.'),
('Recalcul public.', '910 listes sans aucun cas sur 10 010 donnent 9,091 %. Le plan quatre plus un est le meilleur quota testé si les deux groupes doivent être représentés. Cinq mono-source font mieux sur la seule détection d’au moins un cas, mais excluent l’autre groupe. Détecter au moins un cas ne signifie pas détecter tous les fournisseurs critiques.'),
('Suite.', 'Demander un tableau fournisseur–perturbation avec groupe fixé avant résultat, stocks utilisables, alternatives qualifiées et service dégradé. Tester aussi les non-sélectionnés et conserver les deux résultats manquants comme inconnus.')]),
('02 Acheter la quantité de dépannage utile','13 à 17',[
('Acquis.', '46 des 60 configurations évitent la rupture. Le besoin court passe de 800 à 900 kg lorsque seuls 90 % du premier arrivage sont utilisables. Les ordres et contraintes détaillés ne sont pas publics.'),
('Lecture métier.', '[Microsoft sur les paramètres de commande](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings), 10 juillet 2025, distingue minimum, multiple, maximum et délai. Demander ces paramètres pour la référence et le site. L’[étude d’Akkerman et al.](https://doi.org/10.1080/00207543.2025.2489755), version auteur d’avril 2025, ouvre une lecture sur la fiabilité différente des sources ; elle ne remplace pas le calcul à réception.'),
('Exemple pédagogique calculé.', 'Besoin de 1 850 kg, stock utilisable de 150 kg, arrivage long de 1 000 kg, multiple court de 200 kg et capacité de 800 kg. À 100 % puis 90 % utilisables, les manques sont 700 puis 800 kg ; la commande reste 800 kg dans les deux cas. Le conditionnement absorbe ici l’écart.'),
('Suite.', 'Demander les besoins datés, réservations, dates de libération, minimums, multiples et capacité confirmée. Ne pas compter comme certain un lot dont la libération est incertaine.')]),
('03 Demander le justificatif qui change un audit','19 à 23',[
('Acquis.', '16 des 84 cotations peuvent changer le choix de trois visites, lorsque chaque cotation est testée séparément. Cela représente 19,05 % des cotations, sans donner une probabilité de défaillance.'),
('Lecture métier.', '[ISO 19011 édition 2026](https://www.iso.org/standard/19011), publiée en mai 2026, fournit le repère actuel d’organisation des audits. Définir les preuves et l’objectif de visite avant de compléter la grille. Le [guide JRC de sensibilité](https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en), actualisé en décembre 2020, invite à distinguer incertitude sur les données et choix de pondération.'),
('Exemple pédagogique calculé.', 'Pour la troisième visite, C vaut 70 points et D 65. Baisser C de deux points seul ou relever D de quatre points seul ne change rien. Les deux modifications réunies donnent C à 68 et D à 69 : la sélection change. À 68 partout, conserver l’ex æquo. Tester les cases une à une ne suffit donc pas toujours.'),
('Suite.', 'Demander la grille versionnée, poids, bornes plausibles, dépendances et règles d’ex æquo. Commencer par les dossiers proches du seuil ; le calcul ne chiffre pas la rentabilité de chaque justificatif.')]),
('04 Dater la couverture réelle du dépôt','27 à 31',[
('Acquis.', 'Le dépôt couvre quatre jours complets. Le stock amont ajoute une journée de quantité uniquement si son transfert devient utilisable avant le premier manque.'),
('Lecture métier.', '[Oracle sur la promesse après libération des lots](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fascp/promise-only-after-you-release-holds-on-lots.html), documentation 26A de 2026, distingue levée de blocage et transfert. En entretien, demander la première arrivée utilisable au dépôt. [Microsoft sur les besoins nets](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/net-requirements), 21 juillet 2025, justifie de relever aussi la date du dernier calcul de planning.'),
('Exemple pédagogique calculé.', 'Avec 40 unités au dépôt et 10 consommées par jour, les 10 unités amont portent le ratio total à cinq jours. Arrivées à l’ouverture de J5, elles permettent cinq jours consécutifs. Arrivées à J6, elles laissent un manque de 10 unités en J5 : la continuité reste limitée à quatre jours. Le solde projeté négatif mesure le besoin non couvert.'),
('Suite.', 'Demander stock libre par statut, besoins et réservations datés, transferts, réception, libération qualité et calendriers. Compter chaque réception une seule fois, au point où elle sert la demande.')]),
('05 Choisir entre volume et service quotidien','33 à 37',[
('Acquis.', 'Les deux trajectoires servent 90 % et 84 % du volume sur cinq jours. Avec la réserve datée, la seconde tient neuf livraisons par jour, tandis que la première manque encore une unité à J2.'),
('Lecture métier.', '[Microsoft sur les dates promises](https://learn.microsoft.com/en-us/dynamics365/business-central/sales-how-to-calculate-order-promising-dates), mise à jour du 16 novembre 2026, rapproche quantité disponible, date et délais. Fixer le point d’engagement : départ dépôt ou réception client. L’[étude d’Ivanov sur la résilience vue par le client](https://doi.org/10.1080/00207543.2025.2454331), janvier 2025, compare plusieurs indicateurs sur trois réseaux simulés.'),
('Calcul partiel exécuté.', 'L’écart de volume est de six points. La réserve totale vaut quatre unités, dont seulement deux disponibles avant J3. D’après le manque publié à J2, la première trajectoire sert huit unités ce jour-là après réserve. Les séries complètes ne sont pas disponibles et ne sont pas reconstituées.'),
('Suite.', 'Si l’engagement est quotidien, le cahier départage déjà ces deux trajectoires. Pour un engagement hebdomadaire, comparer le cumul à échéance. Demander une vue article–jour avec besoins, arrivages utilisables, réserve, allocations et report autorisé.')]),
('06 Affecter un lot à deux commandes','39 à 43',[
('Acquis.', 'Servir l’urgence réduit le retard maximal de sept à quatre jours, mais augmente le retard pondéré par les quantités de 28 à 32 unités-jours.'),
('Lecture métier.', '[Microsoft sur la planification par priorité](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/priority-based-planning), 17 juin 2025, aide à demander qui attribue les priorités et comment elles passent entre lignes liées. Cette documentation de réapprovisionnement ne démontre pas l’optimalité d’une allocation de lots. La lecture d’Ivanov au thème 05 aide à expliquer les classements différents selon l’engagement.'),
('Calcul exécuté.', 'L’urgence évite trois jours de retard maximal et ajoute quatre unités-jours, soit 14,29 % du témoin. Si le contrat plafonne chaque retard à quatre jours, elle seule respecte le plafond parmi ces deux options. Avec une pénalité linéaire identique par unité-jour et aucune autre clause, l’autre ordre coûte moins cher. Aucun tarif réel n’est supposé.'),
('Suite.', 'Demander quantité et échéance par commande, lots libérés, réservations, prochains arrivages connus et possibilité de fractionner. Lire les franchises et plafonds de pénalité avant le choix. Un tableau de deux options suffit ; un nouvel algorithme n’apporte rien sans ces règles.')]),
('07 Replanifier après une fermeture de quai','47 à 51',[
('Acquis.', 'Deux charges de 40 unités dépassent une capacité de 60. Le cahier rapporte aucun regroupement faisable sur les 21 fermetures étudiées ; ces calendriers ne sont pas publics.'),
('Lecture métier.', '[Microsoft sur les rendez-vous de chargement](https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/tasks/set-up-appointment-load), 17 février 2025, distingue quai, heure locale et durée. Demander le temps complet d’occupation. L’[étude de Huang et al.](https://doi.org/10.1371/journal.pone.0318606), février 2025, combine fenêtres et rotations dans un cas portuaire simulé ; ses gains ne sont pas transférés à notre quai.'),
('Recalcul exécuté.', '80 unités représentent 133,33 % de la capacité, avec un dépassement de 20. Deux chargements au minimum sont nécessaires si les charges sont fractionnables. Cela ne signifie pas nécessairement deux véhicules : un véhicule peut tourner deux fois si son temps de cycle le permet.'),
('Suite.', 'Comparer départ avancé, créneau supplémentaire et second véhicule. Demander disponibilité marchandise, rendez-vous, délais client, capacités poids et volume, temps de rotation et chauffeurs. Écarter d’abord les solutions impossibles, puis comparer coût, heures et émissions des mouvements réellement déclenchés, retours compris.')]),
('08 Choisir les justificatifs transport','53 à 57',[
('Acquis.', 'Avec un budget de trois demandes, la collecte par parcours couvre 47,6 % des tonnes-kilomètres modélisées, contre 42,0 % par liaisons. À dix demandes, le classement s’inverse. La carte complète n’est pas publiée.'),
('Lecture métier.', '[GLEC v3.3 de Smart Freight Centre](https://smartfreightcentre.org/news/13311209/), publié le 27 octobre 2026, distingue transport et plateformes. Demander facteur, version, méthode de distance et correction déjà incluse. Une liaison bien documentée ne prouve pas que tout le parcours l’est. L’[étude sur les pratiques de reporting](https://researchportal.tuni.fi/en/publications/development-of-logistics-emissions-reporting-shippers-and-logisti/), en ligne en novembre 2025, justifie un format commun de collecte.'),
('Sensibilité pédagogique calculée.', 'L’avantage initial est de 5,6 points. Si chaque demande de parcours aboutit avec une probabilité de 80 %, contre 95 % par liaison, les couvertures attendues deviennent 38,08 % et 39,90 %. Ces taux hypothétiques supposent une couverture additive sans double compte ; ce ne sont pas des réponses observées.'),
('Suite.', 'Demander une vue expédition–tronçon–plateforme, activité, justificatif et résultat de chaque demande. Séparer tonnes-kilomètres documentées et proportion de parcours complets. L’optimum réel reste à tester.')]),
('09 Régler la relance du transitaire','59 à 63',[
('Acquis.', 'Sur 956 mois-scénarios apparentés, la saturation à 95 % détecte 251 des 273 mois dégradés et produit 616 fausses alertes. Le seuil de coût de 4,14 compare uniquement cette règle à la persistance.'),
('Lecture métier.', '[IATA Cargo iQ sur les jalons](https://iata-cargo.github.io/ONE-Record/2025-07/Orchestration/orchestration-mop/), version juillet 2025, conduit à demander jalon prévu, réalisation et annonce du report. La [publication de Mendonça et al.](https://doi.org/10.1108/IJPDLM-10-2022-0328), en ligne en décembre 2023, traite des expéditions individuelles ; les données mensuelles ne permettent pas d’entraîner ce type de prévision ici.'),
('Recalcul public.', '476 fausses alertes supplémentaires divisées par 115 mois manqués en moins donnent 4,139. Parmi les cinq règles du CSV, aucune alerte puis persistance puis saturation à 90 % minimisent successivement le coût limité aux fausses alertes et mois manqués. La bascule entre persistance et 90 % vaut 3,98347. Avec une fausse alerte à 1 et un mois manqué à 4, persistance coûte 688 contre 686 pour 90 %. Les seuils 95 % et 99 % ne gagnent jamais dans ce modèle.'),
('Suite.', 'Renseigner coût de tous les dossiers et capacité de traitement. La détection ne prouve pas qu’une relance évite le retard. Demander horaires et solutions encore possibles à l’instant d’annonce.')]),
('10 Vérifier les jeux complets disponibles','67 à 71',[
('Acquis.', 'Le cahier vérifie les bilans de 163 composants. Une disponibilité décalée laisse 115,12 kg bloqués et réduit les jeux livrés d’une unité. La masse totale ne révèle pas le composant manquant.'),
('Lecture métier.', '[Microsoft sur les blocages de stock](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-blocking), 14 août 2025, distingue quantité inspectée et quantité immobilisée. Demander le blocage réel du lot et éviter les doubles déductions. [GS1 EPCIS 2.0](https://ref.gs1.org/standards/epcis/), juin 2022, fournit une structure de journal daté reliant lot, lieu et état métier ; un export Excel suffit pour commencer.'),
('Exemple pédagogique calculé.', 'Trois composants A, B et C nécessitent deux, une et trois pièces par jeu. Le stock physique permettrait dix jeux. Après réservations et blocages, les quantités permettent respectivement huit, six et neuf jeux : seulement six sont complets. Libérer les cinq B avant consommation porte le total à huit, A devenant limitant.'),
('Suite.', 'Demander nomenclature versionnée, lot, stock physique, réservations, blocage, date de libération et passage au poste. Compter la disponibilité à chaque consommation. Une libération seulement espérée reste une hypothèse de planning.')]),
('11 Décider une retouche après recontrôle','73 à 77',[
('Acquis.', 'Sur le lot simulé de six pièces, trois acceptations suffisent sans trajet supplémentaire ; une tournée dédiée de 12 kg CO₂e porte le seuil à quatre. L’inventaire complet n’est pas public.'),
('Lecture métier.', 'Le [GHG Protocol Product Standard](https://ghgprotocol.org/product-standard), 2011, aide à décrire périmètre et allocation. Il ne suffit pas à établir un crédit d’émissions évitées. L’[étude de Järnefelt et al.](https://doi.org/10.1016/j.jclepro.2026.149164), septembre 2026, sur un téléphone, montre une préférence dépendant du composant et du moment de panne. Le résumé primaire seul a été lu.'),
('Exemple pédagogique distinct.', 'Pour huit pièces de service équivalent, remplacer coûte 72 kg CO₂e. Retoucher le lot ajoute 25 kg, puis chaque échec exige un remplacement de 9 kg. Trois acceptations donnent 70 kg sans transport ajouté. Avec une tournée de 12 kg, quatre acceptations donnent encore 73 kg ; cinq descendent à 64 kg. Les seuils calculés sont donc trois et cinq, distincts du cahier.'),
('Suite.', 'Demander acceptations par défaut, énergie, rebuts, pièces neuves évitées, trajet déclenché et durée de service garantie. Un trajet déjà prévu n’a un effet marginal nul que sous une hypothèse à vérifier.')]),
('12 Examiner la pondération en conception','79 à 83',[
('Acquis.', 'Huit impacts s’améliorent et huit se dégradent. Le cahier situe l’inversion à un poids de 7,294 % pour l’eutrophisation des eaux douces, les autres poids variant proportionnellement. Ce seuil n’est pas recalculable sans les seize résultats.'),
('Lecture métier.', 'La [méthode européenne PEF](https://environment.ec.europa.eu/publications/recommendation-use-environmental-footprint-methods_en), décembre 2021, sépare fonction, impacts, normalisation et pondération. Demander ces étapes séparément. Le [rapport JRC EF 3.1](https://op.europa.eu/en/publication-detail/-/publication/145f8401-a82a-11ed-b508-01aa75ed71a1), février 2023, décrit des changements de facteurs : figer leur version avant comparaison. Une préférence d’entreprise ne remplace pas librement les poids d’un résultat revendiqué conforme à PEF.'),
('Vérification exécutée.', 'Une plage proposée de 5 à 10 % traverse 7,294 %. Sous les mêmes hypothèses proportionnelles, aucun classement unique n’est stable sur toute cette plage. Le cahier ne dit pas quelle variante gagne de chaque côté. La plage acceptable doit être discutée avant le classement.'),
('Suite.', 'Demander fonction et durée de service, périmètre, seize impacts caractérisés, normalisation, poids et incertitudes. La masse identique ne suffit pas à garantir une fonction identique. Conserver les deux variantes tant que la préférence n’est pas tranchée.')]),
('13 Négocier un plafond sur les urgences','87 à 91',[
('Acquis.', 'Sur 240 jeux simulés, la probabilité que l’achat coûte plus que la fabrication passe d’environ 15,0 % à 40,4 % selon le regroupement. Les tarifs et tirages ne sont pas publics.'),
('Lecture métier.', 'Le [Green Book 2026](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026), mis à jour le 28 octobre 2026, invite à examiner les hypothèses et valeurs de bascule. L’[Orange Book](https://www.gov.uk/government/publications/orange-book/the-orange-book-management-of-risk-principles-and-concepts), actualisé le 18 novembre 2026, rappelle les relations entre risques. En négociation, demander un prix de plafonnement séparé et les incidents communs aux sous-lots.'),
('Exemple pédagogique calculé.', 'Quatre sous-lots ont chacun 25 % de risque marginal d’urgence, facturée 100 €. Un plafond de 200 € par lot parent évite en moyenne 5,46875 € si les urgences sont indépendantes, et 50 € si un événement commun touche les quatre. Avec une prime de 20 €, le plafond augmente le coût moyen dans le premier cas et le réduit dans le second.'),
('Suite.', 'Vérifier où le compteur redémarre. Demander lots avec et sans urgence, liens parent–sous-lot, incidents communs, exclusions, frais, prime et dates. Séparer économie moyenne et protection contre une facture extrême.')]),
('14 Comparer accélération et combinaison','93 à 97',[
('Acquis.', 'Pour le retard d’approvisionnement publié, accélérer seul atteint le même gain moyen d’arriéré que combiner et coûte moins cher. Sous retenue qualité, la combinaison apporte un gain ; le seuil documenté vaut environ 2,49 unités monétaires simulées par unité-jour.'),
('Lecture métier.', '[ACCA sur les coûts pertinents](https://www.accaglobal.com/uk/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/relevant-costs.html), page non datée, aide à retenir les dépenses futures qui changent avec la décision. Demander un devis différentiel. L’[étude de Müllerklein et Fontaine](https://doi.org/10.1016/j.ejor.2024.11.021), en ligne en novembre 2024, relie les possibilités de réacheminement à leur délai et capacité dans un cas industriel modélisé.'),
('Exemple pédagogique calculé.', 'L’accélération coûte 300 € et laisse 70 unités-jours d’arriéré. La combinaison coûte 400 € et en laisse 30. Les 100 € supplémentaires évitent 40 unités-jours, soit un seuil de 2,50 €/unité-jour. Avec une pénalité linéaire au-dessus de ce seuil, combiner devient préférable. Ce calcul distinct ne reproduit pas le seuil de 2,49.'),
('Suite.', 'Demander mêmes commandes, horizon, disponibilité, capacités, devis et pénalités. Si le gain supplémentaire est nul, retenir l’option moins chère sur cet indicateur. Valoriser tout arriéré restant en fin d’horizon.')]),
]

doc=Document();sec=doc.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.7);sec.bottom_margin=Inches(.65);sec.left_margin=Inches(.8);sec.right_margin=Inches(.8)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3']:
    st=doc.styles[name];st.font.name='Calibri';st.font.color.rgb=RGBColor(0,0,0)
    st.element.get_or_add_rPr().rFonts.set(qn('w:ascii'),'Calibri');st.element.get_or_add_rPr().rFonts.set(qn('w:hAnsi'),'Calibri')
normal=doc.styles['Normal'];normal.font.size=Pt(11);normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.line_spacing=1.06
for n,size in [('Title',23),('Heading 1',14),('Heading 2',13)]:
    st=doc.styles[n];st.font.size=Pt(size);st.paragraph_format.space_before=Pt(11);st.paragraph_format.space_after=Pt(7)
    st.paragraph_format.keep_with_next=True
# Explicitly remove style border and theme color residue.
for st in doc.styles:
    if st.type==1:
        pr=st.element.find(qn('w:pPr'))
        if pr is not None:
            for b in pr.findall(qn('w:pBdr')):pr.remove(b)
        rp=st.element.find(qn('w:rPr'))
        if rp is not None:
            for c in rp.findall(qn('w:color')):
                for k in ('themeColor','themeTint','themeShade'):c.attrib.pop(qn('w:'+k),None)
# Page count makes a multi-page working note easier to share.
f=sec.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.RIGHT
f.add_run('25 novembre 2026   ').font.size=Pt(9)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');f._p.append(fld)

doc.add_paragraph('Amorces métier pour les quatorze thèmes',style='Title')
para('', 'Note de supervision du 25 novembre 2026')
para('', 'Cette note aide les ingénieurs industriels, gestionnaires de projet et contrôleurs de gestion à partir des travaux existants pour préparer une décision concrète. La première contribution attendue peut être une lecture commentée, un entretien bien préparé ou un calcul simple. Les développements scientifiques éventuels se cadrent ensuite avec la supervision.')
doc.add_paragraph('Une progression accessible',style='Heading 1')
for label,text in [
('1 Lire les acquis.', 'Repérer le résultat exact, sa pièce et sa limite. Ne pas refaire une étude déjà concluante.'),
('2 Faire la veille métier.', 'Ouvrir pratiques et standards actuels. Expliquer ce que chaque lecture change dans une question au fournisseur ou une revue.'),
('3 Ouvrir la recherche utile.', 'Lire les résumés et résultats appliqués pertinents, puis préciser les différences avec notre situation.'),
('4 Vérifier et décider.', 'Recalculer un résultat disponible ou comparer deux options sur un petit tableau. Si une information terrain suffit, la demander.'),
('5 Préparer la suite.', 'Décrire la donnée ou la connaissance manquante. La supervision décide si un essai plus avancé est justifié.')]:para(label,text)
doc.add_paragraph('Le repère de Frascati',style='Heading 1')
para('', 'Le [Manuel de Frascati 2015 de l’OCDE](https://doi.org/10.1787/9789264257252-fr), édition française de juin 2016, chapitre 2, retient cinq critères pour la R&D : nouveauté, créativité, incertitude, démarche systématique et résultats transférables ou reproductibles. Apprendre une pratique nouvelle pour l’intervenant ne suffit pas à établir la nouveauté pour le secteur. Une veille prépare un projet ; elle ne prouve pas que l’activité satisfait ces critères. Une donnée manquante n’est pas à elle seule une incertitude scientifique.')
doc.add_paragraph('Origine et usage des résultats',style='Heading 1')
para('', 'Les acquis sont localisés dans les cahiers publics de la branche partage/cahiers-ic-anonymes, version du commit REV-0415. Ils proviennent d’exemples ou de simulations. Les deux CSV permettent des recalculs publics ; les autres exemples ajoutés sont identifiés comme pédagogiques. Les essais terrain restent des propositions. Aucun calcul complémentaire ni durée historique n’est attribué à un intervenant.')
para('', 'Toutes les lectures ont été consultées le 25 novembre 2026. Les liens ci-après ouvrent les références ; les six notes thématiques et le complément bibliographique conservent les dates, les périmètres et les limites de lecture détaillés. Les résultats d’une publication restent ceux de son cas d’application.')

for i,(title,lines,items) in enumerate(themes):
    if i%2==0:doc.add_page_break()
    doc.add_paragraph(title,style='Heading 1')
    p=doc.add_paragraph();p.paragraph_format.space_after=Pt(7);rich(p,source(lines))
    for label,text in items:para(label,text)
    # Separation between the two fiches on one page remains simple whitespace.
    if i%2==0:
        p=doc.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1
        p.add_run().font.size=Pt(3)

props=doc.core_properties;props.title='Amorces métier pour les quatorze thèmes';props.subject='Veille métier et préparation des décisions de supervision';props.author='';props.keywords='achats planification transport qualité contrôle de gestion'
output=ROOT/'Amorces-14-themes.docx';doc.save(output)
print(output)
print('Nombre de thèmes:',len(themes))
for title,lines,items in themes:
    words=len(re.sub(r'\[[^]]+\]\([^)]*\)','source',' '.join(t for _,t in items)).split())
    print(title,words)
