from __future__ import annotations

from dimensionner_pack_cellules import (
    definir_batterie_samsung_25r,
    dimensionner_pack_samsung_25r_equivalent_twingo,
    formatter_rapport_pack,
)


# 1) Équivalent batterie Twingo 22 kWh, sans imposer de puissance moteur.
rapport_twingo = dimensionner_pack_samsung_25r_equivalent_twingo(
    courant_charge_cellule_a=2.0,  # prudent : ≈ 18 kW nominal sur 96S26P
)
print(formatter_rapport_pack(rapport_twingo))


# 2) Même pack, mais avec validation de puissance et charge rapide max.
rapport_puissance = definir_batterie_samsung_25r(
    nb_series=96,
    nb_parallele=26,
    puissance_continue_kw=60.0,
    puissance_pic_kw=90.0,
    courant_decharge_cellule_conception_a=20.0,  # limite haute constructeur, chauffe sévère
    courant_charge_cellule_a=4.0,                # charge rapide max constructeur
)
print(formatter_rapport_pack(rapport_puissance))


# 3) Nombre total de cellules variable.
rapport_variable = definir_batterie_samsung_25r(
    nb_cellules_total=2496,
    tension_nominale_cible_v=345.6,
    puissance_continue_kw=60.0,
    puissance_pic_kw=90.0,
    courant_decharge_cellule_conception_a=15.0,
    courant_charge_cellule_a=2.0,
)
print(formatter_rapport_pack(rapport_variable))
