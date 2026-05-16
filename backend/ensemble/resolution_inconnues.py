from __future__ import annotations

"""Resolution centrale et tracee des inconnues STHO-ME.

Ce module ne remplace pas les calculateurs metier. Il complete uniquement les
valeurs calculables, propagables ou choisies dans un domaine explicitement porte
par le cahier des charges. Toute valeur ajoutee est tracee.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
import copy
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Number = int | float


@dataclass(frozen=True)
class CahierDesChargesSTHOME:
    """Contraintes globales exploitees par le resolveur.

    Les valeurs par defaut representent le cahier des charges projet, pas des
    donnees mesurees. Quand une de ces valeurs est injectee, la trace indique
    ``type_resolution="contrainte_cdc"`` ou ``"optimisee"``.
    """

    duty_cycle_moteur_thermique_max: float = 0.50
    marge_wltp: float = 0.20
    scenario_pire_cas: str = "batterie_vide_traction_electrique_pleine_puissance"
    systeme_multi_energies: bool = True
    compatibilite_solidworks_requise: bool = True

    tension_bus_dc_v: Optional[float] = 400.0
    tension_bus_dc_min_v: float = 250.0
    tension_bus_dc_max_v: float = 850.0

    nombres_cylindres_autorises: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 8, 10, 12)
    alesage_min_m: float = 0.040
    alesage_max_m: float = 0.180
    course_min_m: float = 0.040
    course_max_m: float = 0.220
    ratio_course_alesage_min: float = 0.70
    ratio_course_alesage_max: float = 1.35
    ratio_course_alesage_cible: float = 1.00
    vitesse_piston_max_ms: Optional[float] = None

    rpm_moteur_min: float = 800.0
    rpm_moteur_max: float = 5000.0
    rpm_moteur_prefere: float = 3000.0
    regimes_moteur_candidats_rpm: Tuple[float, ...] = (1200.0, 1500.0, 1800.0, 2400.0, 3000.0, 3600.0)

    rapport_boite_min: float = 0.40
    rapport_boite_max: float = 6.00
    architectures_autorisees: Tuple[str, ...] = ("L", "V", "Boxer", "Etoile")

    rendement_alternateur_reference: Optional[float] = None
    rendement_boite_reference: Optional[float] = None
    rendement_liaison_meca_alt_reference: Optional[float] = None

    materiaux_autorises: Tuple[str, ...] = ("acier_42crmo4_qt", "alu_7075_t6", "fonte_en_gjl_250")
    familles_materiaux_autorisees: Tuple[str, ...] = ("metal",)
    temperature_service_max_c: Optional[float] = None
    contrainte_service_pa: Optional[float] = None
    facteur_securite_materiau: float = 1.5
    autoriser_choix_materiau: bool = True

    max_iterations_resolution: int = 3


@dataclass(frozen=True)
class HypotheseResolue:
    champ: str
    valeur: Any
    unite: str
    type_resolution: str
    source: str
    formule: str
    dependances: Dict[str, Any]
    justification: str
    niveau_confiance: str
    validation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionInconnuesReport:
    payload_resolu: Dict[str, Any]
    hypotheses: List[HypotheseResolue] = field(default_factory=list)
    donnees_auto_completees: Dict[str, Any] = field(default_factory=dict)
    inconnues: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    coherence_systeme: Dict[str, Any] = field(default_factory=dict)
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def en_dict(self) -> Dict[str, Any]:
        return {
            "payload_resolu": _jsonable(self.payload_resolu),
            "hypotheses": [_jsonable(h) for h in self.hypotheses],
            "donnees_auto_completees": _jsonable(self.donnees_auto_completees),
            "inconnues": _jsonable(self.inconnues),
            "coherence_systeme": _jsonable(self.coherence_systeme),
            "iterations": _jsonable(self.iterations),
            "notes": list(self.notes),
        }


def resoudre_inconnues_systeme(
    entrees: Mapping[str, Any] | None,
    rapports_existants: Mapping[str, Any] | None = None,
    cahier_des_charges: CahierDesChargesSTHOME | Mapping[str, Any] | None = None,
) -> ResolutionInconnuesReport:
    """Complete les inconnues resolubles sans inventer de donnees cachees."""

    cdc = _coerce_cdc(cahier_des_charges)
    payload = _deepcopy_dict(entrees)
    rapports = _deepcopy_dict(rapports_existants)
    context = _deep_merge(copy.deepcopy(rapports), copy.deepcopy(payload))

    state = _ResolutionState(payload=payload, rapports=rapports, cdc=cdc)

    for index in range(max(1, int(cdc.max_iterations_resolution))):
        before = len(state.hypotheses)
        _resoudre_puissances_et_bus(state)
        _resoudre_rotation_et_couple(state)
        _resoudre_geometrie_moteur(state)
        _resoudre_alternateur_boite(state)
        _resoudre_batterie(state)
        _resoudre_materiaux(state)
        after = len(state.hypotheses)
        state.iterations.append(
            {
                "iteration": index + 1,
                "valeurs_ajoutees": after - before,
                "arret": "point_fixe" if after == before else "nouvelles_valeurs",
            }
        )
        if after == before:
            break
        context = _deep_merge(context, copy.deepcopy(state.payload))
        state.rapports = _deep_merge(state.rapports, context)

    _classer_inconnues_restantes(state)
    coherence = verifier_coherence_resolution(state.payload, cdc)
    state.coherence_systeme = coherence

    return ResolutionInconnuesReport(
        payload_resolu=state.payload,
        hypotheses=state.hypotheses,
        donnees_auto_completees=dict(state.completed),
        inconnues=state.inconnues,
        coherence_systeme=coherence,
        iterations=state.iterations,
        notes=state.notes,
    )


def appliquer_resolution_inconnues(
    payload: Mapping[str, Any] | None,
    resolutions: ResolutionInconnuesReport | Sequence[HypotheseResolue] | Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Applique une liste de resolutions tracees a une copie du payload."""

    out = _deepcopy_dict(payload)
    hypotheses: Iterable[Any]
    if isinstance(resolutions, ResolutionInconnuesReport):
        hypotheses = resolutions.hypotheses
    else:
        hypotheses = resolutions
    for item in hypotheses:
        if isinstance(item, HypotheseResolue):
            champ = item.champ
            valeur = item.valeur
        elif isinstance(item, Mapping):
            champ = str(item.get("champ", ""))
            valeur = item.get("valeur")
        else:
            continue
        if not champ:
            continue
        _set_path(out, champ, valeur)
    return out


