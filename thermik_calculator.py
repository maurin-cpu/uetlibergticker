import math
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# METEOROLOGISCHE KONSTANTEN
# ============================================================================
G = 9.81              # Erdbeschleunigung (m/s^2)
CP = 1005.0           # Spezifische Wärmekapazität trockener Luft (J/(kg*K))
R_D = 287.05          # Gaskonstante für trockene Luft (J/(kg*K))
L_V = 2.5e6           # Verdampfungswärme Wasser (J/kg)
DALR = 0.0098         # Trockenadiabatischer Temperaturgradient (K/m) (~1°C/100m)
SALR = 0.006          # Feuchtadiabatischer Gradient (K/m) (vereinfacht, ~0.6°C/100m)
RHO = 1.1             # Vereinfachte Luftdichte auf typischer Starthöhe (kg/m^3)
MU = 0.0002           # Entrainment-Rate (m^-1) - Rate der Einmischung von Umgebungsluft


def calculate_dewpoint(temp_c: float, rh_percent: float) -> float:
    """Berechnet den Taupunkt mittels Magnus-Formel."""
    if temp_c is None or rh_percent is None or rh_percent <= 0:
        return None
    A = 17.625
    B = 243.04
    alpha = math.log(rh_percent / 100.0) + ((A * temp_c) / (B + temp_c))
    return (B * alpha) / (A - alpha)


def calculate_lcl_approx(temp_c: float, dewpoint_c: float, elevation_m: float) -> float:
    """Näherungsweise Berechnung des Lifting Condensation Level (Wolkenbasis in m.ü.M.).
    Faustregel: (T - Td) * 125 = LCL in Metern über Grund."""
    if temp_c is None or dewpoint_c is None:
        return None
    spread = max(0, temp_c - dewpoint_c)
    lcl_agl = spread * 125.0
    return elevation_m + lcl_agl


def estimate_sensible_heat_flux(shortwave_radiation: float, sunshine_duration_s: float) -> float:
    """
    Fallback-Schätzung des sensiblen Wärmeflusses (H) aus der Globalstrahlung.

    Physikalische Annahme: Ca. 30% der eintreffenden Sonnenergie erwärmt die Luft
    direkt (empirischer Bowen-Ratio-Ansatz für mitteleuropäische Verhältnisse).
    Der Rest geht in Bodenwärme, Verdunstung und langwellige Abstrahlung.
    Gewichtet mit der tatsächlichen Sonnenscheindauer der Stunde.

    Formel: H_estimated = shortwave_radiation * 0.3 * sun_factor
    """
    if shortwave_radiation is None or shortwave_radiation <= 0:
        return 0.0
    sun_factor = 1.0
    if sunshine_duration_s is not None:
        sun_factor = min(1.0, max(0.0, sunshine_duration_s / 3600.0))
    return shortwave_radiation * 0.3 * sun_factor


def interpolate_temp_at_height(elevation_ref: float, profile: List[Dict]) -> Optional[float]:
    """
    Elevated Heat Source: Interpoliert die Temperatur auf der Referenzhöhe
    aus dem vertikalen Temperaturprofil (Druckniveau-Daten).

    Für alpine Startplätze ist das entscheidend, da temperature_2m sich auf das
    Modellgelände bezieht (oft im Tal), während der Startplatz höher liegt.
    Wir interpolieren linear zwischen den beiden Druckniveaus, die die
    Referenzhöhe einschliessen.

    Args:
        elevation_ref: Referenzhöhe des Startplatzes (m MSL)
        profile: Liste von {'height': m, 'temp': °C} Dictionaries

    Returns:
        Interpolierte Temperatur in °C oder None wenn keine Daten verfügbar
    """
    if not profile:
        return None

    sorted_p = sorted(
        [p for p in profile if p.get('height') is not None and p.get('temp') is not None],
        key=lambda x: x['height']
    )
    if not sorted_p:
        return None

    # Finde die zwei Schichten, die elevation_ref einschliessen
    below = None
    above = None
    for layer in sorted_p:
        if layer['height'] <= elevation_ref:
            below = layer
        elif above is None:
            above = layer

    # Randfall: elevation_ref liegt unter oder über allen Profildaten
    if below is None and above is None:
        return None
    if below is None:
        return above['temp']
    if above is None:
        return below['temp']

    # Lineare Interpolation zwischen den beiden einschliessenden Schichten
    dh = above['height'] - below['height']
    if dh <= 0:
        return below['temp']
    frac = (elevation_ref - below['height']) / dh
    return below['temp'] + frac * (above['temp'] - below['temp'])


