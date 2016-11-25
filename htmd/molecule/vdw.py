# (c) 2015-2016 Acellera Ltd http://www.acellera.com
# All Rights Reserved
# Distributed under HTMD Software License Agreement
# No redistribution in whole or part
#
class VDW:
  elements = [
    "X",  "H",  "He", "Li", "Be", "B",  "C",  "N",  "O",  "F",  "Ne",
    "Na", "Mg", "Al", "Si", "P" , "S",  "Cl", "Ar", "K",  "Ca", "Sc",
    "Ti", "V",  "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge",
    "As", "Se", "Br", "Kr", "Rb", "Sr", "Y",  "Zr", "Nb", "Mo", "Tc",
    "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I",  "Xe",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb",
    "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W",  "Re", "Os",
    "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr",
    "Ra", "Ac", "Th", "Pa", "U",  "Np", "Pu", "Am", "Cm", "Bk", "Cf",
    "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt",
    "Ds", "Rg"
  ]
  radii = [
    1.50, 1.20, 1.40, 1.82, 2.00, 2.00,
    1.70, 1.55, 1.52, 1.47, 1.54,
    1.36, 1.18, 2.00, 2.10, 1.80,
    1.80, 2.27, 1.88, 1.76, 1.37, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    1.63, 1.40, 1.39, 1.07, 2.00, 1.85,
    1.90, 1.85, 2.02, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    1.63, 1.72, 1.58, 1.93, 2.17, 2.00,
    2.06, 1.98, 2.16, 2.10, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 1.72, 1.66,
    1.55, 1.96, 2.02, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 1.86,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00, 2.00, 2.00, 2.00, 2.00, 2.00,
    2.00, 2.00, 2.00
  ]

  def radiusByElement( element ):
    try:
      return VDW.radii [ VDW.elements.index( element ) ]
    except:
      return 1.5