def tracer_resolution_inconnues(
    resolutions: ResolutionInconnuesReport | Sequence[HypotheseResolue] | Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Retourne les traces JSON-safe des hypotheses resolues."""

    if isinstance(resolutions, ResolutionInconnuesReport):
        hypotheses = resolutions.hypotheses
    else:
        hypotheses = list(resolutions)
    return [_jsonable(h) for h in hypotheses]


def verifier_coherence_resolution(
    payload_resolu: Mapping[str, Any] | None,
    cahier_des_charges: CahierDesChargesSTHOME | Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Evalue un score de coherence exploitable par le frontend."""

    cdc = _coerce_cdc(cahier_des_charges)
    payload = _deepcopy_dict(payload_resolu)
    blockers: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    scores: Dict[str, float] = {
        "puissance": _score_puissance(payload, cdc, blockers, actions),
        "energie": _score_energie(payload, actions),
        "mecanique": _score_mecanique(payload, blockers, actions),
        "thermique": _score_thermique(payload, actions),
        "geometrie": _score_geometrie(payload, blockers, actions),
        "materiaux": _score_materiaux(payload, cdc, actions),
        "cao": _score_cao(payload, cdc, actions),
        "cdc": _score_cdc(payload, cdc, blockers, actions),
    }
    score_global = sum(scores.values()) / max(len(scores), 1)

    if blockers:
        statut = "invalide"
    elif score_global >= 0.85:
        statut = "valide"
    elif score_global >= 0.65:
        statut = "valide_avec_reserves"
    else:
        statut = "incomplet"

    return {
        "score_global": round(float(max(0.0, min(1.0, score_global))), 4),
        "statut": statut,
        "scores": {k: round(float(max(0.0, min(1.0, v))), 4) for k, v in scores.items()},
        "points_bloquants": _dedup_items(blockers),
        "actions_recommandees": _dedup_items(actions),
    }


@dataclass
class _ResolutionState:
    payload: Dict[str, Any]
    rapports: Dict[str, Any]
    cdc: CahierDesChargesSTHOME
    hypotheses: List[HypotheseResolue] = field(default_factory=list)
    completed: Dict[str, Any] = field(default_factory=dict)
    inconnues: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "resolues_automatiquement": [],
            "restantes_catalogue": [],
            "restantes_physiques": [],
            "conflits": [],
            "bloquantes": [],
            "non_bloquantes": [],
        }
    )
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conflits: List[Dict[str, Any]] = field(default_factory=list)

    def get(self, *paths: str) -> Any:
        return _first_non_missing(self.payload, self.rapports, *paths)

    def number(self, *paths: str) -> Optional[float]:
        return _first_number(self.payload, self.rapports, *paths)

    def integer(self, *paths: str) -> Optional[int]:
        value = self.number(*paths)
        if value is None:
            return None
        rounded = int(round(value))
        if abs(value - rounded) <= 1e-9:
            return rounded
        return None

    def add(
        self,
        champ: str,
        valeur: Any,
        *,
        unite: str,
        type_resolution: str,
        source: str,
        formule: str,
        dependances: Mapping[str, Any],
        justification: str,
        niveau_confiance: str,
        validation: Optional[Mapping[str, Any]] = None,
        aliases: Sequence[str] = (),
    ) -> bool:
        if _is_missing_value(valeur):
            return False
        paths = (champ, *aliases)
        added_paths: List[str] = []
        for path in paths:
            current = _get_path(self.payload, path)
            if _is_missing_value(current):
                _set_path(self.payload, path, valeur)
                self.completed[path] = valeur
                added_paths.append(path)
            else:
                _record_conflict_if_needed(self, path, current, valeur, source)
        if not added_paths:
            return False
        for path in added_paths:
            hyp = HypotheseResolue(
                champ=path,
                valeur=valeur,
                unite=unite,
                type_resolution=type_resolution,
                source=source,
                formule=formule,
                dependances=dict(dependances),
                justification=justification,
                niveau_confiance=niveau_confiance,
                validation=dict(validation or {}),
            )
            self.hypotheses.append(hyp)
            self.inconnues["resolues_automatiquement"].append(_jsonable(hyp))
        return True

    def unresolved(self, bucket: str, champ: str, raison: str, *, bloquant: bool = False) -> None:
        item = {"champ": champ, "raison": raison}
        if bucket not in self.inconnues:
            self.inconnues[bucket] = []
        self.inconnues[bucket].append(item)
        self.inconnues["bloquantes" if bloquant else "non_bloquantes"].append(item)


def _resoudre_puissances_et_bus(state: _ResolutionState) -> None:
    p_kw = state.number("puissance_traction_kw", "entrees.puissance_traction_kw", "analyses.systeme_complet.puissance_traction_kw")
    if p_kw is not None:
        state.add(
            "puissance_traction_w",
            p_kw * 1000.0,
            unite="W",
            type_resolution="calculable",
            source="backend.ensemble.resolution_inconnues",
            formule="puissance_traction_kw * 1000",
            dependances={"puissance_traction_kw": p_kw},
            justification="Conversion d'unite exacte.",
            niveau_confiance="exact",
        )

    p_prod = state.number(
        "production_electrique_sortie_w",
        "entrees.production_electrique_sortie_w",
        "analyses.systeme_complet.production_electrique_sortie_w",
    )
    if p_prod is not None:
        state.add(
            "puissance_bus_dc_w",
            p_prod,
            unite="W",
            type_resolution="deduite",
            source="backend.ensemble.resolution_inconnues",
            formule="puissance_bus_dc_w = production_electrique_sortie_w",
            dependances={"production_electrique_sortie_w": p_prod},
            justification="La puissance de sortie electrique alimente le bus DC si aucun bus explicite n'est fourni.",
            niveau_confiance="coherent",
        )

    p_trac_w = state.number("puissance_traction_w")
    if p_trac_w is not None:
        state.add(
            "puissance_moteur_requise_W",
            p_trac_w,
            unite="W",
            type_resolution="deduite",
            source="cahier_des_charges.pire_cas",
            formule="puissance_moteur_requise_W = puissance_traction_w",
            dependances={"puissance_traction_w": p_trac_w, "scenario": state.cdc.scenario_pire_cas},
            justification="Cible minimale de dimensionnement pour le pire cas traction pleine puissance.",
            niveau_confiance="coherent",
            aliases=("puissance_moteur_w",),
        )
        state.add(
            "puissance_bus_dc_w",
            p_trac_w,
            unite="W",
            type_resolution="deduite",
            source="cahier_des_charges.pire_cas",
            formule="puissance_bus_dc_w = puissance_traction_w",
            dependances={"puissance_traction_w": p_trac_w, "scenario": state.cdc.scenario_pire_cas},
            justification="Le scenario pire cas impose que le bus DC supporte au moins la traction pleine puissance.",
            niveau_confiance="coherent",
        )

    tension = state.number("tension_bus_dc_v", "V_bus_dc_v", "bus_dc.tension_bus_dc_v")
    if tension is None and state.cdc.tension_bus_dc_v is not None:
        tension = float(state.cdc.tension_bus_dc_v)
        state.add(
            "tension_bus_dc_v",
            tension,
            unite="V",
            type_resolution="contrainte_cdc",
            source="CahierDesChargesSTHOME.tension_bus_dc_v",
            formule="valeur imposee par le cahier des charges",
            dependances={"tension_bus_dc_v_cdc": tension},
            justification="La tension bus DC est une contrainte systeme explicite.",
            niveau_confiance="coherent",
            validation={"borne_min_v": state.cdc.tension_bus_dc_min_v, "borne_max_v": state.cdc.tension_bus_dc_max_v},
        )

    if tension is not None:
        for path in (
            "batterie.tension_bus_dc_v",
            "alternateur.tension_bus_dc_v",
            "moteur_electrique.tension_bus_dc_v",
            "composants.batterie.tension_bus_dc_v",
            "composants.alternateur.tension_bus_dc_v",
            "composants.moteur_electrique.tension_bus_dc_v",
        ):
            parent = _parent_path(path)
            if parent and isinstance(_get_path(state.payload, parent), Mapping):
                state.add(
                    path,
                    tension,
                    unite="V",
                    type_resolution="deduite",
                    source="propagation_bus_dc",
                    formule="tension sous-systeme = tension_bus_dc_v",
                    dependances={"tension_bus_dc_v": tension},
                    justification="Compatibilite electrique : le bus DC est commun aux sous-systemes.",
                    niveau_confiance="coherent",
                )

    p_bus = state.number("puissance_bus_dc_w", "P_bus_dc_design_w")
    tension = state.number("tension_bus_dc_v", "V_bus_dc_v")
    if p_bus is not None and tension is not None and tension > 0.0:
        courant = p_bus / tension
        state.add(
            "courant_bus_dc_a",
            courant,
            unite="A",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.courant_pack",
            formule="I = P / U",
            dependances={"puissance_bus_dc_w": p_bus, "tension_bus_dc_v": tension},
            justification="Relation electrique exacte en puissance DC.",
            niveau_confiance="exact",
        )