def calculate_thermal_profile(
    surface_temp: float,
    surface_dewpoint: float,
    elevation_m: float,
    pressure_levels_data: List[Dict],
    boundary_layer_height_agl: float = None,
    sunshine_duration_s: float = None,
    surface_sensible_heat_flux: float = None,
    surface_latent_heat_flux: float = None,
    shortwave_radiation: float = None,
) -> Dict:
    """
    Berechnet das Thermik-Profil mit physikalisch fundiertem Modell.

    Implementiert folgende Konzepte (angelehnt an RegTherM):
    1. Elevated Heat Source - Paketaufstieg startet auf Referenzhöhe (elevation_m)
    2. Entrainment - Einmischung von Umgebungsluft (mu = 0.0002 m^-1)
    3. Deardorff w* - Konvektionsgeschwindigkeit aus sensiblem Wärmefluss
    4. Dual w*-Strategie - Minimum aus Parcel-w* und Deardorff-w* (konservativ)
    5. Bodenfeuchte-Bremse - Rating-Reduktion bei nassem Boden (LE > H)

    Args:
        surface_temp: Temperatur 2m über Grund am Gitterpunkt (°C)
        surface_dewpoint: Taupunkt am Startplatz (°C)
        elevation_m: Referenzhöhe des Startplatzes (m MSL)
        pressure_levels_data: Liste von {'height', 'temp', 'pressure'} Dictionaries
        boundary_layer_height_agl: Grenzschichthöhe über Grund (m)
        sunshine_duration_s: Sonnenscheindauer in Sekunden (0-3600)
        surface_sensible_heat_flux: Sensibler Wärmefluss (W/m²), positiv = aufwärts
        surface_latent_heat_flux: Latenter Wärmefluss (W/m²), positiv = aufwärts
        shortwave_radiation: Globalstrahlung (W/m²) - für Fallback-Schätzung von H

    Returns:
        Dict mit max_height, lcl, climb_rate, rating, ti_profile, diagnostics, data_warnings
    """
    data_warnings = []

    if surface_temp is None:
        return {'error': 'Fehlende Bodentemperatur'}

    # Profil sortiert von unten nach oben (nur gültige Einträge)
    profile = sorted(
        [p for p in pressure_levels_data
         if p.get('height') is not None and p.get('temp') is not None],
        key=lambda x: x['height']
    )

    # =========================================================================
    # 1. ELEVATED HEAT SOURCE: Starttemperatur auf Referenzhöhe bestimmen
    # =========================================================================
    # Statt temperature_2m (bezieht sich auf Modellgelände, oft im Talboden)
    # nutzen wir die interpolierte Temperatur auf der tatsächlichen Starthöhe
    # aus dem vertikalen Profil. Das ist physikalisch korrekter für Hangstarts.
    start_temp = interpolate_temp_at_height(elevation_m, profile)
    if start_temp is None:
        # Fallback: Nutze temperature_2m direkt
        start_temp = surface_temp
        data_warnings.append(
            "Keine Profildaten für Starthöhe verfügbar - nutze temperature_2m als Fallback"
        )

    # =========================================================================
    # 2. SENSIBLER WÄRMEFLUSS (H) - mit zweistufigem Fallback
    # =========================================================================
    # Primär: surface_sensible_heat_flux direkt von der API (z.B. icon_seamless)
    # Fallback: Empirische Schätzung aus Globalstrahlung × 0.3 × Sonnenfaktor
    H = surface_sensible_heat_flux
    h_is_estimated = False

    # Prüfe ob H gültig ist (nicht None, nicht NaN)
    h_valid = H is not None and not (isinstance(H, float) and math.isnan(H))

    if not h_valid:
        # Fallback: Schätze H aus Globalstrahlung und Sonnenscheindauer
        H = estimate_sensible_heat_flux(shortwave_radiation, sunshine_duration_s)
        h_is_estimated = True
        if H > 0:
            data_warnings.append(
                f"Sensibler Wärmefluss aus Globalstrahlung geschätzt: {H:.0f} W/m²"
            )
        else:
            data_warnings.append(
                "Kein sensibler Wärmefluss verfügbar (weder API noch Globalstrahlung)"
            )

    # Negativen Flux abfangen (nachts fliesst Wärme vom Boden ab -> keine Thermik)
    H = max(0.0, H)

    # =========================================================================
    # 3. LATENTER WÄRMEFLUSS (LE) - für Bodenfeuchte-Bremse
    # =========================================================================
    # Der latente Wärmefluss zeigt, wieviel Energie in Verdunstung geht.
    # Fehlt dieser Wert, überspringen wir die Bodenfeuchte-Bremse.
    LE = surface_latent_heat_flux
    le_valid = LE is not None and not (isinstance(LE, float) and math.isnan(LE))

    if not le_valid:
        LE = 0.0
        data_warnings.append(
            "Latenter Wärmefluss nicht verfügbar - Bodenfeuchte-Bremse wird übersprungen"
        )

    # =========================================================================
    # 4. LCL (Wolkenbasis) berechnen
    # =========================================================================
    lcl_msl = None
    if surface_dewpoint is not None:
        lcl_msl = calculate_lcl_approx(start_temp, surface_dewpoint, elevation_m)

    # =========================================================================
    # 5. PAKETAUFSTIEG MIT ENTRAINMENT (Schicht für Schicht)
    # =========================================================================
    # Das Luftpaket startet auf elevation_m mit start_temp und steigt auf.
    # Bei jedem Höhenschritt kühlt es trockenadiabatisch ab (DALR = 0.98°C/100m)
    # und mischt sich gleichzeitig mit der kühleren Umgebungsluft (Entrainment).
    #
    # Entrainment-Formel pro Höhenschritt dh:
    #   dT_parcel = -DALR * dh - mu * (T_parcel - T_env) * dh
    #
    # Der Entrainment-Term bewirkt:
    #   - Paket wärmer als Umgebung (T_p > T_e) -> zusätzliche Abkühlung
    #     -> realistischere, schwächere Thermik als reine Parcel-Methode
    #   - Paket kühler als Umgebung (T_p < T_e) -> Erwärmung (stabilisierend)
    #
    # Über dem LCL (Kondensationsniveau) wechseln wir zum feuchtadiabatischen
    # Gradienten (SALR ≈ 0.6°C/100m), da die freiwerdende Kondensationswärme
    # die Abkühlung bremst.

    ti_profile = []
    max_thermal_height = elevation_m
    cumulative_temp_diff = 0.0
    valid_layers = 0

    parcel_temp = start_temp
    prev_height = elevation_m

    for layer in profile:
        h = layer['height']
        if h <= elevation_m:
            continue

        env_temp = layer['temp']
        dh = h - prev_height

        if dh <= 0:
            continue

        # --- Adiabatischer Aufstieg mit Entrainment ---
        if lcl_msl and h > lcl_msl:
            if prev_height < lcl_msl:
                # Übergangsschicht: Trocken bis LCL, dann feucht darüber
                dh_dry = lcl_msl - prev_height
                dh_moist = h - lcl_msl
                # Trockenadiabatischer Teil + Entrainment
                parcel_temp = (parcel_temp
                               - DALR * dh_dry
                               - MU * (parcel_temp - env_temp) * dh_dry)
                # Feuchtadiabatischer Teil + Entrainment
                parcel_temp = (parcel_temp
                               - SALR * dh_moist
                               - MU * (parcel_temp - env_temp) * dh_moist)
            else:
                # Komplett über LCL: feuchtadiabatisch + Entrainment
                parcel_temp = (parcel_temp
                               - SALR * dh
                               - MU * (parcel_temp - env_temp) * dh)
        else:
            # Unter LCL: trockenadiabatisch + Entrainment
            parcel_temp = (parcel_temp
                           - DALR * dh
                           - MU * (parcel_temp - env_temp) * dh)

        # Thermal Index (TI) = Umgebung minus Paket
        # Negativer TI = Paket ist WÄRMER als Umgebung = STEIGEN!
        ti = env_temp - parcel_temp
        ti_profile.append({
            'height': h,
            'pressure': layer.get('pressure'),
            'parcel_temp': round(parcel_temp, 2),
            'env_temp': env_temp,
            'ti': round(ti, 2)
        })

        # Prüfe ob das Paket noch steigt (0.5K Toleranz für Trägheit der Blase)
        if parcel_temp >= env_temp - 0.5:
            max_thermal_height = h
            cumulative_temp_diff += (parcel_temp - env_temp)
            valid_layers += 1
        else:
            # Inversion oder Sperrschicht erreicht -> Thermik-Obergrenze
            break

        prev_height = h

    # Begrenzung durch Boundary Layer Height (Modellinversion)
    if boundary_layer_height_agl is not None:
        blh_msl = elevation_m + boundary_layer_height_agl
        if max_thermal_height > blh_msl:
            max_thermal_height = blh_msl
        elif max_thermal_height <= elevation_m and boundary_layer_height_agl > 150 and H > 30:
            max_thermal_height = min(blh_msl, elevation_m + 2000)
            data_warnings.append(
                f"BLH-Korrektur: Grenzschichthoehe ({boundary_layer_height_agl:.0f}m AGL) "
                f"als Thermiktiefe genutzt (H={H:.0f} W/m²)"
            )

    # H-basierte Fallback-Schaetzung der Thermiktiefe
    # Greift wenn weder Parcel noch BLH eine Thermiktiefe ergeben, aber die Sonne
    # deutlich heizt. icon_seamless liefert z.B. kein boundary_layer_height.
    # Empirische Formel: z_i ~ H * 3, gedeckelt auf 800m (konservativ).
    if max_thermal_height <= elevation_m and H > 50:
        z_i_est = int(min(800, max(200, H * 3)))
        max_thermal_height = elevation_m + z_i_est
        data_warnings.append(
            f"H-Schaetzung: Thermiktiefe ~{z_i_est}m (H={H:.0f} W/m²)"
        )

    # =========================================================================
    # 6. DUAL W*-BERECHNUNG (Geometrisches-Mittel-Strategie)
    # =========================================================================
    # Zwei unabhaengige Konvektionsgeschwindigkeiten (w*):
    #
    # a) w*_parcel: Aus der mittleren Temperaturdifferenz (Parcel-Aufstieg)
    # b) w*_deardorff: Aus dem sensiblen Waermefluss (Energie-Ansatz)
    #
    # Bei BLH-Fallback (z_i aus Grenzschichthoehe): Nur Deardorff,
    # da Parcel keine Instabilitaet fand.
    # Bei beiden > 0: Geometrisches Mittel sqrt(a*b) statt min(a,b).
    # Weniger konservativ, aber physikalisch besser balanciert.

    T_kelvin = start_temp + 273.15
    z_i = max_thermal_height - elevation_m

    w_star_parcel = 0.0
    w_star_deardorff = 0.0
    avg_climb = 0.0
    mean_dT = 0.0
    limiting_factor = "keine_thermik"

    if z_i > 50:
        if valid_layers > 0:
            mean_dT = cumulative_temp_diff / valid_layers

        # a) W* aus Parcel-Methode
        if mean_dT > 0 and valid_layers > 0:
            w_star_parcel = math.sqrt((G / T_kelvin) * mean_dT * z_i)

        # b) W* nach Deardorff
        if H > 0 and z_i > 0:
            buoyancy_flux = H / (RHO * CP)
            w_star_deardorff = ((G / T_kelvin) * buoyancy_flux * z_i) ** (1.0 / 3.0)

        # c) Kombination: Geometrisches Mittel wenn beide verfuegbar
        if w_star_parcel > 0 and w_star_deardorff > 0:
            raw_w_star = math.sqrt(w_star_parcel * w_star_deardorff)
            if w_star_parcel < w_star_deardorff:
                limiting_factor = "inversion_stability"
            else:
                limiting_factor = "solar_energy"
        elif w_star_parcel > 0:
            raw_w_star = w_star_parcel
            limiting_factor = "solar_energy"
        elif w_star_deardorff > 0:
            raw_w_star = w_star_deardorff
            limiting_factor = "inversion_stability"
        else:
            raw_w_star = 0.0

        # Kalibrierungsfaktor: w* -> reales Gleitschirm-Steigen
        # Literatur: Stull 1988 ~0.5 fuer Thermikkern, Bradbury 1991 ~0.4-0.5
        # 0.45 = Mittelwert fuer Paraglider-spezifisches Kreissteigen
        avg_climb = raw_w_star * 0.45

        avg_climb = min(6.0, avg_climb)

    # =========================================================================
    # 7. BEWERTUNG (Rating 0-10)
    # =========================================================================
    rating = 0
    if avg_climb > 0: rating = 1
    if avg_climb >= 0.2: rating = 2
    if avg_climb >= 0.5: rating = 3
    if avg_climb >= 0.8: rating = 5
    if avg_climb >= 1.5: rating = 7
    if avg_climb >= 2.5: rating = 9
    if avg_climb >= 3.5: rating = 10

    # Minimale Thermikhöhe: Unter 200m ueber Start ist Thermik kaum nutzbar
    if max_thermal_height < elevation_m + 200:
        rating = min(rating, 1)
        avg_climb = 0.0

    # =========================================================================
    # 8. BODENFEUCHTE-BREMSE (Latenter Wärmefluss)
    # =========================================================================
    # Wenn der latente Wärmefluss (Verdunstung) den sensiblen (Thermik)
    # übersteigt, ist der Boden nass: Die Sonnenenergie geht primär in
    # Verdunstung statt in die Lufterwärmung -> schwächere Thermik.
    # In diesem Fall reduzieren wir das Rating um 2 Punkte.
    bowen_ratio = None
    if le_valid:
        if abs(LE) > 0:
            bowen_ratio = H / abs(LE)
        else:
            # LE = 0 bedeutet keine Verdunstung -> sehr trockener Boden
            bowen_ratio = 99.0

        # Bremse nur anwenden wenn überhaupt Thermik vorhanden ist (H > 0)
        if abs(LE) > H and H > 0:
            rating = max(0, rating - 2)
            data_warnings.append(
                f"Bodenfeuchte-Bremse: LE ({LE:.0f} W/m²) > H ({H:.0f} W/m²) "
                f"-> Rating um 2 reduziert (Bowen={bowen_ratio:.2f})"
            )

    # =========================================================================
    # 9. DIAGNOSTIK (für LLM-Kontext und Debugging)
    # =========================================================================
    diagnostics = {
        'w_star_parcel': round(w_star_parcel, 2),
        'w_star_deardorff': round(w_star_deardorff, 2),
        'limiting_factor': limiting_factor,
        'sensible_heat_flux': round(H, 1),
        'sensible_heat_flux_estimated': h_is_estimated,
        'latent_heat_flux': round(LE, 1) if le_valid else None,
        'bowen_ratio': round(bowen_ratio, 2) if bowen_ratio is not None else None,
        'mean_dT': round(mean_dT, 2),
        'thermal_depth_m': round(z_i),
        'start_temp_used': round(start_temp, 1),
        'boundary_layer_height_agl': round(boundary_layer_height_agl) if boundary_layer_height_agl is not None else None,
    }

    return {
        'max_height': round(max_thermal_height),
        'lcl': round(lcl_msl) if lcl_msl else None,
        'climb_rate': round(avg_climb, 1),
        'rating': rating,
        'ti_profile': ti_profile,
        'diagnostics': diagnostics,
        'data_warnings': data_warnings,
    }


