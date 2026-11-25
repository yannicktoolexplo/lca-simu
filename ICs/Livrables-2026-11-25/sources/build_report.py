"""Create a completed business report from a reviewed JSON specification."""
import json
import sys
import re
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT


def inline(paragraph, text):
    pos = 0
    for m in re.finditer(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        h = OxmlElement('w:hyperlink')
        h.set(qn('r:id'), paragraph.part.relate_to(m.group(2), RT.HYPERLINK, is_external=True))
        r = OxmlElement('w:r')
        rp = OxmlElement('w:rPr')
        color = OxmlElement('w:color'); color.set(qn('w:val'), '1A526B'); rp.append(color)
        r.append(rp)
        t = OxmlElement('w:t'); t.text = m.group(1); r.append(t); h.append(r)
        paragraph._p.append(h)
        pos = m.end()
    if pos < len(text): paragraph.add_run(text[pos:])


def build(spec, target):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    sec.left_margin = sec.right_margin = Cm(2)
    for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2']:
        st = doc.styles[name]
        st.font.name = 'Calibri'; st.font.color.rgb = RGBColor(0,0,0)
        if st.element.rPr is not None:
            for el in list(st.element.rPr):
                if el.tag == qn('w:color'):
                    for attr in ['themeColor', 'themeTint', 'themeShade']:
                        el.attrib.pop(qn('w:'+attr), None)
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].paragraph_format.space_after = Pt(6)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.07
    doc.styles['Title'].font.size = Pt(23)
    doc.styles['Heading 1'].font.size = Pt(14)
    doc.styles['Heading 2'].font.size = Pt(12)
    for style in doc.styles:
        ppr = style.element.find(qn('w:pPr'))
        if ppr is not None:
            for el in list(ppr):
                if el.tag == qn('w:pBdr'): ppr.remove(el)
    for n in ['Title','Heading 1','Heading 2']:
        doc.styles[n].paragraph_format.keep_with_next = True
    doc.core_properties.title = spec['title']
    doc.core_properties.author = ''
    doc.core_properties.subject = 'Analyse des travaux et résultats disponibles'
    doc.add_paragraph(spec['title'], 'Title')
    doc.add_paragraph('Rapport d’analyse du 25 novembre 2026', 'Subtitle')
    p = doc.add_paragraph(); inline(p, spec['summary'])
    for block in spec['sections']:
        if block.get('new_page'): doc.add_page_break()
        doc.add_heading(block['heading'], level=1)
        for text in block.get('paragraphs', []):
            inline(doc.add_paragraph(), text)
        if 'table' in block:
            data = block['table']
            table = doc.add_table(rows=1, cols=len(data['headers']))
            table.autofit = False
            widths = data.get('widths_cm', [17/len(data['headers'])]*len(data['headers']))
            for i, width in enumerate(widths): table.columns[i].width = Cm(width)
            for i,v in enumerate(data['headers']):
                table.rows[0].cells[i].text = str(v)
            for row in data['rows']:
                cells = table.add_row().cells
                for i,v in enumerate(row): cells[i].text = str(v)
            for ri,row in enumerate(table.rows):
                for i,cell in enumerate(row.cells):
                    cell.width = Cm(widths[i])
                    tcpr = cell._tc.get_or_add_tcPr()
                    borders = OxmlElement('w:tcBorders')
                    for edge in ['top','left','bottom','right']:
                        el = OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
                    tcpr.append(borders)
                    shd = OxmlElement('w:shd');shd.set(qn('w:fill'),'DDE6EA' if ri==0 else ('F5F7F8' if ri%2==0 else 'FFFFFF'));tcpr.append(shd)
                    for p in cell.paragraphs:
                        p.paragraph_format.space_after = Pt(4)
                        p.paragraph_format.space_before = Pt(4)
                        for run in p.runs:
                            run.font.size = Pt(10)
                            run.bold = ri==0
                if ri==0:
                    repeat=OxmlElement('w:tblHeader');row._tr.get_or_add_trPr().append(repeat)
            doc.add_paragraph()
    if spec.get('references'):
        doc.add_heading('Références consultées', level=1)
        for ref in spec['references']:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.0
            inline(p, ref)
            for run in p.runs: run.font.size = Pt(9.5)
    footer = sec.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run('25 novembre 2026   ')
    fld = OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
    for run in footer.runs: run.font.size = Pt(9)
    target = Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    doc.save(target)


if __name__ == '__main__':
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    build(spec, sys.argv[2])