def _resoudre_rotation_et_couple(state: _ResolutionState) -> None:
    rpm = state.number(
        "rpm_moteur",
        "rpm_moteur_nominal",
        "vitesse_moteur_thermique_rpm",
        "regime_moteur_rpm",
        "moteur_thermique_definition.rpm_nominal",
        "moteur_thermique_definition.rpm",
        "analyses.moteur_thermique_definition.rpm",
        "analyses.systeme_complet.vitesse_moteur_thermique_rpm",
    )
    p_moteur = state.number(
        "puissance_moteur_w",
        "puissance_moteur_requise_W",
        "puissance_nominale_visee_w",
        "moteur_thermique_definition.puissance_visee_w",
        "moteur_thermique_definition.puissance_nominale_visee_w",
        "analyses.moteur_thermique_definition.puissance_visee_w",
        "analyses.moteur_thermique_definition.puissance_nominale_visee_w",
        "analyses.systeme_complet.puissance_moteur_requise_W",
    )
    pme = state.number(
        "pme_pa",
        "pression_moyenne_effective_pa",
        "moteur_thermique_definition.pme_nominale_pa",
        "moteur_thermique_definition.pression_moyenne_effective_pa",
        "analyses.moteur_thermique_definition.pression_moyenne_effective_pa",
    )
    if rpm is None and p_moteur is not None and pme is not None:
        candidates = [r for r in state.cdc.regimes_moteur_candidats_rpm if state.cdc.rpm_moteur_min <= r <= state.cdc.rpm_moteur_max]
        if candidates:
            rpm = min(candidates, key=lambda r: abs(r - state.cdc.rpm_moteur_prefere))
            state.add(
                "rpm_moteur_nominal",
                rpm,
                unite="rpm",
                type_resolution="optimisee",
                source="CahierDesChargesSTHOME.regimes_moteur_candidats_rpm",
                formule="argmin |rpm - rpm_prefere| dans le domaine autorise",
                dependances={
                    "domaine_rpm": candidates,
                    "rpm_prefere": state.cdc.rpm_moteur_prefere,
                    "puissance_moteur_w": p_moteur,
                    "pme_pa": pme,
                },
                justification="Regime choisi dans le domaine CDC pour permettre le dimensionnement geometrique.",
                niveau_confiance="a_valider",
                validation={"rpm_min": state.cdc.rpm_moteur_min, "rpm_max": state.cdc.rpm_moteur_max},
                aliases=("rpm_moteur", "vitesse_moteur_thermique_rpm"),
            )

    if rpm is not None and rpm > 0.0:
        omega = 2.0 * math.pi * rpm / 60.0
        state.add(
            "omega_moteur_rad_s",
            omega,
            unite="rad/s",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.pulsation",
            formule="omega = 2*pi*rpm/60",
            dependances={"rpm_moteur": rpm},
            justification="Conversion cinematique exacte.",
            niveau_confiance="exact",
        )

    omega = state.number("omega_moteur_rad_s")
    if p_moteur is not None and omega is not None and omega > 0.0:
        couple = p_moteur / omega
        state.add(
            "couple_moteur_nm",
            couple,
            unite="N.m",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.couple_moteur",
            formule="C = P / omega",
            dependances={"puissance_moteur_w": p_moteur, "omega_moteur_rad_s": omega},
            justification="Relation mecanique exacte.",
            niveau_confiance="exact",
            aliases=("couple_moteur_max_Nm",),
        )


