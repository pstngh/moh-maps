"""Readers for Valve Source (CS:GO) data, used to convert CS:GO maps to MOHAA.

* :mod:`.vpk` - VPK archives and chained search paths (pakfile > loose > VPK)
* :mod:`.vtf` - VTF textures to RGBA numpy arrays, TGA/PNG output
* :mod:`.vmt` - KeyValues / VMT parsing, patch-material resolution
* :mod:`.bsp` - Source BSP v21: entities, brushes, displacements, static props, pakfile
* :mod:`.mdl` - studiohdr_t metadata (materials, bounds) for static prop models

Game files are only read at runtime; nothing from them belongs in the repository.
"""
