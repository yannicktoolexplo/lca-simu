// Run a copy in an OS temporary directory whose node_modules points to the
// Codex primary runtime. Arguments: repository absolute path, QA directory.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const repo = process.argv[2];
if (!repo) throw new Error('Provide the repository absolute path');
const outputDir = path.join(repo, 'ICs/Complements-2026-11-25');
const qaDir = process.argv[3] ?? path.join('/tmp', 'ic-workbook-qa');
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(qaDir, { recursive: true });
const baseUrl = 'https://github.com/yannicktoolexplo/lca-simu/blob/main/docs/provenance-revisions.md?fichier=ICs/#rev-0415';
function parseCsv(text) {
  // Both source CSVs have no quoted fields, embedded commas or newlines.
  return text.trim().split(/\r?\n/).map((row, ri) => row.split(',').map(v => ri === 0 || v === '' || !/^-?\d+(\.\d+)?$/.test(v) ? (v === '' ? null : v) : Number(v)));
}
const rawRevues = parseCsv(await fs.readFile(path.join(repo, 'ICs/Cas/revues-fournisseurs.csv'), 'utf8'));
const rawFret = parseCsv(await fs.readFile(path.join(repo, 'ICs/Cas/alertes-fret.csv'), 'utf8'));
const wb = Workbook.create();
const revues = wb.worksheets.add('Revues fournisseurs');
const alertes = wb.worksheets.add('Alertes fret');
const couts = wb.worksheets.add('Coûts des alertes');
const sr = wb.worksheets.add('Source revues');
const sf = wb.worksheets.add('Source fret');
const sheets = [revues, alertes, couts, sr, sf];
function cell(sheet, addr, value) { sheet.getRange(addr).values = [[value]]; }
function formula(sheet, addr, text) { sheet.getRange(addr).formulas = [[text]]; }
function init(sheet, range, widths) {
  sheet.showGridLines = false;
  sheet.getRange(range).format.font = { name: 'Arial', size: 10, color: '#202A35' };
  sheet.getRange(range).format.verticalAlignment = 'center';
  sheet.getRange(range).format.rowHeight = 22;
  for (const [col, width] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidth = width;
}
function title(sheet, text) { cell(sheet, 'A2', text); sheet.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true, color: '#000000' }; }
function header(sheet, addr, values) {
  const range = sheet.getRange(addr); range.values = [values];
  range.format.fill = '#29465B';
  range.format.font = { name: 'Arial', size: 10, color: '#FFFFFF', bold: true };
  range.format.wrapText = true;
  range.format.horizontalAlignment = 'center';
  range.format.rowHeight = 42;
  range.format.borders = { preset: 'inside', style: 'thin', color: '#FFFFFF' };
}
function note(sheet, addr, text) { cell(sheet, addr, text); sheet.getRange(addr).format.font = { name: 'Arial', size: 10, italic: true, color: '#52606D' }; }
function section(sheet, addr, text) { cell(sheet, addr, text); sheet.getRange(addr).format.font = { name: 'Arial', size: 10, bold: true, color: '#000000' }; }
function band(sheet, r1, r2, lastCol) { for (let r=r1; r<=r2; r++) if((r-r1)%2===1) sheet.getRange(`A${r}:${lastCol}${r}`).format.fill='#F0F4F7'; }

