from .config import InputParameters, DimensionResults

def verify_constraints(inputs: InputParameters, res: DimensionResults) -> DimensionResults:
    """
    Checks calculated dimensions against limits and adds warnings.
    """
    res.warnings = []
    
    # Check Mean Piston Speed
    if res.U_mean > inputs.limits.U_p_max:
        res.warnings.append(f"ALERTE: Vitesse piston ({res.U_mean:.2f} m/s) dépasse la limite ({inputs.limits.U_p_max} m/s).")
        
    # Check Max Pressure (Sanity check vs materials generally)
    if res.p_max > 250e5: # 250 bar
        res.warnings.append(f"ALERTE: Pression max très élevée ({res.p_max/1e5:.1f} bar). Vérifier faisabilité joints/étanchéité.")
        
    # Check Rod Slenderness (Buckling risk indication)
    # Slenderness = L_eff / r_gyration. r = d/4 for circle.
    # Slenderness = L_eff / r_gyration.
    # For I-beam, approx r_gyration ~ 0.25 * width (weak axis)
    r_gyration = res.rod_column_section_width * 0.25
    slenderness = res.rod_length / r_gyration
    if slenderness > 120:
        res.warnings.append(f"ATTENTION: Bielle très élancée (Lambda={slenderness:.1f}). Risque de flambage accru.")

    # Check Dimensions vs Constraints
    if inputs.limits.max_diameter_limit:
        if res.cyl_outer_diameter > inputs.limits.max_diameter_limit:
             res.warnings.append(f"ERREUR: Diamètre cylindre ({res.cyl_outer_diameter*1000:.1f} mm) dépasse limite encombrement.")
    
    return res
