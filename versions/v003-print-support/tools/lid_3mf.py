#!/usr/bin/env python3
"""Turn OpenSCAD's two-body lid 3MF into one object with two parts.

OpenSCAD (with --enable=lazy-union) writes the lid and its black inlay as two
separate objects. Slicers then show two objects that have to be assembled by
hand. This rewrites the file as one object made of two components, and adds
the per-part filament assignment Bambu Studio / OrcaSlicer read from
Metadata/model_settings.config (part 1 -> filament 1, part 2 -> filament 2).
No printer or filament presets are written, so opening the file does not
touch the slicer's own settings.

    python3 tools/lid_3mf.py out/pierrot_lid_2color.3mf [-o out.3mf]
"""

import argparse
import re
import zipfile

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NAMES = ["lid (white)", "ink (black)"]

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def meshes(model_xml):
    """The <mesh> blocks of a 3MF model, colour references stripped."""
    out = re.findall(r"<mesh>.*?</mesh>", model_xml, re.S)
    return [re.sub(r'\s(pid|p1|p2|p3)="[^"]*"', "", m) for m in out]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("-o", "--out", help="default: overwrite src")
    ap.add_argument("--name", default="pierrot_lid")
    a = ap.parse_args()

    with zipfile.ZipFile(a.src) as z:
        model = z.read("3D/3dmodel.model").decode("utf-8")
    parts = meshes(model)
    if len(parts) != 2:
        raise SystemExit(f"expected 2 bodies, found {len(parts)}: export with --enable=lazy-union")

    obj = len(parts) + 1
    res = "".join(f' <object id="{i + 1}" name="{NAMES[i]}" type="model">{m}</object>\n'
                  for i, m in enumerate(parts))
    comps = "".join(f'<component objectid="{i + 1}"/>' for i in range(len(parts)))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}">\n<resources>\n{res}'
           f' <object id="{obj}" name="{a.name}" type="model"><components>{comps}</components></object>\n'
           f'</resources>\n<build><item objectid="{obj}"/></build>\n</model>\n')

    settings = [f'<?xml version="1.0" encoding="UTF-8"?>\n<config>\n <object id="{obj}">\n'
                f'  <metadata key="name" value="{a.name}"/>\n'
                f'  <metadata key="extruder" value="1"/>\n']
    for i in range(len(parts)):
        settings.append(f'  <part id="{i + 1}" subtype="normal_part">\n'
                        f'   <metadata key="name" value="{NAMES[i]}"/>\n'
                        f'   <metadata key="extruder" value="{i + 1}"/>\n  </part>\n')
    settings.append(" </object>\n</config>\n")

    with zipfile.ZipFile(a.out or a.src, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", xml)
        z.writestr("Metadata/model_settings.config", "".join(settings))
    print(f"3MF: one object '{a.name}', parts: {', '.join(NAMES)} -> filaments 1, 2")


if __name__ == "__main__":
    main()