// Original public result tables: values, row order and blank quota cells retained.
init(sr, 'A1:H25', {A:33, B:31, C:17, D:16, E:19, F:20, G:20, H:20});
sr.getRange('A1:H19').values = rawRevues;
header(sr, 'A1:H1', rawRevues[0]); sr.freezePanes.freezeRows(1);
sr.getRange('C2:G19').setNumberFormat('#,##0'); sr.getRange('H2:H19').setNumberFormat('0.00000000');
note(sr, 'A21', 'Source publique simulée conservée sans modification des valeurs.');
cell(sr, 'A22', baseUrl+'Cas/revues-fournisseurs.csv');
cell(sr, 'A23', baseUrl+'Cas/Revue-fournisseurs.md');
cell(sr, 'A24', 'Lecture et complément de calcul : 25 novembre 2026.');
init(sf, 'A1:G22', {A:26, B:37, C:18, D:19, E:18, F:25, G:26});
sf.getRange('A1:G16').values = rawFret;
header(sf, 'A1:G1', rawFret[0]); sf.freezePanes.freezeRows(1);
sf.getRange('C2:G16').setNumberFormat('#,##0');
note(sf, 'A18', 'Source publique simulée conservée sans modification des valeurs.');
cell(sf, 'A19', baseUrl+'Cas/alertes-fret.csv');
cell(sf, 'A20', baseUrl+'Cas/Alertes-fret.md');
cell(sf, 'A21', 'Quatre trajectoires apparentées, aucune indépendance industrielle supposée.');
cell(sf, 'A22', 'Lecture et complément de calcul : 25 novembre 2026.');

// Recompute the finite-population selection comparison.
init(revues, 'A1:J42', {A:24, B:13, C:13, D:18, E:18, F:18, G:16, H:16, I:17, J:20});
revues.tabColor = '#29465B'; title(revues, 'Choisir cinq fournisseurs à revoir');
note(revues, 'A4', 'Complément calculé le 25/11/2026 sur les résultats simulés publiés.');
header(revues, 'A6:D6', ['Portefeuille testé', 'Fournisseurs', 'Baisse positive', 'Baisse ≥ 20 points']);
revues.getRange('A7:D8').values = [['Mono-source',13,5,3],['Autres',14,1,1]];
cell(revues,'A9','Places en revue');cell(revues,'B9',5);
note(revues,'F7','29 fournisseurs représentés, 27 testés, 2 résultats manquants.');
note(revues,'F8','Les probabilités portent sur les listes, pas sur les pannes.');
header(revues,'A12:J12',['Seuil de baisse','Places mono','Places autres','Listes possibles','Sans détection','Avec détection','P sans détection','P avec détection','Détections moyennes','P retenir le cas autre']);
for(let i=0;i<12;i++){
  const r=13+i, k=i%6, s=i<6?'C':'D';
  cell(revues,`A${r}`,i<6?'Positive':'≥ 20 points');cell(revues,`B${r}`,k);
  formula(revues,`C${r}`,`=$B$9-B${r}`);
  formula(revues,`D${r}`,`=COMBIN($B$7,B${r})*COMBIN($B$8,C${r})`);
  formula(revues,`E${r}`,`=COMBIN($B$7-$${s}$7,B${r})*COMBIN($B$8-$${s}$8,C${r})`);
  formula(revues,`F${r}`,`=D${r}-E${r}`);
  formula(revues,`G${r}`,`=E${r}/D${r}`);
  formula(revues,`H${r}`,`=F${r}/D${r}`);
  formula(revues,`I${r}`,`=B${r}*$${s}$7/$B$7+C${r}*$${s}$8/$B$8`);
  formula(revues,`J${r}`,`=C${r}/$B$8`);
}
band(revues,13,24,'J');revues.getRange('D13:F24').setNumberFormat('#,##0');
revues.getRange('G13:H24').setNumberFormat('0.00%');revues.getRange('I13:I24').setNumberFormat('0.000');revues.getRange('J13:J24').setNumberFormat('0.00%');
header(revues,'A28:I28',['Témoin ou règle fixe','Seuil','Autres places','Listes possibles','Sans détection','Avec détection','P sans détection','P avec détection','Détections moyennes']);
for(let i=0;i<2;i++){
  const r=29+i,s=i===0?'C':'D';cell(revues,`A${r}`,'Tirage uniforme');cell(revues,`B${r}`,i===0?'Positive':'≥ 20 points');
  formula(revues,`D${r}`,'=COMBIN(SUM($B$7:$B$8),$B$9)');
  formula(revues,`E${r}`,`=COMBIN(SUM($B$7:$B$8)-SUM($${s}$7:$${s}$8),$B$9)`);
  formula(revues,`F${r}`,`=D${r}-E${r}`);formula(revues,`G${r}`,`=E${r}/D${r}`);formula(revues,`H${r}`,`=F${r}/D${r}`);
  formula(revues,`I${r}`,`=$B$9*SUM($${s}$7:$${s}$8)/SUM($B$7:$B$8)`);
}
for(const [r,label,srrow] of [[31,'Délais les plus longs',16],[32,'Priorité action',18]]){
  cell(revues,`A${r}`,label);cell(revues,`B${r}`,'Positive');
  for(const [dst,src] of [['D','E'],['E','F'],['F','G'],['I','H']])formula(revues,`${dst}${r}`,`='Source revues'!${src}${srrow}`);
  formula(revues,`G${r}`,`=E${r}/D${r}`);formula(revues,`H${r}`,`=F${r}/D${r}`);
}
revues.getRange('D29:F32').setNumberFormat('#,##0');revues.getRange('G29:H32').setNumberFormat('0.00%');revues.getRange('I29:I32').setNumberFormat('0.000');
section(revues,'A35','Lecture pour la revue');
cell(revues,'A36','Quatre mono-source et un autre : 910 / 10 010 = 9,09 % de listes sans cas de baisse.');
cell(revues,'A37','Cinq mono-source : 4,35 %, mais le cas important de l’autre groupe ne peut jamais être retenu.');
cell(revues,'A38','Avec quatre plus un, chaque autre fournisseur a 1 / 14 = 7,14 % de chances d’être retenu.');
cell(revues,'A39','La règle quatre plus un convient si la revue impose la présence des deux groupes.');
cell(revues,'A40','Avant application : confirmer une seconde source réellement qualifiée et tester aussi les dossiers écartés.');
revues.freezePanes.freezeRows(12);