def _resoudre_geometrie_moteur(state: _ResolutionState) -> None:
    bore = state.number("alesage_m", "moteur_thermique_definition.alesage_m")
    stroke = state.number("course_m", "moteur_thermique_definition.course_m")
    nb_cyl = state.integer("nombre_cylindres", "moteur_thermique_definition.nombre_cylindres")
    rpm = state.number(
        "rpm_moteur",
        "rpm_moteur_nominal",
        "vitesse_moteur_thermique_rpm",
        "moteur_thermique_definition.rpm_nominal",
        "moteur_thermique_definition.rpm",
        "analyses.moteur_thermique_definition.rpm",
        "analyses.systeme_complet.vitesse_moteur_thermique_rpm",
    )
    pme = state.number(
        "pme_pa",
        "pression_moyenne_effective_pa",
        "moteur_thermique_definition.pression_moyenne_effective_pa",
        "moteur_thermique_definition.pme_nominale_pa",
        "analyses.moteur_thermique_definition.pression_moyenne_effective_pa",
        "analyses.moteur_thermique_definition.pme_nominale_pa",
    )
    p_moteur = state.number(
        "puissance_moteur_w",
        "puissance_moteur_requise_W",
        "puissance_nominale_visee_w",
        "moteur_thermique_definition.puissance_visee_w",
        "moteur_thermique_definition.puissance_nominale_visee_w",
        "analyses.moteur_thermique_definition.puissance_visee_w",
        "analyses.moteur_thermique_definition.puissance_nominale_visee_w",
        "analyses.systeme_complet.puissance_moteur_requise_W",
    )

    if (bore is None or stroke is None or nb_cyl is None) and all(v is not None for v in (rpm, pme, p_moteur)):
        candidate = _chercher_geometrie_moteur(
            puissance_w=float(p_moteur),
            rpm=float(rpm),
            pme_pa=float(pme),
            bore_known=bore,
            stroke_known=stroke,
            nb_cyl_known=nb_cyl,
            cdc=state.cdc,
        )
        if candidate is not None:
            validation = {
                "domaine": candidate["domaine"],
                "objectif": candidate["objectif"],
                "criteres_rejet": candidate["criteres_rejet"],
                "erreur_relative_puissance": candidate["erreur_relative_puissance"],
            }
            if nb_cyl is None:
                state.add(
                    "nombre_cylindres",
                    candidate["nombre_cylindres"],
                    unite="",
                    type_resolution="optimisee",
                    source="resolution_geometrie_moteur",
                    formule="exploration n_cyl, alesage, course sous P=pme*Vd*rpm/120",
                    dependances={"puissance_w": p_moteur, "rpm": rpm, "pme_pa": pme},
                    justification=candidate["justification"],
                    niveau_confiance="coherent",
                    validation=validation,
                    aliases=("moteur_thermique_definition.nombre_cylindres",),
                )
            if bore is None:
                state.add(
                    "alesage_m",
                    candidate["alesage_m"],
                    unite="m",
                    type_resolution="optimisee",
                    source="resolution_geometrie_moteur",
                    formule="B = (4*Vd_cyl/(pi*S/B))^(1/3)",
                    dependances={"Vd_cyl_m3": candidate["cylindree_unitaire_m3"], "ratio_course_alesage": candidate["ratio_course_alesage"]},
                    justification=candidate["justification"],
                    niveau_confiance="coherent",
                    validation=validation,
                    aliases=("moteur_thermique_definition.alesage_m",),
                )
            if stroke is None:
                state.add(
                    "course_m",
                    candidate["course_m"],
                    unite="m",
                    type_resolution="optimisee",
                    source="resolution_geometrie_moteur",
                    formule="S = ratio_course_alesage * B",
                    dependances={"alesage_m": candidate["alesage_m"], "ratio_course_alesage": candidate["ratio_course_alesage"]},
                    justification=candidate["justification"],
                    niveau_confiance="coherent",
                    validation=validation,
                    aliases=("moteur_thermique_definition.course_m",),
                )
            bore = state.number("alesage_m")
            stroke = state.number("course_m")
            nb_cyl = state.integer("nombre_cylindres")

    if bore is not None and stroke is not None and nb_cyl is not None:
        cylindree = math.pi / 4.0 * bore * bore * stroke * nb_cyl
        state.add(
            "cylindree_totale_m3",
            cylindree,
            unite="m3",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.volume_balayage",
            formule="Vd = pi/4 * alesage^2 * course * nombre_cylindres",
            dependances={"alesage_m": bore, "course_m": stroke, "nombre_cylindres": nb_cyl},
            justification="Geometrie moteur exacte.",
            niveau_confiance="exact",
        )
        state.add(
            "cylindree_totale_cc",
            cylindree * 1_000_000.0,
            unite="cm3",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.volume_balayage",
            formule="cylindree_totale_m3 * 1e6",
            dependances={"cylindree_totale_m3": cylindree},
            justification="Conversion d'unite exacte.",
            niveau_confiance="exact",
        )

    if stroke is not None:
        state.add(
            "rayon_manivelle_m",
            stroke / 2.0,
            unite="m",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me",
            formule="rayon_manivelle = course / 2",
            dependances={"course_m": stroke},
            justification="Geometrie vilebrequin exacte.",
            niveau_confiance="exact",
        )
        if rpm is not None:
            vp = 2.0 * stroke * rpm / 60.0
            state.add(
                "vitesse_piston_m_s",
                vp,
                unite="m/s",
                type_resolution="calculable",
                source="cinematique_piston",
                formule="v_piston_moyenne = 2*course*rpm/60",
                dependances={"course_m": stroke, "rpm_moteur": rpm},
                justification="Cinematique moyenne du piston.",
                niveau_confiance="exact",
            )

    if bore is not None:
        surface = math.pi / 4.0 * bore * bore
        state.add(
            "surface_piston_m2",
            surface,
            unite="m2",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.surface_piston",
            formule="A = pi/4 * alesage^2",
            dependances={"alesage_m": bore},
            justification="Surface piston exacte.",
            niveau_confiance="exact",
        )
        pmax = state.number("pression_max_pa", "moteur_thermique_definition.pression_max_pa")
        if pmax is not None:
            state.add(
                "force_gaz_n",
                pmax * surface,
                unite="N",
                type_resolution="calculable",
                source="backend.ensemble.calcul_stho_me.force_pression",
                formule="F = pression_max_pa * surface_piston_m2",
                dependances={"pression_max_pa": pmax, "surface_piston_m2": surface},
                justification="Effort gaz calcule depuis pression et surface.",
                niveau_confiance="exact",
                aliases=("force_bielle_N",),
            )

    nb_cyl = state.integer("nombre_cylindres", "moteur_thermique_definition.nombre_cylindres")
    arch_forcee = state.get("architecture_forcee", "moteur_thermique_definition.architecture_forcee")
    arch = state.get("architecture_moteur", "architecture", "moteur_thermique_definition.architecture")
    if _is_missing_value(arch):
        if not _is_missing_value(arch_forcee):
            state.add(
                "architecture_moteur",
                arch_forcee,
                unite="",
                type_resolution="contrainte_cdc",
                source="architecture_forcee",
                formule="architecture_moteur = architecture_forcee",
                dependances={"architecture_forcee": arch_forcee},
                justification="Architecture imposee explicitement.",
                niveau_confiance="coherent",
                aliases=("moteur_thermique_definition.architecture", "architecture"),
            )
        elif nb_cyl is not None:
            chosen = _choisir_architecture(nb_cyl, state.cdc.architectures_autorisees)
            if chosen is not None:
                state.add(
                    "architecture_moteur",
                    chosen,
                    unite="",
                    type_resolution="optimisee",
                    source="CahierDesChargesSTHOME.architectures_autorisees",
                    formule="choix compatible nombre_cylindres dans architectures_autorisees",
                    dependances={"nombre_cylindres": nb_cyl, "architectures_autorisees": state.cdc.architectures_autorisees},
                    justification="Architecture retenue dans le domaine autorise, compatible avec le nombre de cylindres.",
                    niveau_confiance="a_valider",
                    aliases=("moteur_thermique_definition.architecture", "architecture"),
                )


