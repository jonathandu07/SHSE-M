import pprint
import traceback
from backend.main import dimensionner_systeme_shsem

try:
    res = dimensionner_systeme_shsem(puissance_traction_kw=10.0)
    pieces = res.get("pieces", {})
    optim = res.get("optimisation", {})

    with open("dump_pieces_v2_output.txt", "w", encoding="utf-8") as f:
        f.write("=== INCONNUES OPTIMISATION ===\n")
        f.write(pprint.pformat(optim.get("inconnues", {})))
        f.write("\n\n=== PIECES ===\n")
        for name, p in pieces.items():
            f.write(f"\n--- {name} ---\n")
            if hasattr(p, "analyser"):
                try:
                    r = p.analyser()
                    f.write(f"Inconnues Impossibles: {[i.get('nom') for i in r.get('inconnues', {}).get('impossibles', [])]}\n")
                    f.write(f"Inconnues Partielles: {[i.get('nom') for i in r.get('inconnues', {}).get('partielles', [])]}\n")
                    if name == "bielle":
                        f.write(f"Efforts bielle: {r.get('efforts')}\n")
                        f.write(f"Force max source: {r.get('sources', {}).get('force_axiale_max_N')}\n")
                        f.write(f"Moteur_thermique dependency is none: {p.moteur_thermique is None}\n")
                    if name == "arbre_vilebrequin":
                        f.write(f"Bielle liée ?: {'Oui' if p.bielle is not None else 'Non'}\n")
                        f.write(f"Moteur_thermique dependency is none: {p.moteur_thermique is None}\n")
                except Exception as e:
                    f.write(f"Erreur d'analyse: {e}\n")
                    f.write(traceback.format_exc() + "\n")
            else:
                f.write("Pas de méthode analyser()\n")

except Exception as e:
    with open("dump_pieces_v2_output.txt", "w", encoding="utf-8") as f:
        f.write("ERREUR FATALE DANS dimensionner_systeme_shsem:\n")
        f.write(traceback.format_exc() + "\n")