// Rates retain the exact denominators and each evaluation period.
init(alertes,'A1:L33',{A:30,B:12,C:12,D:12,E:12,F:14,G:15,H:15,I:15,J:16,K:14,L:16});
alertes.tabColor='#29465B';title(alertes,'Mesurer les alertes mensuelles de fret');
note(alertes,'A4','Unité : mois-scénario. Service insuffisant si masse servie / demandée < 99 %.');
note(alertes,'A5','Signal disponible : mois précédent. Les mois 1 initialisent les quatre trajectoires.');
const ruleLabels=['Saturation ≥ 90 %','Saturation ≥ 95 %','Saturation ≥ 99 %','Service précédent insuffisant','Aucune alerte'];
const blocks=[{header:8,start:9,src:2,label:'Tous les mois 956 décisions'},{header:15,start:16,src:7,label:'Mois 2 à 120 476 décisions'},{header:22,start:23,src:12,label:'Mois 121 à 240 480 décisions'}];
for(const b of blocks){
  section(alertes,`A${b.header-1}`,b.label);
  header(alertes,`A${b.header}:L${b.header}`,['Règle','Alertes justes','Fausses alertes','Mois manqués','Calmes sans alerte','Mois-scénarios','Part dégradée','Rappel','Précision','Fausses / calmes','Revues ouvertes','Revues / mois']);
  for(let i=0;i<5;i++){
    const r=b.start+i,s=b.src+i;cell(alertes,`A${r}`,ruleLabels[i]);
    for(const [dst,src]of[['B','C'],['C','D'],['D','E'],['E','F'],['F','G']]) formula(alertes,`${dst}${r}`,`='Source fret'!${src}${s}`);
    formula(alertes,`G${r}`,`=(B${r}+D${r})/F${r}`);formula(alertes,`H${r}`,`=B${r}/(B${r}+D${r})`);
    formula(alertes,`I${r}`,`=IF(B${r}+C${r}=0,"Indéfinie",B${r}/(B${r}+C${r}))`);
    formula(alertes,`J${r}`,`=C${r}/(C${r}+E${r})`);formula(alertes,`K${r}`,`=B${r}+C${r}`);formula(alertes,`L${r}`,`=K${r}/F${r}`);
  }
  band(alertes,b.start,b.start+4,'L');alertes.getRange(`B${b.start}:F${b.start+4}`).setNumberFormat('#,##0');
  alertes.getRange(`G${b.start}:J${b.start+4}`).setNumberFormat('0.0%');alertes.getRange(`L${b.start}:L${b.start+4}`).setNumberFormat('0.0%');
  alertes.getRange(`I${b.start}:I${b.start+4}`).format.horizontalAlignment='right';
}
section(alertes,'A30','Dénominateurs à conserver');
cell(alertes,'A31','Rappel = alertes justes / mois dégradés. Précision = alertes justes / revues ouvertes.');
cell(alertes,'A32','Fausses / calmes = fausses alertes / tous les mois calmes. Part dégradée = dégradés / mois-scénarios.');
cell(alertes,'A33','La fréquence des mois dégradés passe de 90 / 476 à 183 / 480. Aucun intervalle industriel n’est déduit.');

