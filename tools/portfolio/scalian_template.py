"""Apply the native cover and content layouts of Template Scalian - FR 2026.

The model is supplied locally. Only the two used layouts, their master, theme
and visual assets are imported. Chart workbooks, data and notes belong to the
generated presentation. Python's DOM retains the original namespace prefixes
used by PowerPoint extensions and by markup-compatibility attributes.
"""
from pathlib import Path
from posixpath import basename, dirname, join, normpath, relpath
import re
from tempfile import TemporaryDirectory
from xml.dom.minidom import parseString
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MASTER = "ppt/slideMasters/slideMaster1.xml"
COVER = "ppt/slideLayouts/slideLayout1.xml"
CONTENT = "ppt/slideLayouts/slideLayout8.xml"
THEME = "ppt/theme/theme1.xml"


def rels_path(part):
    return join(dirname(part), "_rels", basename(part) + ".rels")


def elements(node, ns, name):
    return list(node.getElementsByTagNameNS(ns, name))


def one(node, ns, name):
    matches = elements(node, ns, name)
    if len(matches) != 1:
        raise ValueError(f"Modèle de présentation incompatible : élément {name} attendu une fois.")
    return matches[0]


def serialize(document):
    return document.toxml(encoding="UTF-8")


def template_parts(template):
    """Collect assets reachable from these three presentation parts only."""
    master = parseString(template.read(MASTER))
    parts = {THEME: template.read(THEME), COVER: template.read(COVER), CONTENT: template.read(CONTENT)}
    if b"scalian" not in parts[COVER].lower():
        raise ValueError("Le fichier fourni ne contient pas la couverture du modèle Scalian FR 2026.")
    kept_layout_ids = set()
    media = {}
    for part in (MASTER, COVER, CONTENT):
        relationships = parseString(template.read(rels_path(part)))
        for entry in elements(relationships, REL, "Relationship"):
            target = normpath(join(dirname(part), entry.getAttribute("Target")))
            kind = entry.getAttribute("Type").rsplit("/", 1)[-1]
            if entry.getAttribute("TargetMode") == "External":
                raise ValueError(f"Lien externe inattendu dans le masque : {part}")
            if kind == "slideLayout":
                if target in (COVER, CONTENT):
                    kept_layout_ids.add(entry.getAttribute("Id"))
                else:
                    entry.parentNode.removeChild(entry)
            elif kind == "image" and dirname(target) == "ppt/media":
                dest = join("ppt/media", "scalian_" + basename(target))
                media[target] = dest
                parts[dest] = template.read(target)
                entry.setAttribute("Target", relpath(dest, dirname(part)))
            elif target not in (MASTER, THEME):
                raise ValueError(f"Relation de modèle non prise en charge : {part} vers {target}")
        parts[rels_path(part)] = serialize(relationships)
    for item in elements(master, P, "sldLayoutId"):
        if item.getAttributeNS(R, "id") not in kept_layout_ids:
            item.parentNode.removeChild(item)
    if len(kept_layout_ids) != 2:
        raise ValueError("Les dispositions 1 et 8 du modèle Scalian sont requises.")
    parts[MASTER] = serialize(master)

    # The large cover logo is a picture on the example cover, not on its layout.
    # Copy this single object. Neither example text nor source slide notes travel.
    sample = "ppt/slides/slide1.xml"
    picture = one(parseString(template.read(sample)), P, "pic")
    embed = one(picture, A, "blip").getAttributeNS(R, "embed")
    sample_rels = parseString(template.read(rels_path(sample)))
    logo_rel, = [e for e in elements(sample_rels, REL, "Relationship") if e.getAttribute("Id") == embed]
    logo_part = normpath(join(dirname(sample), logo_rel.getAttribute("Target")))
    if logo_part not in media or logo_rel.getAttribute("Type") != R + "/image":
        raise ValueError("Logo de couverture non associé au masque Scalian.")
    return parts, picture, media[logo_part]


