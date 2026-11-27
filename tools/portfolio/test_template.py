"""Read-only checks of a rendered portfolio deck against the official template.

python tools/portfolio/test_template.py --template modele.pptx --presentation sortie/presentation.pptx
Supply --raw to also compare chart workbooks, speaker notes and diagrams byte for byte.
"""
import argparse
from pathlib import Path
from posixpath import dirname, join, normpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scalian_template import CONTENT, COVER, CT, MASTER, P, R, THEME, rels_path


def verify(template, presentation, raw=None):
    with ZipFile(template) as model, ZipFile(presentation) as out:
        names = set(out.namelist())
        for part in (COVER, CONTENT, THEME):
            if out.read(part) != model.read(part):
                raise ValueError(f"Source du modèle différente dans {part}")
        for name in ("image1.png", "image2.jpg"):
            if out.read("ppt/media/scalian_" + name) != model.read("ppt/media/" + name):
                raise ValueError(f"Ressource Scalian différente : {name}")
        layouts = {p for p in names if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", p)}
        if layouts != {COVER, CONTENT}:
            raise ValueError("Les deux dispositions attendues doivent être les seules présentes.")
        for part in names:
            if part.endswith(".rels"):
                for rel in ET.fromstring(out.read(part)):
                    if rel.get("TargetMode") != "External":
                        target = normpath(join(dirname(dirname(part)), rel.attrib["Target"])).lstrip("/")
                        if target not in names:
                            raise ValueError(f"Relation sans cible : {part} vers {target}")
        types = ET.fromstring(out.read("[Content_Types].xml"))
        if any(x.attrib["PartName"].lstrip("/") not in names for x in types.findall(f"{{{CT}}}Override")):
            raise ValueError("Déclaration de type sans partie correspondante.")
        slide_ids = ET.fromstring(out.read("ppt/presentation.xml")).findall(f".//{{{P}}}sldId")
        slide_names = [p for p in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", p)]
        if not slide_ids or len(slide_ids) != len(slide_names):
            raise ValueError("Incohérence dans le nombre de diapositives.")
        for part in slide_names:
            rels = ET.fromstring(out.read(rels_path(part)))
            expected = COVER if part.endswith("/slide1.xml") else CONTENT
            used = [normpath(join(dirname(part), r.attrib["Target"])) for r in rels if r.get("Type") == R + "/slideLayout"]
            if used != [expected]:
                raise ValueError(f"Mauvaise disposition pour {part}")
        master = ET.fromstring(out.read(MASTER))
        if len(master.findall(f".//{{{P}}}sldLayoutId")) != 2:
            raise ValueError("Le masque doit référencer les deux dispositions visibles.")
        if raw is not None:
            with ZipFile(raw) as source:
                prefixes = ("ppt/charts/", "ppt/embeddings/", "ppt/notesSlides/", "ppt/diagrams/")
                parts = {name for name in source.namelist() if name.startswith(prefixes) and not name.endswith("/")}
                for name in parts:
                    if source.read(name) != out.read(name):
                        raise ValueError(f"Contenu du générateur modifié : {name}")
        return len(slide_names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--presentation", required=True, type=Path)
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()
    count = verify(args.template, args.presentation, args.raw)
    print(f"Masque, dispositions, médias et relations vérifiés sur {count} diapositives.")