def analyze_hour(hourly_data: Dict, pressure_data: Dict, time_index: int,
                 elevation_m: float = 850.0) -> Dict:
    """
    Extrahiert die Daten für eine spezifische Stunde und berechnet die Thermik.
    Convenience-Funktion, die alle Parameter aus den API-Rohdaten extrahiert
    und an calculate_thermal_profile() weiterleitet.
    """
    try:
        surf_temp = hourly_data.get('temperature_2m', [])[time_index]
        surf_dew = hourly_data.get('dewpoint_2m', [])

        if not surf_dew or len(surf_dew) <= time_index:
            rh_2m = hourly_data.get('relative_humidity_2m', [])
            if rh_2m and len(rh_2m) > time_index:
                surf_dew_val = calculate_dewpoint(surf_temp, rh_2m[time_index])
            else:
                surf_dew_val = surf_temp - 5  # Grobe Schätzung als Fallback
        else:
            surf_dew_val = surf_dew[time_index]

        blh = hourly_data.get('boundary_layer_height', [])
        blh_val = blh[time_index] if blh and len(blh) > time_index else None

        sun = hourly_data.get('sunshine_duration', [])
        sun_val = sun[time_index] if sun and len(sun) > time_index else 3600.0

        # Neue Flux-Parameter (können None sein -> Fallback im Calculator)
        shf = hourly_data.get('surface_sensible_heat_flux', [])
        shf_val = shf[time_index] if shf and len(shf) > time_index else None

        lhf = hourly_data.get('surface_latent_heat_flux', [])
        lhf_val = lhf[time_index] if lhf and len(lhf) > time_index else None

        swr = hourly_data.get('shortwave_radiation', [])
        swr_val = swr[time_index] if swr and len(swr) > time_index else None

        # Höhendaten extrahieren
        p_levels = []
        for level in [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600]:
            h_key = f"geopotential_height_{level}hPa"
            t_key = f"temperature_{level}hPa"

            if h_key in pressure_data and t_key in pressure_data:
                h_arr = pressure_data[h_key]
                t_arr = pressure_data[t_key]
                if len(h_arr) > time_index and len(t_arr) > time_index:
                    p_levels.append({
                        'pressure': level,
                        'height': h_arr[time_index],
                        'temp': t_arr[time_index]
                    })

        return calculate_thermal_profile(
            surface_temp=surf_temp,
            surface_dewpoint=surf_dew_val,
            elevation_m=elevation_m,
            pressure_levels_data=p_levels,
            boundary_layer_height_agl=blh_val,
            sunshine_duration_s=sun_val,
            surface_sensible_heat_flux=shf_val,
            surface_latent_heat_flux=lhf_val,
            shortwave_radiation=swr_val,
        )

    except Exception as e:
        logger.error(f"Fehler bei Thermik-Berechnung: {e}")
        return {'error': str(e)}
