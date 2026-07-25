# -*- coding: utf-8 -*-
import arcpy, os, sys
FOLDER = r"C:\Users\Usuario\Downloads\Analise_de_area\Lauri_Analise_1\MXD\claude"
name = sys.argv[1] if len(sys.argv) > 1 else "2000"
mxd = arcpy.mapping.MapDocument(os.path.join(FOLDER, "Dinamica_%s.mxd" % name))
els = arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT")
print("Dinamica_%s.mxd  -> %d TEXT_ELEMENT" % (name, len(els)))
for el in els:
    print("   x=%7.3f y=%7.3f | %r" % (el.elementPositionX, el.elementPositionY, el.text))
del mxd