// Decision comparison with editable cost ratios, not claimed operational savings.
init(couts,'A1:G62',{A:40,B:15,C:15,D:15,E:20,F:18,G:20});
couts.tabColor='#29465B';title(couts,'Choisir une règle selon le coût des erreurs');
note(couts,'A4','Coûts relatifs : une fausse alerte vaut 1. Valeurs illustratives modifiables en jaune.');
cell(couts,'A5','Coût mois manqué / fausse alerte');cell(couts,'B5',5);
cell(couts,'D5','Coût revue juste / fausse alerte');cell(couts,'E5',0);
couts.getRange('A5:A6').format.wrapText=true;couts.getRange('D5:D6').format.wrapText=true;couts.getRange('A5:G5').format.rowHeight=44;
for(const a of ['B5','E5']){couts.getRange(a).format.fill='#FFF2CC';couts.getRange(a).setNumberFormat('0.00');couts.getRange(a).dataValidation={rule:{type:'decimal',operator:'greaterThanOrEqual',formula1:0}};}
cell(couts,'A6','Entrées numériques positives ou nulles');
formula(couts,'B6','=IF(AND(ISNUMBER(B5),ISNUMBER(E5),B5>=0,E5>=0),"Valides","À renseigner")');
cell(couts,'D6','Ratio hors coût de revue juste');formula(couts,'E6','=IF(B6="Valides",B5-E5,"À renseigner")');
couts.getRange('B6').format.wrapText=true;couts.getRange('A6:G6').format.rowHeight=35;
const cb=[{h:9,start:10,ar:9,title:'Tous les mois 956 décisions'},{h:19,start:20,ar:16,title:'Mois 2 à 120 476 décisions'},{h:29,start:30,ar:23,title:'Mois 121 à 240 480 décisions'}];
for(const b of cb){
  section(couts,`A${b.h-1}`,b.title);header(couts,`A${b.h}:G${b.h}`,['Règle','Alertes justes','Fausses alertes','Mois manqués','Coût relatif total','Minimum 5 règles','Minimum avec toujours']);
  for(let i=0;i<6;i++){
    const r=b.start+i, ar=b.ar+i;cell(couts,`A${r}`,i<5?ruleLabels[i]:'Toujours alerter référence calculée');
    couts.getRange(`A${r}`).format.wrapText=true;
    if(i<5){for(const c of['B','C','D'])formula(couts,`${c}${r}`,`='Alertes fret'!${c}${ar}`);}
    else {formula(couts,`B${r}`,`=B${b.start}+D${b.start}`);formula(couts,`C${r}`,`='Alertes fret'!C${b.ar}+'Alertes fret'!E${b.ar}`);cell(couts,`D${r}`,0);}
    formula(couts,`E${r}`,`=IF($B$6="Valides",D${r}*$B$5+C${r}+B${r}*$E$5,"À renseigner")`);
    formula(couts,`F${r}`,i<5?`=IF($B$6="Valides",IF(ABS(E${r}-MIN($E$${b.start}:$E$${b.start+4}))<0.000000001,"Minimum",""),"À renseigner")`:'="Référence ajoutée"');
    formula(couts,`G${r}`,`=IF($B$6="Valides",IF(ABS(E${r}-MIN($E$${b.start}:$E$${b.start+5}))<0.000000001,"Minimum",""),"À renseigner")`);
  }
  band(couts,b.start,b.start+5,'G');couts.getRange(`E${b.start}:E${b.start+5}`).setNumberFormat('#,##0.00');
  couts.getRange(`A${b.start+5}:G${b.start+5}`).format.rowHeight=36;
  couts.getRange(`F${b.start}:G${b.start+5}`).conditionalFormats.add('containsText',{text:'Minimum',format:{fill:'#E3EEE5',font:{bold:true,color:'#244D30'}}});
}
section(couts,'A38','Seuils de décision pour tous les mois');
header(couts,'A39:D39',['Comparaison','Numérateur','Dénominateur','Ratio de bascule']);
const thresholds=[
  [40,'Aucune vers persistance','=C13-C14','=D14-D13'],
  [41,'Persistance vers saturation 90 %','=C10-C13','=D13-D10'],
  [42,'Persistance vers toujours alerter','=C15-C13','=D13-D15'],
  [43,'Persistance vers saturation 95 %','=C11-C13','=D13-D11'],
];
for(const[r,label,n,d]of thresholds){cell(couts,`A${r}`,label);formula(couts,`B${r}`,n);formula(couts,`C${r}`,d);formula(couts,`D${r}`,`=IF($B$6="Valides",B${r}/C${r}+$E$5,"À renseigner")`);}
couts.getRange('D40:D43').setNumberFormat('0.00000');
cell(couts,'A45','Cinq règles : aucune alerte, puis persistance, puis saturation à 90 % aux seuils ci-dessus.');
cell(couts,'A46','Les saturations à 95 % et 99 % ne minimisent jamais ce coût parmi les cinq règles.');
cell(couts,'A47','Avec toujours alerter : aucune alerte, puis persistance, puis toujours alerter.');
cell(couts,'A48','À la bascule exacte, les deux règles ex æquo doivent rester en revue.');
section(couts,'A50','Ce que les calculs permettent de décider');
cell(couts,'A51','Coût = mois manqués × ratio + fausses alertes + alertes justes × coût relatif de revue juste.');
cell(couts,'A52','Les ratios sont des hypothèses de comparaison. Aucun coût industriel n’est mesuré dans les pièces.');
cell(couts,'A53','Toujours alerter est une référence ajoutée. Avec coût de revue juste nul, ses revues justes sont gratuites.');
cell(couts,'A54','Une alerte juste ne prouve pas qu’une relance évite la perte : l’efficacité de l’action reste à mesurer.');
cell(couts,'A55','Le seuil 4,14 compare seulement saturation 95 % et persistance. Il ne choisit pas parmi toutes les règles.');
cell(couts,'A56','Les minima préservent les ex æquo. Les périodes sont comparées séparément sur les mêmes ratios.');
cell(couts,'A57','Pour une décision réelle : relever le temps de revue, le coût du manque et l’action rendue possible à temps.');