def _resoudre_alternateur_boite(state: _ResolutionState) -> None:
    p_alt_elec = state.number("puissance_alternateur_electrique_w", "production_electrique_sortie_w", "puissance_bus_dc_w")
    eta_alt = state.number("rendement_alternateur", "rendement_alternateur_impose")
    if eta_alt is None:
        eta_alt = state.cdc.rendement_alternateur_reference
    if p_alt_elec is not None and eta_alt is not None and 0.0 < eta_alt <= 1.0:
        state.add(
            "puissance_alternateur_mecanique_w",
            p_alt_elec / eta_alt,
            unite="W",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.puissance_mecanique_requise",
            formule="P_meca_alt = P_elec_alt / rendement_alternateur",
            dependances={"puissance_alternateur_electrique_w": p_alt_elec, "rendement_alternateur": eta_alt},
            justification="Puissance mecanique alternateur calculee depuis rendement fourni ou CDC.",
            niveau_confiance="exact" if state.number("rendement_alternateur", "rendement_alternateur_impose") is not None else "coherent",
        )

    rpm_moteur = state.number("rpm_moteur", "rpm_moteur_nominal", "vitesse_moteur_thermique_rpm")
    rpm_alt = state.number("vitesse_alternateur_rpm", "rpm_alternateur_cible")
    rapport = state.number("rapport_vitesse_alt_sur_moteur", "rapport_boite_alt")
    if rpm_moteur is not None and rpm_alt is not None and rpm_moteur > 0.0:
        ratio = rpm_alt / rpm_moteur
        if state.cdc.rapport_boite_min <= ratio <= state.cdc.rapport_boite_max:
            state.add(
                "rapport_vitesse_alt_sur_moteur",
                ratio,
                unite="",
                type_resolution="calculable",
                source="chaine_mecanique_alternateur",
                formule="rapport = rpm_alternateur / rpm_moteur",
                dependances={"vitesse_alternateur_rpm": rpm_alt, "rpm_moteur": rpm_moteur},
                justification="Compatibilite cinematique entre moteur thermique, boite et alternateur.",
                niveau_confiance="exact",
                validation={"rapport_min": state.cdc.rapport_boite_min, "rapport_max": state.cdc.rapport_boite_max},
                aliases=("rapport_boite_alt",),
            )
        else:
            state.unresolved(
                "conflits",
                "rapport_vitesse_alt_sur_moteur",
                f"Rapport calcule {ratio:.6g} hors domaine CDC [{state.cdc.rapport_boite_min}, {state.cdc.rapport_boite_max}].",
                bloquant=True,
            )
    elif rpm_moteur is not None and rapport is not None:
        state.add(
            "vitesse_alternateur_rpm",
            rpm_moteur * rapport,
            unite="rpm",
            type_resolution="calculable",
            source="chaine_mecanique_alternateur",
            formule="rpm_alternateur = rpm_moteur * rapport",
            dependances={"rpm_moteur": rpm_moteur, "rapport_vitesse_alt_sur_moteur": rapport},
            justification="Propagation cinematique moteur-boite-alternateur.",
            niveau_confiance="exact",
        )


def _resoudre_batterie(state: _ResolutionState) -> None:
    p_moy = state.number("puissance_moyenne_w", "puissance_moyenne_W")
    duree_h = state.number("duree_h", "temps_usage_h")
    if p_moy is not None and duree_h is not None and duree_h >= 0.0:
        state.add(
            "energie_batterie_kwh",
            p_moy * duree_h / 1000.0,
            unite="kWh",
            type_resolution="calculable",
            source="dimensionnement_energie_batterie",
            formule="E_kWh = P_moyenne_W * duree_h / 1000",
            dependances={"puissance_moyenne_w": p_moy, "duree_h": duree_h},
            justification="Energie utile calculee depuis puissance moyenne et duree.",
            niveau_confiance="exact",
            aliases=("energie_utile_imposee_kwh",),
        )

    distance = state.number("distance_km")
    conso = state.number("conso_kwh_km")
    if distance is not None and conso is not None:
        state.add(
            "energie_batterie_kwh",
            distance * conso * (1.0 + state.cdc.marge_wltp),
            unite="kWh",
            type_resolution="calculable",
            source="cahier_des_charges.WLTP",
            formule="E = distance_km * conso_kwh_km * (1 + marge_wltp)",
            dependances={"distance_km": distance, "conso_kwh_km": conso, "marge_wltp": state.cdc.marge_wltp},
            justification="Dimensionnement WLTP avec marge de securite CDC.",
            niveau_confiance="coherent",
            aliases=("energie_utile_imposee_kwh",),
        )

    tension = state.number("tension_bus_dc_v")
    u_cell = state.number("cellule_tension_nominale_v", "cellule.u_nominale_v")
    e_kwh = state.number("energie_batterie_kwh", "energie_utile_imposee_kwh")
    cap_ah = state.number("cellule_capacite_ah", "cellule.capacite_ah")
    if tension is not None and u_cell is not None and u_cell > 0.0:
        n_serie = int(math.ceil(tension / u_cell))
        state.add(
            "nb_cellules_serie",
            n_serie,
            unite="",
            type_resolution="calculable",
            source="backend.ensemble.calcul_stho_me.nb_cellules_serie",
            formule="ceil(tension_bus_dc_v / cellule_tension_nominale_v)",
            dependances={"tension_bus_dc_v": tension, "cellule_tension_nominale_v": u_cell},
            justification="Nombre de cellules serie calcule depuis la tension de cellule fournie.",
            niveau_confiance="exact",
        )
        if e_kwh is not None and cap_ah is not None and cap_ah > 0.0:
            e_pack_wh = e_kwh * 1000.0
            e_string_wh = n_serie * u_cell * cap_ah
            if e_string_wh > 0.0:
                n_par = int(math.ceil(e_pack_wh / e_string_wh))
                state.add(
                    "nb_cellules_parallele",
                    n_par,
                    unite="",
                    type_resolution="calculable",
                    source="backend.ensemble.calcul_stho_me.nb_cellules_parallele",
                    formule="ceil(E_pack_Wh / (Nserie * Ucell * Ahcell))",
                    dependances={"energie_batterie_kwh": e_kwh, "nb_cellules_serie": n_serie, "cellule_tension_nominale_v": u_cell, "cellule_capacite_ah": cap_ah},
                    justification="Nombre de branches paralleles calcule depuis energie et donnees cellule fournies.",
                    niveau_confiance="exact",
                )


def _resoudre_materiaux(state: _ResolutionState) -> None:
    if not state.cdc.autoriser_choix_materiau:
        return
    existing = state.get("materiau_cle", "materiau", "materiau_structure_cle")
    if not _is_missing_value(existing):
        mat = _get_material(str(existing))
        if mat is None:
            state.unresolved("restantes_catalogue", "materiau_cle", f"Materiau {existing!r} absent du catalogue materiaux.py.", bloquant=False)
            return
        _injecter_props_materiau(state, str(existing), mat, source="materiau_cle")
        return

    contrainte = state.number("contrainte_service_pa", "contrainte_admissible_pa")
    if contrainte is None:
        contrainte = state.cdc.contrainte_service_pa
    temperature = state.number("temperature_service_max_c")
    if temperature is None:
        temperature = state.cdc.temperature_service_max_c
    if contrainte is None and temperature is None:
        state.unresolved(
            "restantes_physiques",
            "materiau_cle",
            "Choix materiau indetermine sans contrainte de service, temperature ou materiau impose.",
            bloquant=False,
        )
        return

    best = _choisir_materiau(state.cdc, contrainte, temperature)
    if best is None:
        state.unresolved(
            "restantes_catalogue",
            "materiau_cle",
            "Aucun materiau autorise du catalogue ne valide les contraintes fournies.",
            bloquant=True,
        )
        return
    cle, mat, validation = best
    state.add(
        "materiau_cle",
        cle,
        unite="",
        type_resolution="materiau",
        source="backend.ensemble.materiaux",
        formule="selection catalogue sous contraintes CDC",
        dependances={"materiaux_autorises": state.cdc.materiaux_autorises, "contrainte_service_pa": contrainte, "temperature_service_max_c": temperature},
        justification="Materiau retenu parmi les materiaux autorises et valides par les contraintes disponibles.",
        niveau_confiance="a_valider",
        validation=validation,
        aliases=("materiau_structure_cle",),
    )
    _injecter_props_materiau(state, cle, mat, source="backend.ensemble.materiaux")