def apply_template(content_pptx, template_pptx, output_pptx):
    """Write a new styled PPTX, leaving both sources intact."""
    content, template, output = map(Path, (content_pptx, template_pptx, output_pptx))
    if output.resolve() in (content.resolve(), template.resolve()):
        raise ValueError("Choisir une sortie différente du modèle et de la présentation de contenu.")
    try:
        with ZipFile(content) as deck, ZipFile(template) as model:
            for package in (deck, model):
                size = one(parseString(package.read("ppt/presentation.xml")), P, "sldSz")
                if (size.getAttribute("cx"), size.getAttribute("cy")) != ("12192000", "6858000"):
                    raise ValueError("Le modèle Scalian FR 2026 et le contenu doivent être au format 16:9.")
            parts, logo, logo_part = template_parts(model)
            if any(name in deck.namelist() for name in parts if name.startswith("ppt/media/")):
                raise ValueError("Collision de noms entre un média du contenu et le modèle.")
            slide_names = [s for s in deck.namelist() if re.fullmatch(r"ppt/slides/slide[1-9][0-9]*\.xml", s)]
            if "ppt/slides/slide1.xml" not in slide_names:
                raise ValueError("Le contenu doit comporter une couverture.")
            for name in slide_names:
                slide = parseString(deck.read(name))
                relationships = parseString(deck.read(rels_path(name)))
                is_cover = name == "ppt/slides/slide1.xml"
                for entry in elements(relationships, REL, "Relationship"):
                    if entry.getAttribute("Type") == R + "/slideLayout":
                        entry.setAttribute("Target", relpath(COVER if is_cover else CONTENT, dirname(name)))
                for bg in elements(slide, P, "bg"):
                    bg.parentNode.removeChild(bg)
                if slide.documentElement.hasAttribute("showMasterSp"):
                    slide.documentElement.removeAttribute("showMasterSp")
                if is_cover:
                    new_pic = slide.importNode(logo, deep=True)
                    properties = one(new_pic, P, "cNvPr")
                    max_id = max(int(p.getAttribute("id")) for p in elements(slide, P, "cNvPr"))
                    properties.setAttribute("id", str(max_id + 1))
                    properties.setAttribute("name", "Logo Scalian")
                    properties.setAttribute("descr", "Scalian")
                    one(new_pic, A, "blip").setAttributeNS(R, "r:embed", "scalianCoverLogo")
                    one(slide, P, "spTree").appendChild(new_pic)
                    addition = relationships.createElementNS(REL, "Relationship")
                    addition.setAttribute("Id", "scalianCoverLogo")
                    addition.setAttribute("Type", R + "/image")
                    addition.setAttribute("Target", relpath(logo_part, dirname(name)))
                    relationships.documentElement.appendChild(addition)
                parts[name] = serialize(slide)
                parts[rels_path(name)] = serialize(relationships)

            # PptxGenJS can announce masters for slides that do not have one.
            # Keep only real parts and declare the source layout and media types.
            dest_types = parseString(deck.read("[Content_Types].xml"))
            model_types = parseString(model.read("[Content_Types].xml"))
            actual = set(deck.namelist()) | parts.keys()
            overrides = set()
            for entry in elements(dest_types, CT, "Override"):
                name = entry.getAttribute("PartName").lstrip("/")
                if name not in actual:
                    dest_types.documentElement.removeChild(entry)
                else:
                    overrides.add(name)
            src_types = {e.getAttribute("PartName").lstrip("/"): e.getAttribute("ContentType")
                         for e in elements(model_types, CT, "Override")}
            default_types = {e.getAttribute("Extension"): e.getAttribute("ContentType")
                             for e in elements(model_types, CT, "Default")}
            for name in (COVER, CONTENT, *(p for p in parts if p.startswith("ppt/media/"))):
                if name not in overrides:
                    override = dest_types.createElementNS(CT, "Override")
                    override.setAttribute("PartName", "/" + name)
                    override.setAttribute("ContentType", src_types.get(name) or default_types[name.rsplit(".", 1)[-1]])
                    dest_types.documentElement.appendChild(override)
            parts["[Content_Types].xml"] = serialize(dest_types)
            output.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=output.parent) as stage:
                finished = Path(stage) / "presentation.pptx"
                with ZipFile(finished, "w", compression=ZIP_DEFLATED) as out:
                    for meta in deck.infolist():
                        if meta.filename not in parts and not meta.is_dir():
                            out.writestr(meta, deck.read(meta.filename))
                    for name, data in parts.items():
                        out.writestr(name, data)
                finished.replace(output)
    except (BadZipFile, KeyError) as exc:
        raise ValueError("Fichier PowerPoint ou modèle Scalian FR 2026 incomplet.") from exc
