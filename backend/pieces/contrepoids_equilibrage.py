import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'contrepoids_equilibrage'.
    Masses d'équilibrage monobloc ou rapportées sur le vilebrequin.
    """

    def __init__(self):
        self.nom = "contrepoids_equilibrage"
        self.masse_unitaire_kg = 0.0
        self.nombre = 0
        self.rayon_gravite_m = 0.0
        self.force_centrifuge_max_n = 0.0

    def dimensionner(self, vilebrequin, bielle, piston, rpm_max):
        """
        Calcule la masse requise pour équilibrer les forces rotatives et une partie des alternatives.
        M_cp * R_cp = M_rot * R_maneton + K * M_alt * R_maneton
        Avec K = 0.5 (facteur d'équilibrage 50%)
        """
        # On suppose 2 contrepoids par maneton pour un vilo standard, ou calcul global
        self.nombre = vilebrequin.nb_manetons * 2 
        
        # Masses mobiles
        masse_rotative_bielle = bielle.masse_totale_kg * 0.65 # Tête + partie corps (approx 2/3)
        masse_alternative = piston.masse_kg + (bielle.masse_totale_kg * 0.35) # Piston + Pied + partie corps
        
        # Rayon Maneton
        r_maneton = vilebrequin.rayon_manivelle_m
        
        # Rayon du Centre de Gravité du Contrepoids (souvent opposé au maneton, un peu plus grand ou égal)
        self.rayon_gravite_m = r_maneton * 1.1 # Un peu plus loin pour efficacité
        
        # Moment à équilibrer (100% Rotatif + 50% Alternatif)
        pourcentage_equilibrage_alternatif = 0.50
        moment_requis_kgm = (masse_rotative_bielle + (masse_alternative * pourcentage_equilibrage_alternatif)) * r_maneton
        
        # Masse totale contrepoids requise par maneton
        masse_totale_cp_par_maneton = moment_requis_kgm / self.rayon_gravite_m
        
        # Masse unitaire (2 CP par maneton)
        self.masse_unitaire_kg = masse_totale_cp_par_maneton / 2.0
        
        # Force Centrifuge Max
        omega = (3.14159 * rpm_max) / 30.0
        self.force_centrifuge_max_n = self.masse_unitaire_kg * self.rayon_gravite_m * (omega**2)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nombre: {self.nombre}\n"
                f"  - Masse Unitaire: {self.masse_unitaire_kg:.3f} kg (Rayon CG {self.rayon_gravite_m*1000:.1f} mm)\n"
                f"  - Équilibrage: 100% Rotatif + 50% Alternatif\n"
                f"  - Force Centrifuge Max: {self.force_centrifuge_max_n/1000:.1f} kN")