def _chercher_geometrie_moteur(
    *,
    puissance_w: float,
    rpm: float,
    pme_pa: float,
    bore_known: Optional[float],
    stroke_known: Optional[float],
    nb_cyl_known: Optional[int],
    cdc: CahierDesChargesSTHOME,
) -> Optional[Dict[str, Any]]:
    if puissance_w <= 0.0 or rpm <= 0.0 or pme_pa <= 0.0:
        return None
    vd_total = puissance_w * 120.0 / (pme_pa * rpm)
    ratios = _linspace(cdc.ratio_course_alesage_min, cdc.ratio_course_alesage_max, 21)
    n_values = [nb_cyl_known] if nb_cyl_known is not None else list(cdc.nombres_cylindres_autorises)
    best: Optional[Dict[str, Any]] = None
    rejected = 0
    criteria = [
        "alesage hors bornes CDC",
        "course hors bornes CDC",
        "ratio course/alesage hors bornes CDC",
        "vitesse piston au-dessus de la limite CDC",
        "valeur fournie incompatible avec le candidat",
    ]
    for n in n_values:
        if n is None or n <= 0:
            continue
        vd_cyl = vd_total / n
        for ratio in ratios:
            if bore_known is not None and stroke_known is not None:
                bore = bore_known
                stroke = stroke_known
                ratio_eff = stroke / bore if bore > 0.0 else ratio
            elif bore_known is not None:
                bore = bore_known
                stroke = vd_cyl / (math.pi / 4.0 * bore * bore)
                ratio_eff = stroke / bore if bore > 0.0 else ratio
            elif stroke_known is not None:
                stroke = stroke_known
                bore = math.sqrt(vd_cyl / (math.pi / 4.0 * stroke))
                ratio_eff = stroke / bore if bore > 0.0 else ratio
            else:
                bore = (4.0 * vd_cyl / (math.pi * ratio)) ** (1.0 / 3.0)
                stroke = ratio * bore
                ratio_eff = ratio

            piston_speed = 2.0 * stroke * rpm / 60.0
            valid = (
                cdc.alesage_min_m <= bore <= cdc.alesage_max_m
                and cdc.course_min_m <= stroke <= cdc.course_max_m
                and cdc.ratio_course_alesage_min <= ratio_eff <= cdc.ratio_course_alesage_max
                and (cdc.vitesse_piston_max_ms is None or piston_speed <= cdc.vitesse_piston_max_ms)
            )
            if not valid:
                rejected += 1
                continue
            p_calc = pme_pa * (math.pi / 4.0 * bore * bore * stroke * n) * rpm / 120.0
            error = abs(p_calc - puissance_w) / max(abs(puissance_w), 1e-12)
            objective = error + 0.02 * abs(ratio_eff - cdc.ratio_course_alesage_cible) + 0.002 * n
            candidate = {
                "nombre_cylindres": int(n),
                "alesage_m": float(bore),
                "course_m": float(stroke),
                "ratio_course_alesage": float(ratio_eff),
                "cylindree_unitaire_m3": float(vd_cyl),
                "cylindree_totale_m3": float(vd_total),
                "vitesse_piston_m_s": float(piston_speed),
                "erreur_relative_puissance": float(error),
                "score_objectif": float(objective),
                "objectif": "minimiser erreur puissance, ecart au ratio S/B cible et complexite nombre cylindres",
                "criteres_rejet": criteria,
                "domaine": {
                    "nombre_cylindres": list(n_values),
                    "alesage_m": [cdc.alesage_min_m, cdc.alesage_max_m],
                    "course_m": [cdc.course_min_m, cdc.course_max_m],
                    "ratio_course_alesage": [cdc.ratio_course_alesage_min, cdc.ratio_course_alesage_max],
                    "rpm": rpm,
                    "pme_pa": pme_pa,
                    "candidats_rejetes": rejected,
                },
                "justification": "Candidat minimisant l'objectif dans le domaine explicite du cahier des charges.",
            }
            if best is None or candidate["score_objectif"] < best["score_objectif"]:
                best = candidate
    return best


def _choisir_architecture(nb_cyl: int, architectures: Sequence[str]) -> Optional[str]:
    normalized = {str(a).lower(): str(a) for a in architectures}
    if nb_cyl <= 6:
        for key in ("l", "ligne", "inline"):
            if key in normalized:
                return normalized[key]
    if nb_cyl >= 6:
        for key in ("v", "vee"):
            if key in normalized:
                return normalized[key]
    return str(architectures[0]) if architectures else None


def _choisir_materiau(
    cdc: CahierDesChargesSTHOME,
    contrainte_pa: Optional[float],
    temperature_c: Optional[float],
) -> Optional[Tuple[str, Any, Dict[str, Any]]]:
    candidates: List[Tuple[float, str, Any, Dict[str, Any]]] = []
    for cle in cdc.materiaux_autorises:
        mat = _get_material(cle)
        if mat is None:
            continue
        famille = getattr(mat, "famille", None)
        if cdc.familles_materiaux_autorisees and famille not in cdc.familles_materiaux_autorisees:
            continue
        re_pa = _material_yield(mat)
        temp_max = getattr(mat, "temperature_service_max_c", None)
        ok_stress = contrainte_pa is None or (re_pa is not None and re_pa / max(cdc.facteur_securite_materiau, 1e-12) >= contrainte_pa)
        ok_temp = temperature_c is None or temp_max is None or temperature_c <= float(temp_max)
        validation = {
            "famille": famille,
            "limite_elastique_pa": re_pa,
            "contrainte_service_pa": contrainte_pa,
            "facteur_securite": cdc.facteur_securite_materiau,
            "temperature_service_max_c": temp_max,
            "temperature_requise_c": temperature_c,
            "respecte_contrainte": bool(ok_stress),
            "respecte_temperature": bool(ok_temp),
        }
        if not (ok_stress and ok_temp):
            continue
        density = getattr(mat, "densite_kg_m3", None)
        score = float(density) if _is_number(density) else 1e12
        candidates.append((score, cle, mat, validation))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    _, cle, mat, validation = candidates[0]
    return cle, mat, validation


def _injecter_props_materiau(state: _ResolutionState, cle: str, mat: Any, *, source: str) -> None:
    props = {
        "densite_materiau_kg_m3": (getattr(mat, "densite_kg_m3", None), "kg/m3"),
        "module_young_pa": (_material_value(getattr(mat, "module_young_pa", None), mode="typique"), "Pa"),
        "limite_elastique_pa": (_material_yield(mat), "Pa"),
        "limite_fatigue_pa": (_material_value(getattr(mat, "limite_fatigue_pa", None), mode="min"), "Pa"),
        "alpha_dilatation_1_k": (_material_value(getattr(mat, "alpha_dilatation_1_k", None), mode="typique"), "1/K"),
        "conductivite_thermique_w_mk": (_material_value(getattr(mat, "conductivite_thermique_w_mk", None), mode="typique"), "W/(m.K)"),
    }
    for champ, (value, unit) in props.items():
        if value is None:
            continue
        state.add(
            champ,
            value,
            unite=unit,
            type_resolution="materiau",
            source=source,
            formule=f"{champ} extrait du materiau {cle}",
            dependances={"materiau_cle": cle},
            justification="Propriete issue du module materiaux.py, conservee avec sa source.",
            niveau_confiance="a_valider" if champ == "limite_fatigue_pa" else "coherent",
            validation={"materiau_cle": cle, "nom": getattr(mat, "nom", cle), "famille": getattr(mat, "famille", None)},
        )