// Independent JS arithmetic verifies workbook results and input-driven recalculation.
const verification={date:'2026-11-25',source_commit:'REV-0415',checks:[],limitations:[
 'Calcul et rendu vérifiés dans Artifact Tool ; ouverture dans Excel desktop non exécutée.',
 'Coûts de classification illustratifs ; efficacité des relances et pertes industrielles non mesurées.',
 'Deux résultats fournisseurs manquants exclus du portefeuille de 27 essais.'
]};
function check(name, actual, expected, tolerance=1e-8){if(typeof actual==='number'&&typeof expected==='number'){if(Math.abs(actual-expected)>tolerance)throw new Error(`${name}: ${actual} != ${expected}`);}else if(actual!==expected)throw new Error(`${name}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);verification.checks.push({name,actual,expected});}
wb.recalculate();
for(let i=0;i<12;i++){
  const r=13+i,k=i%6,threshold=i<6?'baisse_positive':'baisse_au_moins_20_points';
  const raw=rawRevues.slice(1).find(row=>row[0]===threshold&&row[1]==='tirage_par_groupe'&&row[2]===k);
  const got=revues.getRange(`D${r}:I${r}`).values[0];
  check(`revue ${threshold} quota ${k} listes`,got[0],raw[4]);check(`revue ${threshold} quota ${k} sans`,got[1],raw[5]);check(`revue ${threshold} quota ${k} avec`,got[2],raw[6]);check(`revue ${threshold} quota ${k} moyenne`,got[5],raw[7]);
}
for(const b of blocks)for(let i=0;i<5;i++){
  const r=b.start+i, raw=rawFret[b.src-1+i];const got=alertes.getRange(`B${r}:L${r}`).values[0];
  check(`fret ${r} total`,got[4],raw[6]);check(`fret ${r} rappel`,got[6],raw[2]/(raw[2]+raw[4]));check(`fret ${r} précision`,got[7],raw[2]+raw[3]===0?'Indéfinie':raw[2]/(raw[2]+raw[3]));
}
for(let i=0;i<5;i++)for(let col=2;col<=6;col++)check(`somme périodes règle ${i} champ ${col}`,rawFret[1+i][col],rawFret[6+i][col]+rawFret[11+i][col]);
check('cinq règles coût défaut saturation 90',couts.getRange('F10').values[0][0],'Minimum');
check('six règles coût défaut toujours',couts.getRange('G15').values[0][0],'Minimum');
cell(couts,'B5',2);wb.recalculate();check('ratio 2 persistance minimum',couts.getRange('F13').values[0][0],'Minimum');
cell(couts,'B5',0);wb.recalculate();check('ratio zéro aucune alerte',couts.getRange('F14').values[0][0],'Minimum');
cell(couts,'B5',null);wb.recalculate();check('ratio absent signalé',couts.getRange('E10').values[0][0],'À renseigner');
cell(couts,'B5',140/136);wb.recalculate();check('ex æquo aucune',couts.getRange('F14').values[0][0],'Minimum');check('ex æquo persistance',couts.getRange('F13').values[0][0],'Minimum');
cell(couts,'B5',5);cell(couts,'E5',4);wb.recalculate();check('coût revue juste change décision',couts.getRange('F14').values[0][0],'Minimum');
cell(couts,'E5',0);wb.recalculate();
check('seuil cinq règles',couts.getRange('D41').values[0][0],482/121);check('seuil six règles',couts.getRange('D42').values[0][0],543/137);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'Erreurs de formule'});
verification.error_scan=errors.ndjson;
await fs.writeFile(path.join(qaDir,'verification-workbook.json'),JSON.stringify(verification,null,2));
await fs.writeFile(path.join(outputDir,'verification-workbook.json'),JSON.stringify(verification,null,2));
for(const[sheet,range,file]of [[revues,'A1:J24','revues.png'],[alertes,'A1:L27','alertes.png'],[couts,'A1:G35','couts.png'],[couts,'A38:G57','seuils.png'],[sr,'A1:H19','source-revues.png'],[sf,'A1:G16','source-fret.png']]){
  const render=await wb.render({sheetName:sheet.name,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(qaDir,file),new Uint8Array(await render.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(outputDir,'Calculs-revues-et-alertes.xlsx'));
await fs.rm(path.join(outputDir,'Calculs-revues-et-alertes.xlsx.inspect.ndjson'),{force:true});
console.log(JSON.stringify({output:path.join(outputDir,'Calculs-revues-et-alertes.xlsx'),checks:verification.checks.length,error_scan:errors.ndjson,qaDir}));
