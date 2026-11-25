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


def inline(paragraph, text, color_hex="1A526B"):
    pos = 0
    for m in re.finditer(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        h = OxmlElement('w:hyperlink')
        h.set(qn('r:id'), paragraph.part.relate_to(m.group(2), RT.HYPERLINK, is_external=True))
        r = OxmlElement('w:r')
        rp = OxmlElement('w:rPr')
        color = OxmlElement('w:color'); color.set(qn('w:val'), color_hex); rp.append(color)
        r.append(rp)
        t = OxmlElement('w:t'); t.text = m.group(1); r.append(t); h.append(r)
        paragraph._p.append(h)
        pos = m.end()
    if pos < len(text): paragraph.add_run(text[pos:])


def build(spec, target):
    # Each layout serves a different type of document and reader.
    layouts = {
        'terrain': ('Arial', 10.5, 23, 13, '151515', 'E5E5E5', 'F6F6F6', 1.12, 7),
        'étude': ('Calibri', 11, 23, 15, '1D4958', 'DEE9EC', 'F4F7F8', 1.10, 6),
        'méthode': ('Aptos', 10.5, 22, 13, '253D56', 'E0E7F0', 'F2F4F7', 1.08, 6),
        'revue': ('Arial', 10.5, 21, 13, '4D4338', 'EAE5E0', 'F6F4F1', 1.09, 6),
    }
    font, body_pt, title_pt, heading_pt, accent, shade, stripe, spacing, after = layouts[spec.get('layout', 'étude')]
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    sec.left_margin = sec.right_margin = Cm(2)
    for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2']:
        st = doc.styles[name]
        st.font.name = font; st.font.color.rgb = RGBColor(0,0,0)
        if st.element.rPr is not None:
            fonts = st.element.rPr.find(qn('w:rFonts'))
            if fonts is not None:
                for key in list(fonts.attrib):
                    if 'theme' in key.lower(): del fonts.attrib[key]
                for attr in ['ascii', 'hAnsi', 'eastAsia', 'cs']: fonts.set(qn('w:' + attr), font)
            for el in list(st.element.rPr):
                if el.tag == qn('w:color'):
                    for attr in ['themeColor', 'themeTint', 'themeShade']:
                        el.attrib.pop(qn('w:'+attr), None)
    doc.styles['Normal'].font.size = Pt(body_pt)
    doc.styles['Normal'].paragraph_format.space_after = Pt(after)
    doc.styles['Normal'].paragraph_format.line_spacing = spacing
    doc.styles['Title'].font.size = Pt(title_pt)
    doc.styles['Heading 1'].font.size = Pt(heading_pt)
    doc.styles['Heading 1'].font.color.rgb = RGBColor.from_string(accent)
    doc.styles['Subtitle'].font.size = Pt(10)
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
    doc.add_paragraph(spec.get('genre','Note métier') + '  ·  Cahiers métier et veille documentaire, 25 novembre 2026', 'Subtitle')
    p = doc.add_paragraph(); inline(p, spec['summary'], accent)
    for block in spec['sections']:
        if block.get('new_page'): doc.add_page_break()
        doc.add_heading(block['heading'], level=1)
        for text in block.get('paragraphs', []):
            inline(doc.add_paragraph(), text, accent)
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
                    shd = OxmlElement('w:shd');shd.set(qn('w:fill'),shade if ri==0 else (stripe if ri%2==0 else 'FFFFFF'));tcpr.append(shd)
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
        doc.add_heading(spec.get('reference_heading','Sources consultées'), level=1)
        for ref in spec['references']:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.0
            inline(p, ref, accent)
            for run in p.runs: run.font.size = Pt(9.5)
    target = Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    doc.save(target)


if __name__ == '__main__':
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    build(spec, sys.argv[2])