def _classer_inconnues_restantes(state: _ResolutionState) -> None:
    requirements = {
        "omega_moteur_rad_s": (
            ("rpm_moteur", "rpm_moteur_nominal", "vitesse_moteur_thermique_rpm"),
            "inconnue_calculable",
            "Calculable si le regime moteur est fourni ou resolu.",
            False,
        ),
        "couple_moteur_nm": (
            ("puissance_moteur_w", "puissance_moteur_requise_W", "omega_moteur_rad_s"),
            "inconnue_calculable",
            "Calculable si puissance et omega moteur sont connus.",
            True,
        ),
        "cylindree_totale_m3": (
            ("alesage_m", "course_m", "nombre_cylindres"),
            "inconnue_optimisable",
            "Optimisable si puissance, regime et PME sont disponibles ; sinon geometrie moteur indeterminee.",
            True,
        ),
        "courant_bus_dc_a": (
            ("puissance_bus_dc_w", "tension_bus_dc_v"),
            "inconnue_calculable",
            "Calculable si puissance et tension bus DC sont connues.",
            True,
        ),
        "nb_cellules_parallele": (
            ("energie_batterie_kwh", "nb_cellules_serie", "cellule_capacite_ah"),
            "inconnue_catalogue",
            "Necessite les donnees cellule constructeur pour fermer le pack batterie.",
            False,
        ),
    }
    for champ, (deps, typ, reason, blocking) in requirements.items():
        if not _is_missing_value(_get_path(state.payload, champ)):
            continue
        missing = [dep for dep in deps if _is_missing_value(state.get(dep))]
        item = {
            "champ": champ,
            "type_inconnue": typ,
            "raison": reason,
            "donnees_manquantes": missing,
        }
        if typ == "inconnue_catalogue":
            state.inconnues["restantes_catalogue"].append(item)
        elif typ == "inconnue_optimisable":
            state.inconnues["restantes_physiques"].append(item)
        else:
            state.inconnues["restantes_physiques"].append(item)
        state.inconnues["bloquantes" if blocking else "non_bloquantes"].append(item)

    for conflict in state.conflits:
        state.inconnues["conflits"].append(conflict)
        state.inconnues["bloquantes"].append(conflict)

    for key in list(state.inconnues):
        state.inconnues[key] = _dedup_items(state.inconnues[key])


