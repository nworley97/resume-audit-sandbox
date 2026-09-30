"""Reproduce bundled Figtree weights with fontTools 4.60.1.

Source: https://github.com/google/fonts/tree/main/ofl/figtree
License: ../AlteraSF/Fonts/OFL.txt (SIL OFL 1.1).
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root = Path(__file__).resolve().parents[1] / "AlteraSF" / "Fonts"
for weight, name in [(400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")]:
    font = instantiateVariableFont(TTFont(root / "Figtree-Variable.ttf"), {"wght": weight}, updateFontNames=True)
    font.save(root / f"Figtree-{name}.ttf")
    print(weight, font["name"].getDebugName(6))