def _score_puissance(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    p = _first_number(payload, {}, "puissance_bus_dc_w", "P_bus_dc_design_w", "puissance_moteur_requise_W")
    u = _first_number(payload, {}, "tension_bus_dc_v", "V_bus_dc_v")
    i = _first_number(payload, {}, "courant_bus_dc_a")
    score = 0.35
    if p is not None:
        score += 0.25
    else:
        actions.append({"champ": "puissance_bus_dc_w", "action": "fournir ou deduire une puissance de bus"})
    if u is not None:
        score += 0.20
        if not (cdc.tension_bus_dc_min_v <= u <= cdc.tension_bus_dc_max_v):
            blockers.append({"champ": "tension_bus_dc_v", "raison": "hors bornes CDC"})
            return 0.0
    else:
        actions.append({"champ": "tension_bus_dc_v", "action": "fournir une tension bus DC ou une contrainte CDC"})
    if p is not None and u is not None and i is not None and u > 0.0:
        expected = p / u
        if _relative_error(i, expected) <= 0.05:
            score += 0.20
        else:
            blockers.append({"champ": "courant_bus_dc_a", "raison": "incoherent avec P/U"})
            score -= 0.30
    elif p is not None and u is not None:
        score += 0.10
    return _clamp01(score)


def _score_energie(payload: Mapping[str, Any], actions: List[Dict[str, Any]]) -> float:
    e = _first_number(payload, {}, "energie_batterie_kwh", "energie_utile_imposee_kwh")
    distance = _first_number(payload, {}, "distance_km")
    conso = _first_number(payload, {}, "conso_kwh_km")
    if e is not None:
        return 1.0
    if distance is not None and conso is not None:
        return 0.75
    actions.append({"champ": "energie_batterie_kwh", "action": "fournir distance/conso ou puissance moyenne/duree"})
    return 0.35


def _score_mecanique(payload: Mapping[str, Any], blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    rpm = _first_number(payload, {}, "rpm_moteur", "rpm_moteur_nominal", "vitesse_moteur_thermique_rpm")
    omega = _first_number(payload, {}, "omega_moteur_rad_s")
    couple = _first_number(payload, {}, "couple_moteur_nm")
    p = _first_number(payload, {}, "puissance_moteur_w", "puissance_moteur_requise_W")
    score = 0.25
    if rpm is not None:
        score += 0.25
    if rpm is not None and omega is not None and _relative_error(omega, 2.0 * math.pi * rpm / 60.0) <= 0.02:
        score += 0.20
    elif rpm is not None and omega is not None:
        blockers.append({"champ": "omega_moteur_rad_s", "raison": "incoherent avec rpm"})
    if p is not None and omega is not None and couple is not None and omega > 0.0:
        if _relative_error(couple, p / omega) <= 0.05:
            score += 0.30
        else:
            blockers.append({"champ": "couple_moteur_nm", "raison": "incoherent avec P/omega"})
    else:
        actions.append({"champ": "couple_moteur_nm", "action": "completer puissance et regime"})
    return _clamp01(score)


def _score_thermique(payload: Mapping[str, Any], actions: List[Dict[str, Any]]) -> float:
    losses = _first_number(payload, {}, "pertes_thermiques_w", "pertes_totales_w")
    cooling = _first_number(payload, {}, "puissance_refroidissement_w", "flux_refroidissement_w")
    if losses is not None and cooling is not None:
        return 1.0 if cooling >= losses else 0.35
    if losses is not None:
        actions.append({"champ": "puissance_refroidissement_w", "action": "dimensionner le refroidissement depuis les pertes"})
        return 0.65
    return 0.45


def _score_geometrie(payload: Mapping[str, Any], blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    bore = _first_number(payload, {}, "alesage_m")
    stroke = _first_number(payload, {}, "course_m")
    nb = _first_number(payload, {}, "nombre_cylindres")
    vd = _first_number(payload, {}, "cylindree_totale_m3")
    if bore is not None and stroke is not None and nb is not None:
        calc = math.pi / 4.0 * bore * bore * stroke * nb
        if vd is not None and _relative_error(vd, calc) > 0.05:
            blockers.append({"champ": "cylindree_totale_m3", "raison": "incoherente avec alesage/course/nombre_cylindres"})
            return 0.25
        return 1.0 if vd is not None else 0.85
    actions.append({"champ": "geometrie_moteur", "action": "resoudre alesage/course/nombre_cylindres"})
    return 0.35


def _score_materiaux(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, actions: List[Dict[str, Any]]) -> float:
    mat = _first_non_missing(payload, {}, "materiau_cle", "materiau_structure_cle")
    density = _first_number(payload, {}, "densite_materiau_kg_m3")
    young = _first_number(payload, {}, "module_young_pa")
    re_pa = _first_number(payload, {}, "limite_elastique_pa")
    score = 0.30
    if not _is_missing_value(mat):
        score += 0.30
    else:
        actions.append({"champ": "materiau_cle", "action": "fournir materiau ou contraintes autorisant le choix catalogue"})
    if density is not None:
        score += 0.15
    if young is not None:
        score += 0.10
    if re_pa is not None:
        score += 0.15
        if cdc.contrainte_service_pa is not None and re_pa / max(cdc.facteur_securite_materiau, 1e-12) < cdc.contrainte_service_pa:
            score -= 0.40
    return _clamp01(score)


def _score_cao(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, actions: List[Dict[str, Any]]) -> float:
    sw = _first_non_missing(payload, {}, "solidworks_ready", "cao.solidworks_ready", "cao.solidworks_ready_minimal")
    if sw is True:
        return 1.0
    bore = _first_number(payload, {}, "alesage_m")
    stroke = _first_number(payload, {}, "course_m")
    mat = _first_non_missing(payload, {}, "materiau_cle")
    score = 0.25
    if bore is not None and stroke is not None:
        score += 0.35
    if not _is_missing_value(mat):
        score += 0.20
    if cdc.compatibilite_solidworks_requise and sw is not True:
        actions.append({"champ": "cao.solidworks_ready", "action": "generer/valider les cotes CAO detaillees"})
    return _clamp01(score)


def _score_cdc(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    score = 0.65
    duty = _first_number(payload, {}, "duty_cycle_moteur_thermique")
    if duty is not None:
        if duty <= cdc.duty_cycle_moteur_thermique_max:
            score += 0.15
        else:
            blockers.append({"champ": "duty_cycle_moteur_thermique", "raison": "depasse 50% dans le pire cas"})
            score -= 0.35
    else:
        actions.append({"champ": "duty_cycle_moteur_thermique", "action": "verifier le pire cas batterie vide + traction pleine puissance"})
    if cdc.systeme_multi_energies:
        score += 0.10
    if cdc.marge_wltp >= 0.20:
        score += 0.10
    return _clamp01(score)


def _coerce_cdc(value: CahierDesChargesSTHOME | Mapping[str, Any] | None) -> CahierDesChargesSTHOME:
    if isinstance(value, CahierDesChargesSTHOME):
        return value
    if isinstance(value, Mapping):
        allowed = set(CahierDesChargesSTHOME.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in value.items() if k in allowed}
        for key in ("nombres_cylindres_autorises", "regimes_moteur_candidats_rpm", "architectures_autorisees", "materiaux_autorises", "familles_materiaux_autorisees"):
            if key in kwargs and kwargs[key] is not None and not isinstance(kwargs[key], tuple):
                kwargs[key] = tuple(kwargs[key])
        return CahierDesChargesSTHOME(**kwargs)
    return CahierDesChargesSTHOME()


def _deepcopy_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    return {}


def _deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(left)
    for key, value in right.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(dict(out[key]), dict(value))
        else:
            out[key] = copy.deepcopy(value)
    return out


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "-", "none", "null", "inconnu", "unknown", "n/a"}:
        return True
    return False


def _get_path(data: Mapping[str, Any] | None, path: str) -> Any:
    if not isinstance(data, Mapping) or not path:
        return None
    if path in data:
        return data[path]
    current: Any = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    if not path:
        return
    parts = path.split(".")
    current: Dict[str, Any] = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _parent_path(path: str) -> str:
    parts = path.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else ""


def _first_non_missing(payload: Mapping[str, Any], rapports: Mapping[str, Any], *paths: str) -> Any:
    for path in paths:
        for root in (payload, rapports):
            value = _get_path(root, path)
            if not _is_missing_value(value):
                return value
    return None


def _first_number(payload: Mapping[str, Any], rapports: Mapping[str, Any], *paths: str) -> Optional[float]:
    value = _first_non_missing(payload, rapports, *paths)
    if _is_number(value):
        return float(value)
    return None


def _record_conflict_if_needed(state: _ResolutionState, path: str, current: Any, proposed: Any, source: str) -> None:
    if _is_number(current) and _is_number(proposed):
        if _relative_error(float(current), float(proposed)) > 0.05:
            state.conflits.append(
                {
                    "champ": path,
                    "type_inconnue": "inconnue_conflit",
                    "valeur_existante": current,
                    "valeur_calculee": proposed,
                    "source_calculee": source,
                    "raison": "Valeur existante incompatible avec la valeur resolue.",
                }
            )
    elif current != proposed and not _is_missing_value(current) and not _is_missing_value(proposed):
        state.conflits.append(
            {
                "champ": path,
                "type_inconnue": "inconnue_conflit",
                "valeur_existante": current,
                "valeur_calculee": proposed,
                "source_calculee": source,
                "raison": "Valeur existante incompatible avec la valeur resolue.",
            }
        )


def _relative_error(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _linspace(start: float, stop: float, count: int) -> List[float]:
    if count <= 1:
        return [float(start)]
    step = (stop - start) / float(count - 1)
    return [start + i * step for i in range(count)]


def _dedup_items(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        serial = repr(sorted(_jsonable(item).items()))
        if serial in seen:
            continue
        seen.add(serial)
        out.append(dict(_jsonable(item)))
    return out


def _material_value(value: Any, *, mode: str) -> Optional[float]:
    if value is None:
        return None
    if _is_number(value):
        return float(value)
    try:
        from backend.ensemble.materiaux import valeur as material_valeur  # type: ignore

        result = material_valeur(value, mode=mode)
        return float(result) if _is_number(result) else None
    except Exception:
        for attr in ("mini", "maxi"):
            if hasattr(value, attr):
                mini = getattr(value, "mini", None)
                maxi = getattr(value, "maxi", None)
                if _is_number(mini) and _is_number(maxi):
                    if mode == "min":
                        return float(mini)
                    if mode == "max":
                        return float(maxi)
                    return 0.5 * (float(mini) + float(maxi))
        return None


def _material_yield(mat: Any) -> Optional[float]:
    method = getattr(mat, "limite_elastique_effective_pa", None)
    if callable(method):
        try:
            value = method(mode="min")
            return float(value) if _is_number(value) else None
        except Exception:
            pass
    return _material_value(getattr(mat, "limite_elastique_pa", None), mode="min")


def _get_material(cle: str) -> Any:
    try:
        from backend.ensemble.materiaux import get_materiau  # type: ignore

        return get_materiau(cle)
    except Exception:
        return None
