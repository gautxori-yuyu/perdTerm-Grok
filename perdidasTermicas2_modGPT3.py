# -*- coding: utf-8 -*-
"""
SIMULADOR HIGROTERMICO SIMPLIFICADO DE VIVIENDA
Compatible con Python 3.8. Interfaz Tkinter; gráficos Matplotlib opcionales.
CoolProp HumidAirProp se utiliza si está instalado; existe alternativa psicrométrica.

Modelo:
- Un nodo térmico y uno de humedad por estancia.
- Al simular la vivienda completa, cada estancia conserva su propio nodo térmico y de humedad.
 Las estancias intercambian energía y humedad a través de las conexiones configuradas..
- Paso temporal configurable (por defecto 1 hora).
- Transmisión, ventilación, ganancias internas/solares, calefacción,
  deshumidificación y riesgo de condensación superficial.

IMPORTANTE:
Los valores geométricos iniciales son ejemplos heredados/adaptados, no una
caracterización validada de una vivienda real. Deben revisarse antes de usar
los resultados para tomar decisiones constructivas o energéticas.
"""

import os
import json
import math
import copy
import calendar
import hashlib
from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_TITLE = "Simulador higrotérmico simplificado"
CONFIG_FILE = "vivienda_config.json"
P_ATM = 101325.0
RHO_AIR = 1.20
CP_AIR = 1006.0
H_FG = 2450000.0
SECONDS_PER_HOUR = 3600.0
# W por cada m³/h de ventilación y cada K. Igual a rho·cp/3600.
VENT_HEAT_W_PER_M3H_K = RHO_AIR * CP_AIR / SECONDS_PER_HOUR

DEFAULT_WEATHER = [
    # Hora, temperatura exterior (°C), humedad relativa exterior (%), radiación (W/m²), velocidad viento, dirección viento
    [0, 8.2, 88, 0, 2.5, 270], [1, 7.3, 93, 0, 2.5, 270], [2, 6.6, 99, 0, 2.5, 270],
    [3, 6.2, 100, 0, 2.5, 270], [4, 6.0, 100, 0, 2.5, 270], [5, 6.2, 100, 0, 2.5, 270],
    [6, 6.6, 100, 0, 2.5, 270], [7, 7.3, 100, 0, 2.5, 270], [8, 8.2, 100, 10, 2.5, 270],
    [9, 9.3, 100, 40, 2.5, 270], [10, 10.5, 98, 100, 2.5, 270], [11, 11.7, 95, 180, 2.5, 270],
    [12, 12.7, 93, 250, 2.5, 270], [13, 13.7, 74, 350, 2.5, 270], [14, 14.4, 67, 450, 2.5, 270],
    [15, 14.8, 62, 500, 2.5, 270], [16, 15.0, 57, 450, 2.5, 270], [17, 14.8, 74, 250, 2.5, 270],
    [18, 14.4, 68, 100, 2.5, 270], [19, 13.7, 74, 20, 2.5, 270], [20, 12.8, 70, 0, 2.5, 270],
    [21, 11.7, 68, 0, 2.5, 270], [22, 10.5, 69, 0, 2.5, 270], [23, 9.3, 72, 0, 2.5, 270]
]
DEFAULT_CONFIG = {
    "pressure_pa": 101325.0,
    "target_temperature": 20.0,
    "target_rh": 60.0,
    "initial_temperature": 18.0,
    "initial_rh": 85.0,
    "initial_glass_temperature": 12.0,
    "people": 1,
    "occupancy_start": 8,
    "occupancy_end": 23,
    "moisture_per_person_g_h": 55.0,
    "sensible_gain_per_person_w": 70.0,
    "internal_gain_w": 0.0,
    "thermal_mass_j_m2k": 100000.0,
    "air_changes_h": 0.35,
    "ventilation_max_ach": 2.0,
    "ventilation_control": True,
    "dehumidifier_l_day": 12.0,
    "dehumidifier_power_kw": 0.22,
    "dehumidifier_heat_factor": 1.0,
    "heater_kw": 3.8,
    "heating_type": "butane",  # butane / electric / heat_pump
    "heat_pump_cop": 3.0,
    "combustion_moisture_g_kwh": 75.0,
    "solar_enabled": True,
    "solar_factor": 0.55,
    "surface_factor": 0.75,
    "weather": DEFAULT_WEATHER,
    "connections": [
        {
            "room_a": "SALON",
            "room_b": "COCINA",
            "type": "open",
            "ventilation_transfer_factor": 0.5
        },
        {
            "room_a": "COCINA",
            "room_b": "PASILLO",
            "type": "ajar",
            "ventilation_transfer_factor": 0.3
        }
    ],
    "rooms": [
        {
            "name": "SALON", "height": 2.6, "floor_area": 40.0,
            "window_area": 7.5, "window_u": 2.4,
            "wall_area": 35.0, "wall_u": 1.1,
            "roof_area": 0.0, "roof_u": 0.85,
            "floor_exposed_area": 0.0, "floor_u": 1.6,
            "air_changes_h": 0.35, "thermal_mass_j_m2k": 100000.0,
            "people": 1,
            "internal_gain_w": 0.0,
            "dehumidifier_l_day": 12.0,
            "dehumidifier_power_kw": 0.22,
            "heater_kw": 3.8,
            "heating_type": "butane",
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60
        },
        {
            "name": "COCINA", "height": 2.6, "floor_area": 20.0,
            "window_area": 5.0, "window_u": 2.4,
            "wall_area": 22.0, "wall_u": 1.1,
            "roof_area": 0.0, "roof_u": 0.85,
            "floor_exposed_area": 0.0, "floor_u": 1.6,
            "air_changes_h": 0.50, "thermal_mass_j_m2k": 100000.0,
            "people": 0,
            "internal_gain_w": 0.0,
            "dehumidifier_l_day": 12.0,
            "dehumidifier_power_kw": 0.22,
            "heater_kw": 3.8,
            "heating_type": "butane",
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60
        },
        {
            "name": "PASILLO", "height": 2.5, "floor_area": 15.0,
            "window_area": 0.0, "window_u": 2.4,
            "wall_area": 18.0, "wall_u": 1.1,
            "roof_area": 0.0, "roof_u": 0.85,
            "floor_exposed_area": 0.0, "floor_u": 1.6,
            "air_changes_h": 0.35, "thermal_mass_j_m2k": 100000.0,
            "people": 0,
            "internal_gain_w": 0.0,
            "dehumidifier_l_day": 12.0,
            "dehumidifier_power_kw": 0.22,
            "heater_kw": 3.8,
            "heating_type": "butane",
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60
        }
    ],
    "latitude_deg": 42.5,
    "longitude_deg": -8.0,
    "altitude_m": 0.0,

    "solar_date": date.today().isoformat(),
    "solar_utc_offset_hours": None,

    "solar_glazing_area_factor": 0.90,
    "solar_ground_reflectance": 0.20,
    "solar_shading_factor": 1.0
    "solar_hour_reference": "interval_end",
}

# CONEXIONES ENTRE ESTANCIAS
DOOR_DEFAULTS = {
    "open": {
        "width_m": 0.82,
        "height_m": 2.03,
        "opening_factor": 1.0,
        "discharge_coefficient": 0.62
    },
    "ajar": {
        "width_m": 0.82,
        "height_m": 2.03,
        "opening_factor": 0.12,
        "discharge_coefficient": 0.62
    },
    "closed_gap": {
        "width_m": 0.82,
        "height_m": 2.03,
        "opening_factor": 0.015,
        "discharge_coefficient": 0.62
    },
    "custom": {
        "width_m": 0.82,
        "height_m": 2.03,
        "opening_factor": 1.0,
        "discharge_coefficient": 0.62
    }
}

SOLAR_ORIENTATIONS = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SO": 225.0,
    "O": 270.0,
    "NO": 315.0,

    # Alias por compatibilidad.
    "NW": 315.0,
    "W": 270.0,
    "SW": 225.0
}

# ---------------------------------------------------------------------------
# PSICROMETRIA
# ---------------------------------------------------------------------------

class Psychrometrics:
    """Funciones psicrométricas. SI: Pa, kg/kg de aire seco, °C y kJ/kg."""

    def __init__(self):
        self.coolprop = False
        try:
            from CoolProp.HumidAirProp import HAPropsSI
            self._ha = HAPropsSI
            self.coolprop = True
        except Exception:
            self._ha = None

    @staticmethod
    def saturation_pressure_pa(t_c):
        # Buck simplificada, válida para el rango habitual de edificios.
        return 611.21 * math.exp((18.678 - t_c / 234.5) *
                                 (t_c / (257.14 + t_c)))

    def humidity_ratio(self, t_c, rh, pressure=P_ATM):
        rh = max(0.0, min(100.0, float(rh))) / 100.0
        if self.coolprop:
            try:
                return float(self._ha("W", "T", t_c + 273.15,
                                      "P", pressure, "R", rh))
            except Exception:
                pass
        pws = self.saturation_pressure_pa(t_c)
        pv = min(rh * pws, pressure * 0.99)
        return 0.621945 * pv / (pressure - pv)

    def relative_humidity(self, t_c, w, pressure=P_ATM):
        w = max(0.0, float(w))
        if self.coolprop:
            try:
                return max(0.0, min(100.0, 100.0 * float(
                    self._ha("R", "T", t_c + 273.15, "P", pressure, "W", w))))
            except Exception:
                pass
        pv = pressure * w / (0.621945 + w)
        return max(0.0, min(100.0, 100.0 * pv /
                            self.saturation_pressure_pa(t_c)))

    def dew_point(self, t_c, w, pressure=P_ATM):
        if w <= 0:
            return -80.0
        if self.coolprop:
            try:
                rh = self.relative_humidity(t_c, w, pressure) / 100.0
                return float(self._ha("D", "T", t_c + 273.15,
                                      "P", pressure, "R", rh)) - 273.15
            except Exception:
                pass
        pv = pressure * w / (0.621945 + w)
        # Inversión numérica robusta de la presión de saturación.
        lo, hi = -80.0, 80.0
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if self.saturation_pressure_pa(mid) < pv:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0
        
    def enthalpy_kj_kg(self, t_c, w):
        return 1.006 * t_c + w * (2501.0 + 1.86 * t_c)


# ---------------------------------------------------------------------------
# MODELO FISICO MULTIESTANCIA
# ---------------------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def room_geometry(room):
    """Volumen de una estancia en m³."""
    return max(0.1, float(room["height"]) * float(room["floor_area"]))


def room_envelope_ua(room):
    """
    Calcula la conductancia térmica de la envolvente,
    sin incluir la ventilación, en W/K.
    """

    return (
        room_window_area_total(room)
        * float(room.get("window_u", 0.0)) +

        float(room.get("wall_area", 0.0))
        * float(room.get("wall_u", 0.0)) +

        float(room.get("roof_area", 0.0))
        * float(room.get("roof_u", 0.0)) +

        float(room.get("floor_exposed_area", 0.0))
        * float(room.get("floor_u", 0.0))
    )

def room_ua(room, ach_override=None, temperature=None,
            humidity_ratio=0.0, pressure=P_ATM):
    """
    Calcula la conductancia térmica total de una estancia.

    Si se proporcionan temperatura, humedad específica y presión,
    calcula el UA de ventilación a partir de la masa de aire seco.

    Sin esos parámetros utiliza la aproximación convencional
    basada en RHO_AIR y CP_AIR.
    """

    ach = (
        float(room.get("air_changes_h", 0.0))
        if ach_override is None
        else max(0.0, float(ach_override))
    )

    volume = room_geometry(room)

    if temperature is None:

        ua_vent = (
            VENT_HEAT_W_PER_M3H_K
            * ach
            * volume
        )

    else:

        dry_mass = dry_air_mass(
            volume,
            float(temperature),
            max(0.0, float(humidity_ratio)),
            pressure
        )

        cp_moist = (
            CP_AIR
            + 1860.0 * max(0.0, float(humidity_ratio))
        )

        mass_flow_kg_s = (
            dry_mass * ach / 3600.0
        )

        ua_vent = (
            mass_flow_kg_s * cp_moist
        )

    return max(
        0.0,
        room_envelope_ua(room) + ua_vent
    )

def room_capacity(room, thermal_mass_override=None):
    """Capacidad térmica efectiva de la estancia, J/K."""
    volume = room_geometry(room)

    mass_area = (
        float(room.get("thermal_mass_j_m2k", 100000.0))
        if thermal_mass_override is None
        else float(thermal_mass_override)
    )

    return (
        RHO_AIR * CP_AIR * volume +
        max(0.0, mass_area) * float(room["floor_area"])
    )
    
def exact_thermal_step(t0, tout, ua, capacity, gains_w, dt_s):
    """
    Solución exacta de:
        C*dT/dt = UA*(Text-T) + ganancias

    Se supone que UA, Text y las ganancias permanecen constantes
    durante el subpaso.
    """
    if capacity <= 0:
        return t0

    if ua <= 1e-12:
        return t0 + gains_w * dt_s / capacity

    decay = math.exp(-ua * dt_s / capacity)

    return (
        tout +
        (t0 - tout) * decay +
        (gains_w / ua) * (1.0 - decay)
    )

def room_window_area_total(room):
    """
    Devuelve la superficie total de los huecos acristalados.

    Si existen grupos de ventanas, suma sus superficies.
    Para configuraciones antiguas utiliza window_area.
    """

    groups = room.get("window_groups")

    if isinstance(groups, list) and groups:
        return sum(
            max(0.0, float(group.get("area_m2", 0.0)))
            for group in groups
        )

    return max(
        0.0,
        float(room.get("window_area", 0.0))
    )
    

def last_sunday_of_month(year, month):
    """
    Obtiene la fecha del último domingo de un mes.
    """

    last_day = calendar.monthrange(year, month)[1]

    last_date = date(
        year,
        month,
        last_day
    )

    return (
        last_date
        - timedelta(days=(last_date.weekday() + 1) % 7)
    )


def solar_utc_offset(day, config):
    """
    Obtiene el desfase horario respecto a UTC.

    Por defecto utiliza el horario de España peninsular:
    UTC+1 en invierno y UTC+2 en verano.

    Puede sobrescribirse mediante solar_utc_offset_hours.
    """

    configured = config.get("solar_utc_offset_hours")

    if configured is not None:
        return float(configured)

    dst_start = last_sunday_of_month(
        day.year, 3
    )

    dst_end = last_sunday_of_month(
        day.year, 10
    )

    if dst_start <= day < dst_end:
        return 2.0

    return 1.0


def solar_position(hour, config, day_offset=0):
    """
    Calcula la elevación y azimut solar.

    Devuelve:
        elevation_deg: elevación solar sobre el horizonte.
        azimuth_deg: azimut desde el norte, sentido horario.
        cos_zenith: coseno del ángulo cenital.

    Utiliza fecha, latitud, longitud y hora local.
    """

    solar_date = str(
        config.get(
            "solar_date",
            date.today().isoformat()
        )
    )

    try:
        base_date = date.fromisoformat(
            solar_date[:10]
        )
    except ValueError:
        raise ValueError(
            "solar_date debe tener formato YYYY-MM-DD."
        )
    '''
    local_hour = float(hour) + 0.5

    current_date = (
        base_date
        + timedelta(days=int(day_offset))
    )
    '''
    # La radiación horaria de Open-Meteo corresponde a la hora anterior.
    # Por ejemplo, el dato etiquetado 13:00 representa 12:00-13:00.
    reference = config.get(
        "solar_hour_reference",
        "interval_end"
    )

    if reference == "interval_end":
        local_hour = float(hour) - 0.5

    elif reference == "interval_start":
        local_hour = float(hour) + 0.5

    elif reference == "instant":
        local_hour = float(hour)

    else:
        raise ValueError(
            "solar_hour_reference debe ser interval_end, "
            "interval_start o instant."
        )

    adjusted_day_offset = int(day_offset)

    while local_hour < 0.0:
        local_hour += 24.0
        adjusted_day_offset -= 1

    while local_hour >= 24.0:
        local_hour -= 24.0
        adjusted_day_offset += 1

    current_date = (
        base_date
        + timedelta(days=adjusted_day_offset)
    )

    latitude = float(
        config.get("latitude_deg", 42.5)
    )

    longitude = float(
        config.get("longitude_deg", -8.0)
    )

    if not -90.0 <= latitude <= 90.0:
        raise ValueError(
            "La latitud debe estar entre -90 y 90 grados."
        )

    if not -180.0 <= longitude <= 180.0:
        raise ValueError(
            "La longitud debe estar entre -180 y 180 grados."
        )

    utc_offset = solar_utc_offset(
        current_date,
        config
    )

    day_of_year = current_date.timetuple().tm_yday

    days_in_year = (
        366 if calendar.isleap(current_date.year)
        else 365
    )

    gamma = (
        2.0 * math.pi / days_in_year
        * (
            day_of_year - 1
            + (local_hour - 12.0) / 24.0
        )
    )

    # Ecuación del tiempo, en minutos.
    equation_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )

    # Declinación solar, en radianes.
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
        - 0.002697 * math.cos(3.0 * gamma)
        + 0.00148 * math.sin(3.0 * gamma)
    )

    # Tiempo solar verdadero.
    time_offset = (
        equation_time
        + 4.0 * (
            longitude - 15.0 * utc_offset
        )
    )

    true_solar_minutes = (
        local_hour * 60.0 + time_offset
    )

    hour_angle = math.radians(
        true_solar_minutes / 4.0 - 180.0
    )

    lat_rad = math.radians(latitude)

    cos_zenith = (
        math.sin(lat_rad) * math.sin(declination)
        + math.cos(lat_rad)
        * math.cos(declination)
        * math.cos(hour_angle)
    )

    cos_zenith = clamp(
        cos_zenith,
        -1.0,
        1.0
    )

    elevation = math.degrees(
        math.asin(cos_zenith)
    )

    azimuth = (
        math.degrees(
            math.atan2(
                math.sin(hour_angle),
                (
                    math.cos(hour_angle)
                    * math.sin(lat_rad)
                    - math.tan(declination)
                    * math.cos(lat_rad)
                )
            )
        )
        + 180.0
    ) % 360.0

    return (
        elevation,
        azimuth,
        cos_zenith
    )


def solar_irradiance_on_vertical_facade(
        ghi, hour, orientation, config, day_offset=0):
    """
    Estima la irradiancia solar sobre una fachada vertical.

    Entrada:
        ghi: irradiancia global horizontal, W/m².
        orientation: N, NE, E, SE, S, SO, O, NO o azimut numérico.

    Se utiliza una descomposición aproximada de Erbs para estimar
    radiación difusa y directa a partir de GHI.

    La componente difusa se distribuye mediante el modelo isotrópico
    de cielo. La reflexión del suelo utiliza solar_ground_reflectance.
    """

    ghi = max(0.0, float(ghi))

    if ghi <= 0.0:
        return 0.0

    elevation, sun_azimuth, cos_zenith = solar_position(
        hour,
        config,
        day_offset
    )

    if elevation <= 0.0 or cos_zenith <= 0.0:
        return 0.0

    # Orientaciones no especificadas: promedio de las ocho fachadas.
    if isinstance(orientation, str):

        orientation = orientation.strip().upper()

        if orientation in ("AVERAGE", "MEDIA", "DESCONOCIDA"):

            values = [
                solar_irradiance_on_vertical_facade(
                    ghi,
                    hour,
                    key,
                    config,
                    day_offset
                )
                for key in (
                    "N", "NE", "E", "SE",
                    "S", "SO", "O", "NO"
                )
            ]

            return sum(values) / len(values)

        if orientation not in SOLAR_ORIENTATIONS:
            raise ValueError(
                "Orientación solar no válida: %s"
                % orientation
            )

        facade_azimuth = SOLAR_ORIENTATIONS[
            orientation
        ]

    else:
        facade_azimuth = float(orientation) % 360.0

    # Irradiancia extraterrestre normal.
    day = date.fromisoformat(
        str(config.get(
            "solar_date",
            date.today().isoformat()
        ))[:10]
    ) + timedelta(days=int(day_offset))

    day_number = day.timetuple().tm_yday

    i0_normal = (
        1367.0
        * (
            1.0
            + 0.033
            * math.cos(
                2.0 * math.pi * day_number / 365.0
            )
        )
    )

    i0_horizontal = (
        i0_normal * cos_zenith
    )

    # Índice de claridad atmosférica.
    kt = clamp(
        ghi / max(1.0, i0_horizontal),
        0.0,
        1.2
    )

    # Fracción difusa de Erbs.
    if kt <= 0.22:

        diffuse_fraction = (
            1.0 - 0.09 * kt
        )

    elif kt <= 0.80:

        diffuse_fraction = (
            0.9511
            - 0.1604 * kt
            + 4.388 * kt ** 2
            - 16.638 * kt ** 3
            + 12.336 * kt ** 4
        )

    else:

        diffuse_fraction = 0.165

    diffuse_fraction = clamp(
        diffuse_fraction,
        0.0,
        1.0
    )

    dhi = (
        ghi * diffuse_fraction
    )

    # Cerca del horizonte la descomposición directa resulta inestable.
    if cos_zenith < 0.065:

        dni = 0.0
        dhi = ghi

    else:

        dni = (
            max(0.0, ghi - dhi)
            / cos_zenith
        )

        dni = min(
            dni,
            i0_normal
        )

    # --------------------------------------------------------------
    # COMPONENTE DIRECTA SOBRE LA FACHADA VERTICAL
    # --------------------------------------------------------------

    cos_elevation = math.sqrt(
        max(0.0, 1.0 - cos_zenith ** 2)
    )

    incidence_cos = (
        cos_elevation
        * math.cos(
            math.radians(
                sun_azimuth - facade_azimuth
            )
        )
    )

    direct_plane = (
        dni * max(0.0, incidence_cos)
    )

    # --------------------------------------------------------------
    # COMPONENTE DIFUSA DEL CIELO
    # --------------------------------------------------------------

    diffuse_plane = (
        dhi * 0.5
    )

    # --------------------------------------------------------------
    # COMPONENTE REFLEJADA POR EL SUELO
    # --------------------------------------------------------------

    albedo = clamp(
        float(
            config.get(
                "solar_ground_reflectance",
                0.20
            )
        ),
        0.0,
        1.0
    )

    ground_reflected = (
        ghi * albedo * 0.5
    )

    return max(
        0.0,
        direct_plane
        + diffuse_plane
        + ground_reflected
    )


def room_solar_gain_w(room, ghi, config,
                      hour, day_offset=0):
    """
    Calcula las ganancias solares transmitidas a una estancia.

    Cada grupo de ventanas tiene:
        orientation
        area_m2
        g_factor
        shade_factor

    Las configuraciones antiguas utilizan window_area y una
    orientación media de las ocho fachadas.
    """

    if not config.get("solar_enabled", True):
        return 0.0

    groups = room.get("window_groups")

    if not isinstance(groups, list) or not groups:

        groups = [
            {
                "orientation": "AVERAGE",
                "area_m2": room.get("window_area", 0.0),
                "g_factor": config.get("solar_factor", 0.55),
                "shade_factor": config.get(
                    "solar_shading_factor",
                    1.0
                )
            }
        ]

    glazing_factor = clamp(
        float(
            config.get(
                "solar_glazing_area_factor",
                0.90
            )
        ),
        0.0,
        1.0
    )

    total_solar_w = 0.0

    for group in groups:

        area = max(
            0.0,
            float(group.get("area_m2", 0.0))
        )

        g_factor = clamp(
            float(
                group.get(
                    "g_factor",
                    group.get(
                        "solar_factor",
                        config.get("solar_factor", 0.55)
                    )
                )
            ),
            0.0,
            1.0
        )

        shade_factor = clamp(
            float(
                group.get(
                    "shade_factor",
                    config.get(
                        "solar_shading_factor",
                        1.0
                    )
                )
            ),
            0.0,
            1.0
        )

        orientation = group.get(
            "orientation",
            "AVERAGE"
        )

        facade_irradiance = (
            solar_irradiance_on_vertical_facade(
                ghi,
                hour,
                orientation,
                config,
                day_offset
            )
        )

        effective_area = (
            area * glazing_factor
        )

        total_solar_w += (
            effective_area
            * g_factor
            * shade_factor
            * facade_irradiance
        )

    return max(0.0, total_solar_w)
    
# ---------------------------------------------------------------------------
# PSICROMETRIA AUXILIAR
# ---------------------------------------------------------------------------

def saturation_humidity_ratio(psych, temperature, pressure):
    """Humedad específica de saturación, kg/kg aire seco."""
    return psych.humidity_ratio(temperature, 100.0, pressure)


def dry_air_mass(volume, temperature, humidity_ratio, pressure):
    """
    Masa aproximada de aire seco de una estancia.

    Se obtiene a partir de la ecuación de gas ideal para el aire seco.
    La aproximación es suficiente para el balance de humedad del modelo.
    """
    t_k = temperature + 273.15

    pv = pressure * humidity_ratio / (0.621945 + humidity_ratio)
    p_dry = max(100.0, pressure - pv)

    r_dry = 287.055

    return max(0.01, p_dry * volume / (r_dry * t_k))


def air_density(temperature, humidity_ratio, pressure):
    """Densidad aproximada del aire húmedo, kg/m³."""
    t_k = temperature + 273.15

    pv = pressure * humidity_ratio / (0.621945 + humidity_ratio)
    p_dry = max(100.0, pressure - pv)

    r_dry = 287.055
    r_vapour = 461.495

    return (
        p_dry / (r_dry * t_k) +
        pv / (r_vapour * t_k)
    )

def wet_bulb_temperature_c(psych, temperature,
                          humidity_ratio, pressure):
    """
    Calcula la temperatura de bulbo húmedo termodinámica.

    Utiliza CoolProp cuando está disponible.
    En su ausencia, resuelve el balance de entalpía de saturación
    mediante bisección.

    No constituye un cálculo PMV ni un índice normalizado de confort.
    """

    t = float(temperature)
    w = max(0.0, float(humidity_ratio))

    w_sat = psych.humidity_ratio(
        t,
        100.0,
        pressure
    )

    if w >= w_sat:
        return t

    # CoolProp: B representa la temperatura de bulbo húmedo.
    if getattr(psych, "coolprop", False):

        try:
            return float(
                psych._ha(
                    "B",
                    "T", t + 273.15,
                    "P", pressure,
                    "W", w
                )
            ) - 273.15

        except Exception:
            pass

    # --------------------------------------------------------------
    # Alternativa psicrométrica por balance de entalpía.
    # Unidades de entalpía: kJ/kg de aire seco.
    # --------------------------------------------------------------

    h_air = (
        1.006 * t
        + w * (2501.0 + 1.86 * t)
    )

    def residual(t_wb):

        w_sat_wb = psych.humidity_ratio(
            t_wb,
            100.0,
            pressure
        )

        h_sat = (
            1.006 * t_wb
            + w_sat_wb
            * (2501.0 + 1.86 * t_wb)
        )

        h_liquid = (
            4.186 * t_wb
        )

        return (
            h_sat
            - h_air
            - (w_sat_wb - w) * h_liquid
        )

    low = -80.0
    high = t

    for _ in range(70):

        middle = (
            low + high
        ) / 2.0

        if residual(middle) > 0.0:
            high = middle
        else:
            low = middle

    return (
        low + high
    ) / 2.0
    
# ---------------------------------------------------------------------------
# CONEXIONES ENTRE ESTANCIAS
# ---------------------------------------------------------------------------


def door_buoyancy_exchange(room_a, room_b, state_a, state_b,
                           connection, pressure):
    """
    Estima el intercambio bidireccional por flotabilidad.

    Fórmula simplificada para una abertura vertical:

        Q = Cd * A / 3 * sqrt(g * H * abs(rho_a-rho_b)/rho_mean)

    Q se expresa en m³/s por sentido.

    No representa un caudal neto: modela aire que sale por una zona
    de la abertura y entra por otra debido a la diferencia de densidad.
    """
    kind = connection.get("type", "open")

    defaults = DOOR_DEFAULTS.get(kind, DOOR_DEFAULTS["open"])

    width = max(
        0.0,
        float(connection.get("width_m", defaults["width_m"]))
    )

    height = max(
        0.0,
        float(connection.get("height_m", defaults["height_m"]))
    )

    opening_factor = clamp(
        float(connection.get(
            "opening_factor", defaults["opening_factor"]
        )),
        0.0, 1.0
    )

    cd = max(
        0.0,
        float(connection.get(
            "discharge_coefficient",
            defaults["discharge_coefficient"]
        ))
    )

    area = width * height * opening_factor

    if area <= 0 or height <= 0:
        return 0.0

    rho_a = air_density(
        state_a["temperature"], state_a["w"], pressure
    )

    rho_b = air_density(
        state_b["temperature"], state_b["w"], pressure
    )

    rho_mean = max(0.1, (rho_a + rho_b) / 2.0)

    delta_rho = abs(rho_a - rho_b)

    if delta_rho < 1e-9:
        return 0.0

    g = 9.80665

    q_m3_s = (
        cd * area / 3.0 *
        math.sqrt(g * height * delta_rho / rho_mean)
    )

    return max(0.0, q_m3_s * 3600.0)


def connection_ventilation_exchange(connection, q_window):
    """
    Intercambio adicional inducido por la ventilación de una estancia.

    El factor representa la fracción del caudal de ventilación que
    contribuye a la mezcla entre las estancias comunicadas.

    No se interpreta como un flujo neto a través de la puerta.
    """
    factor = clamp(
        float(connection.get("ventilation_transfer_factor", 0.0)),
        0.0, 1.0
    )

    return max(0.0, q_window * factor)

def connection_exchange_m3_h(connection, state_a, state_b,
                             room_a, room_b, pressure):
    """
    Calcula el intercambio bidireccional entre dos estancias.

    El intercambio se determina por flotabilidad o mediante
    un caudal personalizado.

    La ventilación exterior se contabiliza separadamente
    en simulate_room_substep.
    """

    if connection.get("type", "open") == "custom":

        custom = connection.get(
            "airflow_m3_h",
            connection.get("flow_m3_h")
        )

        if custom is None:
            return 0.0

        return max(0.0, float(custom))

    return door_buoyancy_exchange(
        room_a,
        room_b,
        state_a,
        state_b,
        connection,
        pressure
    )
            
# ---------------------------------------------------------------------------
# VENTILACION EXTERIOR
# ---------------------------------------------------------------------------

def window_airflow(room, weather):
    """
    Estima el caudal de ventilación por ventanas abiertas.

    Si existe un caudal personalizado, tiene prioridad.

    En caso contrario:
        Q = Cd * A * v * wind_factor

    Es una aproximación simplificada. No resuelve presiones de fachada,
    ventilación cruzada ni diferencias de presión por altura.
    """
    if not room.get("windows_open", False):
        return 0.0

    custom_flow = room.get("window_airflow_m3_h")

    if custom_flow is not None:
        return max(0.0, float(custom_flow))

    area = max(
        0.0,
        float(room.get("window_opening_area_m2", 0.0))
    )

    wind_speed = max(
        0.0,
        float(weather.get("wind_speed_m_s", 0.0))
    )

    wind_factor = max(
        0.0,
        float(room.get("wind_factor", 0.60))
    )

    discharge_coefficient = max(
        0.0,
        float(room.get("window_discharge_coefficient", 0.60))
    )

    # Caudal estimado en m³/s.
    q_m3_s = (
        discharge_coefficient *
        area *
        wind_speed *
        wind_factor
    )

    return q_m3_s * 3600.0


def ventilation_control_ach(w_inside, w_outside, w_target,
                            ach_base, ach_max, enabled):
    """
    Calcula ACH adicional de ventilación controlada.

    Solo ventila cuando el aire exterior tiene menor humedad específica
    y el aire interior supera la consigna.

    El control se limita al ACH máximo configurado.
    """
    if not enabled:
        return 0.0

    if w_inside <= w_target or w_outside >= w_inside:
        return 0.0

    if ach_max <= ach_base:
        return 0.0

    return max(0.0, ach_max - ach_base)


# ---------------------------------------------------------------------------
# EQUIPOS
# ---------------------------------------------------------------------------
def resolve_room_param(room, config, key, default=None):
    """Valor propio de la estancia o, si no existe, el global."""
    value = room.get(key)
    if value is not None and value != "":
        return value
    return config.get(key, default)


def dehumidifier_capacity_kg_h(dehumidifier_l_day, t_c, rh):
    """Capacidad horaria del deshumidificador de la estancia."""
    nominal = max(0.0, float(dehumidifier_l_day)) / 24.0
    temp_factor = clamp((t_c + 5.0) / 25.0, 0.20, 1.0)
    rh_factor = clamp((rh - 35.0) / 45.0, 0.0, 1.0)
    return nominal * temp_factor * rh_factor


def heater_efficiency(heating_type, cop=3.0):
    if heating_type == "heat_pump":
        return max(1.0, float(cop))
    if heating_type == "electric":
        return 1.0
    return 0.90


def heater_energy_kwh(thermal_kwh, heating_type, cop=3.0):
    if heating_type == "heat_pump":
        return thermal_kwh / max(1.0, float(cop))
    if heating_type == "electric":
        return thermal_kwh
    return thermal_kwh / max(0.1, heater_efficiency(heating_type, cop))


def heater_butane_kg(thermal_kwh, heating_type):
    if heating_type != "butane":
        return 0.0
    fuel_kwh = heater_energy_kwh(thermal_kwh, heating_type)
    return fuel_kwh / 12.8

# ---------------------------------------------------------------------------
# ESTADO DE LAS ESTANCIAS
# ---------------------------------------------------------------------------

def create_room_state(room, config, psych):
    """Inicializa el estado térmico e higrométrico de una estancia."""
    temperature = float(config["initial_temperature"])

    w = psych.humidity_ratio(
        temperature,
        config["initial_rh"],
        config["pressure_pa"]
    )

    volume = room_geometry(room)

    return {
        "temperature": temperature,
        "w": w,
        "volume": volume,
        "capacity": room_capacity(room),
        "ua_envelope": room_envelope_ua(room),
        "dry_air_kg": dry_air_mass(
            volume, temperature, w, config["pressure_pa"]
        ),
        "condensate_kg": 0.0,
        "condensate_hour_kg": 0.0,
        "dehumidified_kg": 0.0,
        "heater_kwh": 0.0,
        "heater_kwh_th": 0.0,
        "heater_butane_kg": 0.0,
        "dehumidifier_kwh": 0.0,
        "ventilation_m3": 0.0,
        "ventilation_minutes": 0.0,
        "dehumidifier_minutes": 0.0,
        "heater_minutes": 0.0,
        "condensation": False
    }


def room_occupancy(room, config, hour):
    """Número de personas presentes en la estancia.

    Si la hora de inicio es mayor que la de fin, el horario cruza
    la medianoche (por ejemplo, de 22 h a 7 h).
    """
    start = int(config.get("occupancy_start", 8))
    end = int(config.get("occupancy_end", 23))
    hour = int(hour) % 24

    if start == end:
        present = False
    elif start < end:
        present = start <= hour < end
    else:
        present = hour >= start or hour < end

    if not present:
        return 0

    return max(0, int(room.get("people", 0)))

# ---------------------------------------------------------------------------
# BALANCES DE MASA Y ENERGIA
# ---------------------------------------------------------------------------

def exchange_air_between_rooms(states, connections, rooms,
                               pressure, dt_s):
    """
    Calcula los intercambios bidireccionales de aire entre estancias.

    Cada estancia es un volumen de control homogéneo.
      - Cada estancia tiene una temperatura y humedad homogéneas.
      - El intercambio es bidireccional: igual masa de aire seco
        entra y sale de cada estancia conectada.
      - La transferencia de humedad se calcula mediante la diferencia
        de humedad específica.
      - La transferencia energética se calcula mediante la diferencia
        de entalpía del aire húmedo.

    Se conservan:
      - El balance de masa de aire seco.
      - El balance de humedad específica.
      - El transporte de energía sensible.

    Todas las transferencias se calculan utilizando los estados
    iniciales del subpaso y se acumulan antes de actualizar las
    estancias. De este modo, el resultado no depende del orden
    en que estén definidas las conexiones.

    Se limita el intercambio acumulado de cada estancia al 45 %
    de su masa de aire seco durante un subpaso, para evitar
    inestabilidades numéricas.

    La energía intercambiada se incorpora a la capacidad térmica
    efectiva de cada estancia, que representa conjuntamente
    el aire y la masa térmica equivalente del recinto.
    """

    dt_s = max(0.0, float(dt_s))

    if (
        dt_s <= 0.0
        or not states
        or not connections
    ):
        return

    # --------------------------------------------------------------
    # 1. ESTADOS INICIALES
    # --------------------------------------------------------------

    # Instantánea de las propiedades de cada estancia.
    # Evita que el orden de las conexiones altere los resultados.
    snapshots = {}

    for name, state in states.items():

        snapshots[name] = {
            "temperature": float(state["temperature"]),
            "w": max(0.0, float(state["w"])),
            "dry_air_kg": max(
                0.01,
                float(state["dry_air_kg"])
            ),
            "capacity": max(
                1.0,
                float(state["capacity"])
            )
        }

    moisture_delta = {
        name: 0.0 for name in states
    }

    energy_delta = {
        name: 0.0 for name in states
    }

    requested_mass = {
        name: 0.0 for name in states
    }

    transfers = []

    # --------------------------------------------------------------
    # 2. CAUDALES Y MASAS INTERCAMBIADAS
    # --------------------------------------------------------------

    for connection in connections:

        name_a = connection.get("room_a")
        name_b = connection.get("room_b")

        if (
            name_a not in states
            or name_b not in states
            or name_a == name_b
        ):
            continue

        a = snapshots[name_a]
        b = snapshots[name_b]

        q_total = connection_exchange_m3_h(
            connection,
            states[name_a],
            states[name_b],
            rooms[name_a],
            rooms[name_b],
            pressure
        )

        if q_total <= 0.0:
            continue

        # Volumen intercambiado por sentido durante el subpaso.
        exchanged_volume = (
            q_total * dt_s / 3600.0
        )

        if exchanged_volume <= 0.0:
            continue

        # Masa seca equivalente asociada al volumen intercambiado
        # en cada estancia.
        mass_a = dry_air_mass(
            exchanged_volume,
            a["temperature"],
            a["w"],
            pressure
        )

        mass_b = dry_air_mass(
            exchanged_volume,
            b["temperature"],
            b["w"],
            pressure
        )

        # Masa común para ambos sentidos del intercambio.
        # Así se conserva exactamente la masa total de aire seco.
        exchanged_dry_mass = (
            mass_a + mass_b
        ) / 2.0

        if exchanged_dry_mass <= 0.0:
            continue

        transfers.append(
            (
                name_a,
                name_b,
                exchanged_dry_mass
            )
        )

        requested_mass[name_a] += exchanged_dry_mass
        requested_mass[name_b] += exchanged_dry_mass

    if not transfers:
        return

    # --------------------------------------------------------------
    # 3. LIMITACIÓN CONJUNTA POR ESTANCIA
    # --------------------------------------------------------------

    # Cada estancia dispone de una fracción limitada de su masa
    # de aire seco para el intercambio durante el subpaso.
    scale = {}

    for name, snapshot in snapshots.items():

        available_mass = (
            0.45 * snapshot["dry_air_kg"]
        )

        requested = requested_mass[name]

        if (
            requested > available_mass
            and requested > 0.0
        ):
            scale[name] = (
                available_mass / requested
            )
        else:
            scale[name] = 1.0

    # --------------------------------------------------------------
    # 4. BALANCES DE MASA Y ENERGÍA
    # --------------------------------------------------------------

    for name_a, name_b, requested in transfers:

        a = snapshots[name_a]
        b = snapshots[name_b]

        # La transferencia se limita aplicando el factor más
        # restrictivo de las dos estancias conectadas.
        exchanged_dry_mass = (
            requested
            * min(
                scale[name_a],
                scale[name_b]
            )
        )

        if exchanged_dry_mass <= 0.0:
            continue

        # ----------------------------------------------------------
        # Balance de humedad.
        # ----------------------------------------------------------

        # A recibe el aire de B y entrega su propio aire a B.
        moisture_a = (
            exchanged_dry_mass
            * (b["w"] - a["w"])
        )

        moisture_delta[name_a] += moisture_a
        moisture_delta[name_b] -= moisture_a

        # ----------------------------------------------------------
        # Balance sensible.
        #
        # CP_AIR + 1860*w representa el calor específico sensible
        # del aire húmedo por kg de aire seco.
        #
        # No se incorpora el término latente 2501*w.
        # La transferencia se expresa en J.
        # ----------------------------------------------------------

        cp_moist_a = (
            CP_AIR + 1860.0 * a["w"]
        )

        cp_moist_b = (
            CP_AIR + 1860.0 * b["w"]
        )

        cp_exchange = (
            cp_moist_a + cp_moist_b
        ) / 2.0

        energy_a = (
            exchanged_dry_mass
            * cp_exchange
            * (b["temperature"] - a["temperature"])
        )

        energy_delta[name_a] += energy_a
        energy_delta[name_b] -= energy_a

    # --------------------------------------------------------------
    # 5. APLICACIÓN SIMULTÁNEA
    # --------------------------------------------------------------

    for name, state in states.items():

        snapshot = snapshots[name]

        dry_mass = snapshot["dry_air_kg"]
        capacity = snapshot["capacity"]

        state["w"] = max(
            0.0,
            snapshot["w"]
            + moisture_delta[name] / dry_mass
        )

        # Actualización de la temperatura.
        # La energía intercambiada se distribuye sobre la capacidad
        # térmica efectiva del nodo concentrado.
        state["temperature"] = (
            snapshot["temperature"]
            + energy_delta[name] / capacity
        )

        # La masa seca se recalcula con el estado termodinámico
        # actualizado y el volumen constante de la estancia.
        update_dry_air_mass(
            state,
            pressure
        )

def apply_condensation(state, psych, pressure):
    """Condensación del exceso sobre saturación. Devuelve la masa condensada."""
    w_sat = saturation_humidity_ratio(psych, state["temperature"], pressure)
    if state["w"] <= w_sat:
        state["condensation"] = False
        return 0.0
    excess = state["w"] - w_sat
    condensate = excess * state["dry_air_kg"]
    state["w"] = w_sat
    state["condensate_kg"] += condensate
    state["condensate_hour_kg"] += condensate
    state["condensation"] = True
    return condensate
    

def update_dry_air_mass(state, pressure):
    """Actualiza la masa de aire seco tras el cambio de temperatura."""
    state["dry_air_kg"] = dry_air_mass(
        state["volume"],
        state["temperature"],
        state["w"],
        pressure
    )

def simulate_room_substep(room, state, config, weather,
                          psych, hour, dt_s):
    """
    Evoluciona el estado térmico e higrométrico de una estancia
    durante un subpaso temporal.

    Los equipos funcionan con potencia fija cuando están activos.
    La duración efectiva de funcionamiento se calcula dentro del
    subpaso, sin modular la potencia nominal.

    Variables de estado:
        temperature: temperatura seca, °C.
        w: humedad específica, kg vapor/kg aire seco.

    La HR se obtiene de T y w mediante las funciones psicrométricas.

    La humedad objetivo se determina a partir de la temperatura
    y humedad relativa de consigna, manteniendo constante la
    humedad específica objetivo durante toda la simulación.

    La ventilación se incorpora como conductancia térmica adicional.
    Su balance de humedad se resuelve exponencialmente.
    La ventilación intercambia masa de aire y energía sensible.

    Los equipos trabajan a potencia fija o apagados:
        - calefacción: potencia configurada o cero.
        - deshumidificador: capacidad de extracción o apagado.

    Las ganancias térmicas del deshumidificador incluyen:
        - electricidad consumida, ajustada por dehumidifier_heat_factor.
        - calor latente recuperado por la condensación del vapor.

    No se utiliza la entalpía completa para convertir el contenido
    latente de vapor en variaciones de temperatura.
    """

    # --------------------------------------------------------------
    # 1. CONDICIONES INICIALES
    # --------------------------------------------------------------

    pressure = float(config["pressure_pa"])

    t = float(state["temperature"])
    w = max(0.0, float(state["w"]))

    tout = float(weather["temperature"])
    rhout = float(weather["rh"])
    solar_ghi = max(
        0.0,
        float(weather["solar"])
    )

    wout = psych.humidity_ratio(
        tout,
        rhout,
        pressure
    )

    volume = float(state["volume"])

    dry_mass = max(
        0.01,
        float(state["dry_air_kg"])
    )

    dt_s = float(dt_s)

    if dt_s <= 0.0:
        raise ValueError(
            "El intervalo de integración debe ser positivo."
        )

    dt_h = dt_s / 3600.0

    capacity = max(
        1.0,
        float(state["capacity"])
    )

    # Consignas de referencia.
    target_temperature = float(
        config["target_temperature"]
    )

    target_rh = float(
        config["target_rh"]
    )

    # Humedad específica de consigna, calculada a la temperatura
    # de consigna y no a la temperatura instantánea.
    target_w = psych.humidity_ratio(
        target_temperature,
        target_rh,
        pressure
    )

    # ------------------------------------------------------------------
    # 2. PARÁMETROS DE LOS EQUIPOS DE LA ESTANCIA
    # ------------------------------------------------------------------

    # La ausencia de un indicador de disponibilidad significa
    # que el equipo NO está instalado en esta estancia.
    heater_enabled = bool(
        resolve_room_param(
            room,
            config,
            "heater_enabled",
            False
        )
    )

    dehumidifier_enabled = bool(
        resolve_room_param(
            room,
            config,
            "dehumidifier_enabled",
            False
        )
    )

    # Potencia térmica nominal de calefacción.
    # Representa el escalón de funcionamiento elegido en la configuración.
    heater_kw = max(
        0.0,
        float(
            resolve_room_param(
                room,
                config,
                "heater_kw",
                0.0
            )
        )
    )

    heating_type = resolve_room_param(
        room,
        config,
        "heating_type",
        "butane"
    )

    # Capacidad nominal del deshumidificador.
    dehumidifier_l_day = max(
        0.0,
        float(
            resolve_room_param(
                room,
                config,
                "dehumidifier_l_day",
                0.0
            )
        )
    )

    # Potencia eléctrica nominal del deshumidificador.
    dehumidifier_power_kw = max(
        0.0,
        float(
            resolve_room_param(
                room,
                config,
                "dehumidifier_power_kw",
                0.0
            )
        )
    )

    # Fracción de la potencia eléctrica que se contabiliza como
    # ganancia térmica sensible en el recinto.
    # Se conserva el valor de configuración, que puede ser global
    # o específico de la estancia.
    dehumidifier_heat_factor = clamp(
        float(
            resolve_room_param(
                room,
                config,
                "dehumidifier_heat_factor",
                config.get("dehumidifier_heat_factor", 1.0)
            )
        ),
        0.0,
        1.0
    )

    cop = max(
        1.0,
        float(config.get("heat_pump_cop", 3.0))
    )

    # Ganancia sensible interna adicional.
    internal_gain_w = max(
        0.0,
        float(
            resolve_room_param(
                room,
                config,
                "internal_gain_w",
                0.0
            )
        )
    )

    # --------------------------------------------------------------
    # 3. VENTILACIÓN Y BALANCE DE HUMEDAD
    # --------------------------------------------------------------

    # Renovaciones permanentes de la estancia.
    # Representan infiltración/ventilación base, no un equipo activable.
    ach_base = max(
        0.0,
        float(room.get("air_changes_h", 0.0))
    )

    # Caudal máximo disponible por las ventanas configuradas.
    # window_airflow ya tiene en cuenta:
    #   - windows_open
    #   - window_opening_area_m2
    #   - window_airflow_m3_h, si se ha especificado
    #   - velocidad del viento
    if "_window_airflow" in state:
        q_window = max(
            0.0,
            float(state.get("_window_airflow", 0.0))
        )
    else:
        q_window = window_airflow(
            room,
            weather
        )

        state["_window_airflow"] = q_window

    # Caudal máximo disponible por la apertura configurada expresado como renovaciones/hora.
    ach_window_available = (
        q_window / max(0.1, volume)
    )

    # El ACH máximo es un límite para la renovación total.
    # La ventilación adicional nunca puede superar el caudal
    # físicamente disponible por las ventanas configuradas.
    ventilation_max_ach = max(
        0.0,
        float(config.get("ventilation_max_ach", 2.0))
    )

    # La ventilación adicional nunca puede superar:
    #   - El caudal de ventana disponible.
    #   - El límite global de ACH.
    ach_window_limit = min(
        ach_window_available,
        max(
            0.0,
            ventilation_max_ach - ach_base
        )
    )

    ventilation_control = bool(
        config.get("ventilation_control", True)
    )

    if ventilation_control:

        # La ventilación automática funciona cuando:
        #   - La humedad interior supera la consigna.
        #   - El exterior tiene menor humedad específica.
        #
        # Su caudal máximo es el que permite la apertura configurada.
        ach_window_used = ventilation_control_ach(
            w,
            wout,
            target_w,
            ach_base,
            ach_base + ach_window_limit,
            True
        )

    else:

        # Si el control automático está deshabilitado,
        # la ventana configurada como abierta produce su caudal manual.
        ach_window_used = ach_window_limit

    # Renovación total efectiva solicitada.
    ach_total = (
        ach_base + ach_window_used
    )

    ventilation_w = 0.0

    if ach_total > 0.0:

        # Solución exponencial del balance de humedad para un caudal
        # constante durante todo el subpaso.
        decay = math.exp(
            -ach_total * dt_h
        )

        # Balance exponencial de humedad.
        w = (
            wout
            + (w - wout) * decay
        )

        w = max(0.0, w)


        # Fracción de aire sustituida durante el subpaso.
        # Se obtiene de la solución exponencial para ACH constante.
        exchange_fraction = (
            1.0 - decay
        )

        # Límite de estabilidad para intercambios muy elevados.
        # Se aplica también al balance de humedad, para mantener
        # la coherencia entre la masa y la energía intercambiadas.
        exchange_fraction = min(
            0.45,
            max(0.0, exchange_fraction)
        )

        # Masa seca intercambiada durante el subpaso.
        exchanged_dry_mass = (
            dry_mass * exchange_fraction
        )

        # Capacidad calorífica específica sensible del aire húmedo.
        # Se utiliza un valor medio entre el aire interior y exterior.
        # No se incluye el término de calor latente de vaporización.
        cp_inside = CP_AIR + 1860.0 * max(
            0.0,
            float(state["w"])
        )

        cp_outside = CP_AIR + 1860.0 * wout

        cp_exchange = (
            cp_inside + cp_outside
        ) / 2.0

        # Transporte de energía sensible.
        ventilation_energy_j = (
            exchanged_dry_mass
            * cp_exchange
            * (tout - t)
        )

        # Potencia térmica media equivalente del intercambio.
        ventilation_w = (
            ventilation_energy_j / dt_s
        )

        state["ventilation_m3"] += (
            ach_total * volume * dt_h
        )

    # El contador de minutos refleja la ventilación adicional
    # por ventanas, no las renovaciones base permanentes.
    if ach_window_used > 0.0:

        # Solo se contabiliza como tiempo de ventilación activa
        # la parte adicional correspondiente a ventanas/control.
        # Las renovaciones base son permanentes.
        state["ventilation_minutes"] += (
            dt_h * 60.0
        )

    # --------------------------------------------------------------
    # 4. OCUPACIÓN Y GENERACIÓN DE HUMEDAD
    # --------------------------------------------------------------

    people = room_occupancy(
        room,
        config,
        hour
    )

    moisture_per_person = max(
        0.0,
        float(config.get("moisture_per_person_g_h", 0.0))
    )

    sensible_gain_per_person = max(
        0.0,
        float(config.get("sensible_gain_per_person_w", 0.0))
    )

    moisture_kg = (
        people
        * moisture_per_person
        / 1000.0
        * dt_h
    )

    w += (
        moisture_kg / dry_mass
    )

    # Ganancias sensibles por ocupación y otros equipos internos.
    sensible_w = (
        people * sensible_gain_per_person
        + internal_gain_w
    )

    # --------------------------------------------------------------
    # 5. GANANCIA SOLAR
    # --------------------------------------------------------------

    solar_w = room_solar_gain_w(
        room,
        solar_ghi,
        config,
        int(weather["hour"]),
        int(hour) // 24
    )

    # --------------------------------------------------------------
    # 6. DESHUMIDIFICACIÓN
    # --------------------------------------------------------------

    extracted_kg = 0.0
    dehum_minutes = 0.0
    dehum_heat_w = 0.0
    dehum_electric_kwh = 0.0

    if (
        dehumidifier_enabled
        and dehumidifier_l_day > 0.0
    ):

        # HR instantánea: se utiliza para estimar la capacidad
        # real de extracción del aparato.
        rh = psych.relative_humidity(
            t,
            w,
            pressure
        )

        cap_kg_h = dehumidifier_capacity_kg_h(
            dehumidifier_l_day,
            t,
            rh
        )

        # Cantidad de agua que debe extraerse para alcanzar
        # la humedad específica correspondiente a las consignas.
        excess_kg = max(
            0.0,
            (w - target_w) * dry_mass
        )

        if (
            excess_kg > 0.0
            and cap_kg_h > 0.0
        ):

            # Extracción limitada por la capacidad del aparato
            # y por la cantidad de agua que excede la consigna.
            extracted_kg = min(
                excess_kg,
                cap_kg_h * dt_h
            )

            w -= (
                extracted_kg / dry_mass
            )

            w = max(0.0, w)

            state["dehumidified_kg"] += (
                extracted_kg
            )

            # Tiempo real de funcionamiento dentro del subpaso.
            # Se desconecta cuando alcanza la consigna.
            dehum_minutes = min(
                dt_h * 60.0,
                extracted_kg / cap_kg_h * 60.0
            )

            state["dehumidifier_minutes"] += (
                dehum_minutes
            )

            # Energía eléctrica consumida.
            dehum_electric_kwh = (
                dehumidifier_power_kw
                * dehum_minutes / 60.0
            )

            state["dehumidifier_kwh"] += (
                dehum_electric_kwh
            )

            # Ganancia térmica sensible.
            # No se suma el calor latente de condensación:
            # ya está incluido en el ciclo frigorífico del aparato.
            duty_fraction = (
                dehum_minutes / (dt_h * 60.0)
            )

            # Ganancia sensible debida al consumo eléctrico.
            electric_heat_w = (
                dehumidifier_power_kw
                * 1000.0
                * dehumidifier_heat_factor
                * duty_fraction
            )

            # Calor latente recuperado al condensar el vapor extraído.
            # Se distribuye sobre la duración completa del subpaso.
            latent_heat_w = (
                extracted_kg * H_FG
            ) / dt_s

            dehum_heat_w = (
                electric_heat_w
                + latent_heat_w
            )

    # --------------------------------------------------------------
    # 7. CONDUCTANCIA TÉRMICA DE ENVOLVENTE Y VENTILACIÓN
    # --------------------------------------------------------------

    ua_envelope = max(
        0.0,
        float(state["ua_envelope"])
    )

    # Estado medio representativo del aire intercambiado.
    mean_temperature = (
        t + tout
    ) / 2.0

    mean_w = (
        max(0.0, w)
        + max(0.0, wout)
    ) / 2.0

    ua_total = room_ua(
        room,
        ach_override=ach_total,
        temperature=mean_temperature,
        humidity_ratio=mean_w,
        pressure=pressure
    )

    ua_vent = max(
        0.0,
        ua_total - ua_envelope
    )

    # Las ganancias térmicas no contienen un término adicional
    # de ventilación: su efecto ya está incluido en UA_total.
    gains_without_heating = (
        sensible_w
        + solar_w
        + dehum_heat_w
    )

    # Temperatura que se alcanzaría sin calefacción.
    t_free = exact_thermal_step(
        t,
        tout,
        ua_total,
        capacity,
        gains_without_heating,
        dt_s
    )

    # --------------------------------------------------------------
    # 8. CALEFACCIÓN A POTENCIA FIJA
    # --------------------------------------------------------------

    heater_power_w = (
        heater_kw * 1000.0
    )

    heater_on_seconds = 0.0

    def temperature_after_heater(on_seconds):
        """
        Calcula la temperatura final del subpaso suponiendo que
        la calefacción funciona a potencia fija durante on_seconds
        y permanece apagada durante el resto.

        No existe modulación de potencia: el equipo está encendido
        a potencia nominal o apagado.
        """

        on_seconds = clamp(
            float(on_seconds),
            0.0,
            dt_s
        )

        off_seconds = (
            dt_s - on_seconds
        )

        temperature = t

        if on_seconds > 1e-9:

            temperature = exact_thermal_step(
                temperature,
                tout,
                ua_total,
                capacity,
                gains_without_heating + heater_power_w,
                on_seconds
            )

        # Segunda fase: calefacción apagada.
        if off_seconds > 1e-9:

            temperature = exact_thermal_step(
                temperature,
                tout,
                ua_total,
                capacity,
                gains_without_heating,
                off_seconds
            )

        return temperature

    if (
        heater_enabled
        and heater_power_w > 0.0
        and t < target_temperature
        and t_free < target_temperature
    ):

        # Temperatura final si la calefacción permaneciese
        # encendida durante todo el subpaso.
        t_full = temperature_after_heater(
            dt_s
        )

        if t_full <= target_temperature:

            # La potencia nominal completa durante todo el intervalo
            # no llega a superar la consigna.
            heater_on_seconds = dt_s

        else:

            # La calefacción a potencia nominal superaría la consigna.
            # Buscamos el instante de desconexión dentro del subpaso.
            #
            # Se utiliza bisección para encontrar el tiempo durante
            # el que el equipo debe estar encendido a potencia fija.
            low = 0.0
            high = dt_s

            for _ in range(50):

                middle = (
                    low + high
                ) / 2.0

                t_middle = temperature_after_heater(
                    middle
                )

                if t_middle < target_temperature:
                    low = middle
                else:
                    high = middle

            heater_on_seconds = (
                low + high
            ) / 2.0

    # Temperatura final con la duración de funcionamiento calculada.
    t_new = temperature_after_heater(
        heater_on_seconds
    )

    # Potencia media equivalente durante el subpaso.
    # La potencia instantánea cuando está encendida sigue siendo
    # exactamente heater_power_w.
    heater_w = (
        heater_power_w
        * heater_on_seconds / dt_s
    )

    # --------------------------------------------------------------
    # 9. HUMEDAD GENERADA POR COMBUSTIÓN
    # --------------------------------------------------------------

    combustion_g = 0.0

    heater_kwh_th = (
        heater_power_w
        * heater_on_seconds
        / 3600000.0
    )

    if (
        heating_type == "butane"
        and heater_kwh_th > 0.0
    ):

        # Energía química consumida como combustible.
        fuel_kwh = heater_energy_kwh(
            heater_kwh_th,
            heating_type,
            cop
        )

        combustion_g = (
            fuel_kwh
            * float(
                config.get(
                    "combustion_moisture_g_kwh",
                    75.0
                )
            )
        )

        # Incorporación del vapor generado por la combustión.
        w += (
            combustion_g / 1000.0
        ) / dry_mass

    # --------------------------------------------------------------
    # 10. CONSUMO ENERGÉTICO DE CALEFACCIÓN
    # --------------------------------------------------------------

    heater_kwh = heater_energy_kwh(
        heater_kwh_th,
        heating_type,
        cop
    )

    state["heater_kwh_th"] += (
        heater_kwh_th
    )

    state["heater_kwh"] += (
        heater_kwh
    )

    state["heater_butane_kg"] += (
        heater_butane_kg(
            heater_kwh_th,
            heating_type
        )
    )

    if heater_on_seconds > 0.0:

        state["heater_minutes"] += (
            heater_on_seconds / 60.0
        )

    # --------------------------------------------------------------
    # 11. ACTUALIZACIÓN Y CONDENSACIÓN
    # --------------------------------------------------------------

    state["temperature"] = t_new
    state["w"] = max(0.0, w)

    update_dry_air_mass(
        state,
        pressure
    )

    # Condensación si la humedad específica supera la saturación
    # correspondiente a la temperatura final.
    condensate = apply_condensation(
        state,
        psych,
        pressure
    )

    if condensate > 0.0:

        # El calor latente liberado por condensación se incorpora
        # a la capacidad térmica concentrada de la estancia.
        state["temperature"] += (
            condensate
            * H_FG
            / max(1.0, capacity)
        )

    update_dry_air_mass(
        state,
        pressure
    )

    # --------------------------------------------------------------
    # 12. RESULTADO DEL SUBPASO
    # --------------------------------------------------------------

    return {
        "people": people,

        "solar_ghi": solar_ghi,
        "solar_w": solar_w,

        "ua": ua_total,
        "ua_envelope": ua_envelope,
        "ua_vent": ua_vent,

        "heater_w": heater_w,
        "heater_on_w": (
            heater_power_w
            if heater_on_seconds > 0.0
            else 0.0
        ),
        "heater_kw": heater_kw,
        "heater_on_minutes": (
            heater_on_seconds / 60.0
        ),

        "dehum_heat_w": dehum_heat_w,
        "dehum_minutes": dehum_minutes,
        "dehum_kg": extracted_kg,

        "combustion_g": combustion_g,

        "ventilation_ach": ach_total,
        "ventilation_window_ach": ach_window_used,
        "ventilation_w": ventilation_w,
        "heater_kwh_th": heater_kwh_th,
        "heating_type": heating_type
    }

# ---------------------------------------------------------------------------
# RESULTADOS HORARIOS
# ---------------------------------------------------------------------------

def counter_delta(state, key):
    """Incremento de un contador acumulado desde el inicio de la hora."""
    base = 0.0
    hour_base = state.get("_hour_base") or {}
    if key in hour_base:
        base = float(hour_base[key])
    return max(0.0, float(state.get(key, 0.0)) - base)


def room_hour_result(room, state, config, psych, weather,
                     hour, hour_data):
    """
    Construye el resultado horario de una estancia.

    tin, rh y w_g_kg:
        Estado al final de la hora.

    tin_avg, rh_avg y w_g_kg_avg:
        Condiciones medias durante los subpasos de esa hora.

    wet_bulb_c:
        Temperatura de bulbo húmedo calculada con las condiciones
        medias horarias. Se utiliza como indicador higrotérmico
        comparativo, no como PMV.

    Los consumos, caudales y minutos son el incremento de esa hora,
    no el total desde el inicio de la simulación. Los campos *_total
    conservan el acumulado.
    """

    pressure = float(config["pressure_pa"])

    # --------------------------------------------------------------
    # ESTADO FINAL
    # --------------------------------------------------------------

    t = float(state["temperature"])
    w = max(0.0, float(state["w"]))

    rh = psych.relative_humidity(t, w, pressure)
    dew = psych.dew_point(t, w, pressure)

    # --------------------------------------------------------------
    # MEDIAS HORARIAS
    # --------------------------------------------------------------

    samples = max(
        1,
        int(hour_data.get("samples", 1))
    )

    t_avg = (
        hour_data.get("temperature_sum", t)
        / samples
    )

    w_avg = max(
        0.0,
        hour_data.get("humidity_ratio_sum", w)
        / samples
    )

    rh_avg = psych.relative_humidity(
        t_avg,
        w_avg,
        pressure
    )

    wet_bulb = wet_bulb_temperature_c(
        psych,
        t_avg,
        w_avg,
        pressure
    )

    # --------------------------------------------------------------
    # INDICADOR DE CONDENSACIÓN SUPERFICIAL
    # --------------------------------------------------------------

    tout = float(weather["temperature"])

    surface_factor = clamp(
        float(config.get("surface_factor", 0.75)),
        0.0,
        1.0
    )

    t_surface = (
        t
        - (t - tout) * (1.0 - surface_factor)
    )

    # --------------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------------

    result = {
        "hour": hour,

        "tout": tout,
        "rhout": float(weather["rh"]),

        # Radiación global horizontal exterior.
        "solar": float(weather["solar"]),

        # Estado final.
        "tin": t,
        "rh": rh,
        "w_g_kg": w * 1000.0,

        # Medias horarias.
        "tin_avg": t_avg,
        "rh_avg": rh_avg,
        "w_g_kg_avg": w_avg * 1000.0,

        # Indicador higrotérmico comparativo.
        "wet_bulb_c": wet_bulb,
        "hygrothermal_index_c": wet_bulb,

        # Punto de rocío y condensación superficial estimada.
        "dew": dew,
        "surface": t_surface,
        "condensation": t_surface <= dew,

        # Condensación efectiva en el aire.
        "condensate_kg": state["condensate_hour_kg"],
        "condensate_total_kg": state["condensate_kg"],

        # Deshumidificación.
        "dehum_kg": counter_delta(
            state, "dehumidified_kg"
        ),
        "dehum_kg_total": state["dehumidified_kg"],

        "dehum_kwh": counter_delta(
            state, "dehumidifier_kwh"
        ),
        "dehum_kwh_total": state["dehumidifier_kwh"],

        "dehum_min": counter_delta(
            state, "dehumidifier_minutes"
        ),
        "dehum_min_total": state["dehumidifier_minutes"],

        # Calefacción.
        "heater_kwh": counter_delta(
            state, "heater_kwh"
        ),
        "heater_kwh_total": state["heater_kwh"],

        "heater_kwh_th": counter_delta(
            state, "heater_kwh_th"
        ),
        "heater_kwh_th_total": state["heater_kwh_th"],

        "heater_butane_kg": counter_delta(
            state, "heater_butane_kg"
        ),
        "heater_butane_kg_total": state["heater_butane_kg"],

        "heat_min": counter_delta(
            state, "heater_minutes"
        ),
        "heat_min_total": state["heater_minutes"],

        # Ventilación.
        "ventilation_m3": counter_delta(
            state, "ventilation_m3"
        ),
        "ventilation_m3_total": state["ventilation_m3"],

        "vent_min": counter_delta(
            state, "ventilation_minutes"
        ),
        "vent_min_total": state["ventilation_minutes"],

        # Estado físico de la estancia.
        "dry_air_kg": state["dry_air_kg"],
        "ua": hour_data["ua"],
        "capacity_mj_k": state["capacity"] / 1000000.0,

        # Ganancia solar media de la hora.
        "solar_w": hour_data["solar_w"],

        "people": hour_data["people"]
    }

    return result

# ---------------------------------------------------------------------------
# SIMULACION MULTIESTANCIA
# ---------------------------------------------------------------------------

def normalize_weather_row(row):
    """Convierte una fila meteorológica en un diccionario."""
    return {
        "hour": int(row[0]),
        "temperature": float(row[1]),
        "rh": float(row[2]),
        "solar": float(row[3]),
        "wind_speed_m_s": (
            float(row[4]) if len(row) > 4 else 0.0
        ),
        "wind_direction_deg": (
            float(row[5]) if len(row) > 5 else None
        )
    }


def normalize_connections(config, room_names):
    """
    Normaliza las conexiones.

    Formato:
    {
        "room_a": "SALON",
        "room_b": "COCINA",
        "type": "open",
        "ventilation_transfer_factor": 0.5
    }
    """
    connections = []

    for connection in config.get("connections", []):
        a = connection.get("room_a")
        b = connection.get("room_b")

        if a not in room_names or b not in room_names or a == b:
            continue

        item = copy.deepcopy(connection)

        item.setdefault("type", "open")
        item.setdefault("ventilation_transfer_factor", 0.0)

        connections.append(item)

    return connections

def simulate(config, selected_room=None, hours=24, substep_minutes=5):
    """
    Simula la vivienda completa, manteniendo todas las estancias
    y sus conexiones.

    selected_room:
        None -> presenta los resultados globales.
        int  -> presenta los resultados de la estancia por índice.
        str  -> presenta los resultados de la estancia por nombre.

    La selección NO altera el proceso físico de simulación.

    Aunque se solicite una única estancia, todas las habitaciones
    conectadas participan en la evolución de sus estados.

    Devuelve:
        results:
            Resultados de la vista seleccionada.

        global_results:
            Resultados globales de toda la vivienda.

        rooms:
            Resultados horarios de cada estancia.

        room_results:
            Resumen final de todas las estancias.
    """

    psych = Psychrometrics()

    rooms_cfg = copy.deepcopy(
        config.get("rooms", [])
    )

    if not rooms_cfg:
        raise ValueError(
            "No hay estancias configuradas."
        )

    if len(config.get("weather", [])) < 24:
        raise ValueError(
            "El perfil meteorológico debe contener 24 horas."
        )

    hours = int(hours)
    substep_minutes = float(substep_minutes)

    if hours <= 0:
        raise ValueError(
            "El número de horas debe ser positivo."
        )

    if substep_minutes <= 0:
        raise ValueError(
            "El subpaso debe ser positivo."
        )

    # --------------------------------------------------------------
    # 1. PREPARACIÓN DE TODAS LAS ESTANCIAS
    # --------------------------------------------------------------

    room_names_list = [
        room["name"]
        for room in rooms_cfg
    ]

    if len(set(room_names_list)) != len(room_names_list):
        raise ValueError(
            "Hay nombres de estancia duplicados."
        )

    room_map = {
        room["name"]: room
        for room in rooms_cfg
    }

    room_names = set(
        room_map.keys()
    )

    # Todas las conexiones se mantienen.
    connections = normalize_connections(
        config,
        room_names
    )

    # --------------------------------------------------------------
    # 2. INICIALIZACIÓN DE ESTADOS
    # --------------------------------------------------------------

    states = {}

    for room in rooms_cfg:

        states[room["name"]] = create_room_state(
            room,
            config,
            psych
        )

    results_by_room = {
        room["name"]: []
        for room in rooms_cfg
    }

    # --------------------------------------------------------------
    # 3. RESOLUCIÓN TEMPORAL
    # --------------------------------------------------------------

    dt_s = (
        substep_minutes * 60.0
    )

    steps_per_hour = int(
        round(3600.0 / dt_s)
    )

    if (
        abs(steps_per_hour * dt_s - 3600.0)
        > 1e-6
    ):
        raise ValueError(
            "El subpaso debe dividir exactamente una hora."
        )

    # --------------------------------------------------------------
    # 4. SIMULACIÓN HORARIA
    # --------------------------------------------------------------

    for hour in range(hours):

        wx_row = config["weather"][hour % 24]

        weather = normalize_weather_row(
            wx_row
        )

        # ----------------------------------------------------------
        # 4.1. REINICIO DE ACUMULADORES HORARIOS
        # ----------------------------------------------------------

        for state in states.values():

            state["condensate_hour_kg"] = 0.0

            state["_hour_base"] = {
                "dehumidified_kg": state["dehumidified_kg"],
                "dehumidifier_kwh": state["dehumidifier_kwh"],
                "heater_kwh": state["heater_kwh"],
                "heater_kwh_th": state["heater_kwh_th"],
                "heater_butane_kg": state["heater_butane_kg"],
                "ventilation_m3": state["ventilation_m3"],
                "ventilation_minutes": state["ventilation_minutes"],
                "dehumidifier_minutes": state["dehumidifier_minutes"],
                "heater_minutes": state["heater_minutes"]
            }

        # Acumuladores de las variables horarias.
        hour_data = {}

        for name in states:

            hour_data[name] = {
                "ua": 0.0,
                "solar_w": 0.0,
                "people": 0,

                "temperature_sum": 0.0,
                "humidity_ratio_sum": 0.0,

                "samples": 0
            }

        # ----------------------------------------------------------
        # 4.2. SUBPASOS DE CINCO MINUTOS
        # ----------------------------------------------------------

        for step in range(steps_per_hour):

            # A. Caudales de las ventanas.
            #
            # Se calculan antes del intercambio entre estancias.
            for room in rooms_cfg:

                states[room["name"]]["_window_airflow"] = (
                    window_airflow(
                        room,
                        weather
                    )
                )

            # B. Intercambio entre estancias.
            #
            # Se utilizan todos los estados simultáneamente.
            exchange_air_between_rooms(
                states,
                connections,
                room_map,
                float(config["pressure_pa"]),
                dt_s
            )

            # C. Evolución individual de cada estancia.
            for room in rooms_cfg:

                name = room["name"]

                data = simulate_room_substep(
                    room,
                    states[name],
                    config,
                    weather,
                    psych,
                    hour,
                    dt_s
                )

                # Acumulación de conductancia y ganancias solares.
                hour_data[name]["ua"] += (
                    data["ua"]
                )

                hour_data[name]["solar_w"] += (
                    data["solar_w"]
                )

                hour_data[name]["people"] = (
                    data["people"]
                )

                # Acumulación de los estados al final de cada subpaso.
                # Se utilizará para obtener las medias horarias.
                hour_data[name]["temperature_sum"] += (
                    states[name]["temperature"]
                )

                hour_data[name]["humidity_ratio_sum"] += (
                    states[name]["w"]
                )

                hour_data[name]["samples"] += 1

        # ----------------------------------------------------------
        # 4.3. RESULTADOS HORARIOS DE CADA ESTANCIA
        # ----------------------------------------------------------

        for room in rooms_cfg:

            name = room["name"]

            hour_data[name]["ua"] /= (
                steps_per_hour
            )

            hour_data[name]["solar_w"] /= (
                steps_per_hour
            )

            result = room_hour_result(
                room,
                states[name],
                config,
                psych,
                weather,
                hour,
                hour_data[name]
            )

            results_by_room[name].append(
                result
            )

    # --------------------------------------------------------------
    # 5. RESUMEN DE CADA ESTANCIA
    # --------------------------------------------------------------

    room_summary = {}

    for room in rooms_cfg:

        name = room["name"]

        rows = results_by_room[name]

        if not rows:
            continue

        last = rows[-1]

        mean_ua = (
            sum(
                row["ua"]
                for row in rows
            ) / len(rows)
        )

        room_summary[name] = {
            "tin": last["tin"],
            "rh": last["rh"],
            "w_g_kg": last["w_g_kg"],
            "wet_bulb_c": last["wet_bulb_c"],

            "condensate_kg": sum(
                row.get("condensate_kg", 0.0)
                for row in rows
            ),

            "volume": states[name]["volume"],
            "capacity": states[name]["capacity"],
            "ua": mean_ua
        }

    # --------------------------------------------------------------
    # 6. MAGNITUDES GLOBALES
    # --------------------------------------------------------------

    total_volume = sum(
        state["volume"]
        for state in states.values()
    )

    total_capacity = sum(
        state["capacity"]
        for state in states.values()
    )

    total_ua = sum(
        room_summary[name]["ua"]
        for name in room_summary
    )

    # --------------------------------------------------------------
    # 7. RESULTADOS GLOBALES HORARIOS
    # --------------------------------------------------------------

    global_results = []

    for index in range(hours):

        total_dry_mass = 0.0

        # Estados finales.
        weighted_temperature = 0.0
        weighted_w = 0.0
        weighted_surface = 0.0

        # Medias temporales horarias.
        weighted_temperature_avg = 0.0
        weighted_w_avg = 0.0

        room_rows = [
            results_by_room[name][index]
            for name in results_by_room
        ]

        for result in room_rows:

            mass = max(
                0.01,
                float(result.get("dry_air_kg", 0.0))
            )

            total_dry_mass += mass

            weighted_temperature += (
                result["tin"] * mass
            )

            weighted_w += (
                result["w_g_kg"] / 1000.0 * mass
            )

            weighted_surface += (
                result.get("surface", result["tin"])
                * mass
            )

            weighted_temperature_avg += (
                result["tin_avg"] * mass
            )

            weighted_w_avg += (
                result["w_g_kg_avg"] / 1000.0 * mass
            )

        mean_t = (
            weighted_temperature
            / max(0.01, total_dry_mass)
        )

        mean_w = (
            weighted_w
            / max(0.01, total_dry_mass)
        )

        mean_surface = (
            weighted_surface
            / max(0.01, total_dry_mass)
        )

        mean_t_avg = (
            weighted_temperature_avg
            / max(0.01, total_dry_mass)
        )

        mean_w_avg = (
            weighted_w_avg
            / max(0.01, total_dry_mass)
        )

        mean_rh = psych.relative_humidity(
            mean_t,
            mean_w,
            config["pressure_pa"]
        )

        mean_rh_avg = psych.relative_humidity(
            mean_t_avg,
            mean_w_avg,
            config["pressure_pa"]
        )

        mean_dew = psych.dew_point(
            mean_t,
            mean_w,
            config["pressure_pa"]
        )

        mean_wet_bulb = wet_bulb_temperature_c(
            psych,
            mean_t_avg,
            mean_w_avg,
            config["pressure_pa"]
        )

        def sum_key(key):
            return sum(
                row.get(key, 0.0)
                for row in room_rows
            )

        global_results.append({

            "hour": index,

            # Estado final global.
            "tin": mean_t,
            "rh": mean_rh,
            "w_g_kg": mean_w * 1000.0,

            # Medias horarias globales.
            "tin_avg": mean_t_avg,
            "rh_avg": mean_rh_avg,
            "w_g_kg_avg": mean_w_avg * 1000.0,

            # Indicador higrotérmico.
            "wet_bulb_c": mean_wet_bulb,
            "hygrothermal_index_c": mean_wet_bulb,

            "dew": mean_dew,
            "surface": mean_surface,

            "condensation": any(
                row.get("condensation", False)
                for row in room_rows
            ),

            "tout": room_rows[0]["tout"],
            "rhout": room_rows[0]["rhout"],
            "solar": room_rows[0]["solar"],

            # Magnitudes agregadas de las estancias.
            "solar_w": sum_key("solar_w"),
            "ua": sum_key("ua"),

            "condensate_kg": sum_key("condensate_kg"),

            "dehum_kg": sum_key("dehum_kg"),
            "dehum_kwh": sum_key("dehum_kwh"),

            "heater_kwh": sum_key("heater_kwh"),
            "heater_kwh_th": sum_key("heater_kwh_th"),
            "heater_butane_kg": sum_key("heater_butane_kg"),

            "ventilation_m3": sum_key("ventilation_m3"),
            "vent_min": sum_key("vent_min"),

            "dehum_min": sum_key("dehum_min"),
            "heat_min": sum_key("heat_min")
        })

    # --------------------------------------------------------------
    # 8. RESULTADO COMPLETO
    # --------------------------------------------------------------

    full_result = {
        "room": "TODA LA VIVIENDA",

        "results": global_results,
        "global_results": global_results,

        "rooms": results_by_room,
        "room_results": room_summary,

        "room_order": room_names_list,

        "ua": total_ua,
        "volume": total_volume,
        "capacity": total_capacity
    }

    # La selección se aplica exclusivamente a la vista de resultados.
    return select_simulation_view(
        full_result,
        selected_room
    )

def select_simulation_view(simulation_result, selected_room=None):
    """
    Genera una vista de resultados a partir de una simulación completa.

    No ejecuta cálculos físicos ni modifica los resultados almacenados.

    selected_room:
        None -> vista global.
        int  -> índice de la estancia.
        str  -> nombre de la estancia.
    """

    view = dict(simulation_result)

    if (
        selected_room is None
        or selected_room == "TODA LA VIVIENDA"
    ):

        view["room"] = "TODA LA VIVIENDA"

        view["results"] = (
            simulation_result["global_results"]
        )

        view["selected_room"] = None

        return view

    room_order = simulation_result["room_order"]

    if isinstance(selected_room, int):

        if not 0 <= selected_room < len(room_order):
            raise ValueError(
                "Índice de estancia no válido."
            )

        room_name = room_order[selected_room]

    elif isinstance(selected_room, str):

        room_name = selected_room

        if room_name not in simulation_result["rooms"]:
            raise ValueError(
                "La estancia seleccionada no existe."
            )

    else:

        raise ValueError(
            "Selección de estancia no válida."
        )

    view["room"] = room_name

    view["results"] = (
        simulation_result["rooms"][room_name]
    )

    view["selected_room"] = room_name

    room_summary = (
        simulation_result["room_results"][room_name]
    )

    view["ua"] = room_summary["ua"]
    view["volume"] = room_summary["volume"]
    view["capacity"] = room_summary["capacity"]

    return view
    
def simulation_signature(config, hours=24, substep_minutes=5):
    """
    Genera una huella determinista de la configuración de simulación.

    La huella cambia cuando cambia cualquier dato del JSON,
    el número de horas o el intervalo de integración.

    No incluye la selección de estancia: cambiar la vista no
    invalida los resultados calculados.
    """

    payload = {
        "config": config,
        "hours": int(hours),
        "substep_minutes": float(substep_minutes)
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()
    
# ---------------------------------------------------------------------------
# CONFIGURACION Y VALIDACION
# ---------------------------------------------------------------------------

def _ensure_room_defaults(rooms):
    """
    Completa los parámetros predeterminados de las estancias.

    La disponibilidad de los equipos se establece en False cuando
    no está especificada expresamente en el JSON.

    Los valores explícitos existentes se conservan.
    """

    for room in rooms:

        room.setdefault(
            "windows_open",
            False
        )

        room.setdefault(
            "window_opening_area_m2",
            0.0
        )

        room.setdefault(
            "window_airflow_m3_h",
            None
        )

        room.setdefault(
            "wind_factor",
            0.60
        )

        room.setdefault(
            "window_discharge_coefficient",
            0.60
        )

        # La ausencia de equipo no equivale a equipo instalado.
        room.setdefault(
            "heater_enabled",
            False
        )

        room.setdefault(
            "dehumidifier_enabled",
            False
        )

        # Valores técnicos de referencia.
        # Solo se utilizan si el equipo correspondiente está habilitado.
        room.setdefault(
            "heater_kw",
            0.0
        )

        room.setdefault(
            "dehumidifier_l_day",
            0.0
        )

        room.setdefault(
            "dehumidifier_power_kw",
            0.0
        )

        room.setdefault(
            "heating_type",
            "butane"
        )

        room.setdefault(
            "window_groups",
            []
        )
        
def load_config(path=CONFIG_FILE):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        merged = copy.deepcopy(DEFAULT_CONFIG)
        merged.update(data)
        merged.setdefault("connections", [])
        _ensure_room_defaults(merged.get("rooms") or [])
        return merged

    merged = copy.deepcopy(DEFAULT_CONFIG)
    _ensure_room_defaults(merged["rooms"])
    return merged


def save_config(config, path=CONFIG_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def validate_config(cfg):
    """Valida los parámetros básicos del modelo."""
    positive = (
        "pressure_pa",
        "thermal_mass_j_m2k",
        "heater_kw"
    )

    for key in positive:
        if float(cfg[key]) <= 0:
            raise ValueError(
                "El parámetro %s debe ser positivo." % key
            )

    if not 0 < float(cfg["target_rh"]) <= 100:
        raise ValueError(
            "La HR objetivo debe estar entre 0 y 100."
        )

    if not 0 <= float(cfg.get("initial_rh", 0)) <= 100:
        raise ValueError(
            "La HR inicial debe estar entre 0 y 100."
        )

    if float(cfg.get("heat_pump_cop", 1.0)) <= 0:
        raise ValueError(
            "El COP de la bomba de calor debe ser positivo."
        )

    weather = cfg.get("weather") or []
    if len(weather) < 24:
        raise ValueError(
            "El perfil meteorológico debe contener 24 horas."
        )

    for i, row in enumerate(weather):
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            raise ValueError(
                "La hora %d del perfil exterior está incompleta." % i
            )
        rh = float(row[2])
        if not 0 <= rh <= 100:
            raise ValueError(
                "La HR exterior de la hora %d debe estar entre 0 y 100."
                % i
            )
        if float(row[3]) < 0:
            raise ValueError(
                "La radiación de la hora %d no puede ser negativa." % i
            )
        if len(row) > 4 and float(row[4]) < 0:
            raise ValueError(
                "El viento de la hora %d no puede ser negativo." % i
            )
        if len(row) > 5 and not 0 <= float(row[5]) <= 360:
            raise ValueError(
                "La dirección del viento de la hora %d "
                "debe estar entre 0 y 360°." % i
            )

    if not cfg["rooms"]:
        raise ValueError("Debe existir al menos una estancia.")

    room_names = set()

    for room in cfg["rooms"]:
        name = room["name"]

        if name in room_names:
            raise ValueError(
                "Nombre de estancia duplicado: %s" % name
            )
        for key in ("internal_gain_w", "dehumidifier_l_day",
                    "dehumidifier_power_kw", "heater_kw"):
            value = room.get(key)
            if value is not None and float(value) < 0:
                raise ValueError(
                    "%s: %s no puede ser negativo." % (name, key))
        
        ht = room.get("heating_type")
        if ht and ht not in ("butane", "electric", "heat_pump"):
            raise ValueError(
                "%s: tipo de calefacción no válido: %s" % (name, ht))
                                
        room_names.add(name)

        for key in ("height", "floor_area"):
            if float(room[key]) <= 0:
                raise ValueError(
                    "%s: %s debe ser positivo." % (name, key)
                )

        for key in (
            "window_area", "wall_area", "roof_area",
            "floor_exposed_area", "window_u", "wall_u",
            "roof_u", "floor_u", "air_changes_h",
            "thermal_mass_j_m2k", "window_opening_area_m2",
            "wind_factor", "window_discharge_coefficient"
        ):
            if float(room.get(key, 0.0)) < 0:
                raise ValueError(
                    "%s: %s no puede ser negativo." % (name, key)
                )

        custom_flow = room.get("window_airflow_m3_h")

        if custom_flow is not None and float(custom_flow) < 0:
            raise ValueError(
                "%s: el caudal de ventana no puede ser negativo." % name
            )

    for connection in cfg.get("connections", []):
        a = connection.get("room_a")
        b = connection.get("room_b")

        if a not in room_names or b not in room_names:
            raise ValueError(
                "Una conexión hace referencia a una estancia inexistente."
            )

        if a == b:
            raise ValueError(
                "Una estancia no puede conectarse consigo misma."
            )

        factor = float(
            connection.get("ventilation_transfer_factor", 0.0)
        )

        if not 0.0 <= factor <= 1.0:
            raise ValueError(
                "El factor de transferencia debe estar entre 0 y 1."
            )

        if connection.get("type") == "custom":
            flow = connection.get(
                "airflow_m3_h", connection.get("flow_m3_h")
            )
            if flow is None:
                raise ValueError(
                    "La conexión custom entre %s y %s necesita un caudal."
                    % (a, b)
                )
            if float(flow) < 0:
                raise ValueError(
                    "El caudal de la conexión entre %s y %s "
                    "no puede ser negativo." % (a, b)
                )

    if float(cfg.get("ventilation_max_ach", 0.0)) < 0:
        raise ValueError(
            "La ventilación máxima no puede ser negativa."
        )

    if float(cfg.get("dehumidifier_l_day", 0.0)) < 0:
        raise ValueError(
            "La capacidad del deshumidificador no puede ser negativa."
        )

    if float(cfg.get("dehumidifier_power_kw", 0.0)) < 0:
        raise ValueError(
            "La potencia del deshumidificador no puede ser negativa."
        )
    for key in ("internal_gain_w", "dehumidifier_l_day",
                "dehumidifier_power_kw", "heater_kw"):
        if float(room.get(key, 0.0)) < 0:
            raise ValueError(
                "%s: %s no puede ser negativo." % (name, key))
    
    ht = room.get("heating_type")
    if ht and ht not in ("butane", "electric", "heat_pump"):
        raise ValueError(
            "%s: tipo de calefacción no válido: %s" % (name, ht))
                    
# ---------------------------------------------------------------------------
# INTERFAZ GRAFICA
# ---------------------------------------------------------------------------

class App:
    """
    Interfaz gráfica del simulador higrotérmico.

    La interfaz permite:
    - Configurar las condiciones generales de simulación.
    - Gestionar las propiedades térmicas de las estancias.
    - Configurar ventanas abiertas y su superficie efectiva.
    - Configurar las conexiones entre estancias.
    - Editar el perfil meteorológico exterior, incluido el viento.
    - Simular una estancia o la vivienda completa.
    - Consultar resultados, gráficas y exportarlos a CSV.
    """

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1200x850")
        self.root.minsize(1000, 700)

        self.cfg = load_config()
        self.last_simulation = None

        self._build_ui()
        self._refresh_all()

    # -----------------------------------------------------------------------
    # CONSTRUCCION GENERAL
    # -----------------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self.root)
        # CONFIGURACION DE FUENTES Y ALTURA DE FILAS
        style.configure(
            "Treeview",
            font=("Segoe UI", 7),
            rowheight=42
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 7, "bold"),
            padding=(4, 6)
        )

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_sim = ttk.Frame(self.nb)
        self.tab_general = ttk.Frame(self.nb)
        self.tab_rooms = ttk.Frame(self.nb)
        self.tab_connections = ttk.Frame(self.nb)
        self.tab_weather = ttk.Frame(self.nb)

        self.nb.add(self.tab_sim, text="Simulación")
        self.nb.add(self.tab_general, text="Configuración general")
        self.nb.add(self.tab_rooms, text="Estancias")
        self.nb.add(self.tab_connections, text="Conexiones")
        self.nb.add(self.tab_weather, text="Perfil exterior")

        self._build_sim_tab()
        self._build_general_tab()
        self._build_rooms_tab()
        self._build_connections_tab()
        self._build_weather_tab()

    # -----------------------------------------------------------------------
    # UTILIDADES DE INTERFAZ
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_float(value):
        return float(str(value).replace(",", ".").strip())

    @staticmethod
    def _to_int(value):
        return int(float(str(value).replace(",", ".").strip()))

    @staticmethod
    def _format(value, decimals=2):
        try:
            return ("%%.%df" % decimals) % float(value)
        except (TypeError, ValueError):
            return str(value)

    def _normalise_config(self):
        """
        Normaliza la configuración y establece los indicadores
        de disponibilidad de equipos en cada estancia.

        Las configuraciones anteriores que no contienen estos
        indicadores se interpretan como estancias sin equipos.
        """

        if "normalize_config" in globals():
            self.cfg = normalize_config(self.cfg)

        for room in self.cfg.get("rooms", []):

            room.setdefault(
                "heater_enabled",
                False
            )

            room.setdefault(
                "dehumidifier_enabled",
                False
            )

    def _refresh_all(self):
        self._normalise_config()
        self._refresh_rooms()
        self._refresh_connections()
        self._refresh_weather()

    # -----------------------------------------------------------------------
    # PESTAÑA GENERAL
    # -----------------------------------------------------------------------

    def _build_general_tab(self):
        frame = self.tab_general

        # Contenedor desplazable para evitar que los grupos queden
        # fuera de la zona visible en pantallas pequeñas.
        container = ttk.Frame(frame)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        canvas = tk.Canvas(
            container,
            highlightthickness=0
        )

        scroll = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview
        )

        inner = ttk.Frame(canvas)

        window_id = canvas.create_window(
            (0, 0),
            window=inner,
            anchor="nw"
        )

        canvas.configure(yscrollcommand=scroll.set)

        inner.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window_id,
                width=event.width
            )
        )

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self.general_vars = {}
        self.general_bool_vars = {}

        # ------------------------------------------------------------------
        # CONSTRUCTOR DE GRUPOS
        # ------------------------------------------------------------------

        def add_group(title, row, column, fields):
            group = ttk.LabelFrame(
                inner,
                text=title
            )

            group.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=6,
                pady=6
            )

            group.grid_columnconfigure(1, weight=1)

            for index, (key, label) in enumerate(fields):

                # Controles booleanos.
                if key in (
                    "ventilation_control",
                    "solar_enabled"
                ):
                    var = tk.BooleanVar(
                        value=bool(self.cfg.get(key, False))
                    )

                    self.general_bool_vars[key] = var

                    ttk.Checkbutton(
                        group,
                        text=label,
                        variable=var
                    ).grid(
                        row=index,
                        column=0,
                        columnspan=2,
                        sticky="w",
                        padx=7,
                        pady=5
                    )

                # Selector del tipo de calefacción.
                elif key == "heating_type":
                    ttk.Label(
                        group,
                        text=label
                    ).grid(
                        row=index,
                        column=0,
                        sticky="w",
                        padx=7,
                        pady=4
                    )

                    var = tk.StringVar(
                        value=str(
                            self.cfg.get(key, "butane")
                        )
                    )

                    self.general_vars[key] = var

                    ttk.Combobox(
                        group,
                        textvariable=var,
                        values=(
                            "butane",
                            "electric",
                            "heat_pump"
                        ),
                        state="readonly",
                        width=18
                    ).grid(
                        row=index,
                        column=1,
                        sticky="ew",
                        padx=7,
                        pady=4
                    )

                # Controles numéricos.
                else:
                    ttk.Label(
                        group,
                        text=label
                    ).grid(
                        row=index,
                        column=0,
                        sticky="w",
                        padx=7,
                        pady=4
                    )

                    var = tk.StringVar(
                        value=str(self.cfg.get(key, ""))
                    )

                    self.general_vars[key] = var

                    ttk.Entry(
                        group,
                        textvariable=var,
                        width=16
                    ).grid(
                        row=index,
                        column=1,
                        sticky="ew",
                        padx=7,
                        pady=4
                    )

            return group

        # ------------------------------------------------------------------
        # GRUPO 1: CONDICIONES PSICROMÉTRICAS
        # ------------------------------------------------------------------

        add_group(
            "Condiciones iniciales y consignas",
            0,
            0,
            [
                ("pressure_pa", "Presión atmosférica (Pa)"),
                ("initial_temperature", "Temperatura inicial (°C)"),
                ("initial_rh", "Humedad relativa inicial (%)"),
                ("target_temperature", "Consigna de temperatura (°C)"),
                ("target_rh", "Consigna de humedad relativa (%)")
            ]
        )

        # ------------------------------------------------------------------
        # GRUPO 2: OCUPACIÓN Y GANANCIAS INTERNAS
        # ------------------------------------------------------------------

        add_group(
            "Ocupación y ganancias internas",
            0,
            1,
            [
                ("occupancy_start", "Hora de inicio de ocupación"),
                ("occupancy_end", "Hora de fin de ocupación"),
                ("moisture_per_person_g_h", "Humedad por persona (g/h)"),
                ("sensible_gain_per_person_w", "Ganancia sensible por persona (W)"),
                ("internal_gain_w", "Ganancia interna predeterminada (W)")
            ]
        )

        # ------------------------------------------------------------------
        # GRUPO 3: VENTILACIÓN
        # ------------------------------------------------------------------

        add_group(
            "Ventilación",
            1,
            0,
            [
                ("ventilation_max_ach", "ACH máximo adicional"),
                ("ventilation_control", "Habilitar ventilación por humedad")
            ]
        )

        # ------------------------------------------------------------------
        # GRUPO 4: VALORES PREDETERMINADOS DE LAS ESTANCIAS
        # ------------------------------------------------------------------

        add_group(
            "Valores predeterminados para nuevas estancias",
            1,
            1,
            [
                ("air_changes_h", "Renovaciones base (1/h)"),
                ("thermal_mass_j_m2k", "Masa térmica (J/m²K)")
            ]
        )

        # ------------------------------------------------------------------
        # GRUPO 5: EQUIPOS - VALORES GENERALES DE REFERENCIA
        # ------------------------------------------------------------------

        add_group(
            "Parámetros generales de equipos",
            2,
            0,
            [
                ("dehumidifier_l_day", "Capacidad deshumidificador (L/día)"),
                ("dehumidifier_power_kw", "Potencia deshumidificador (kW)"),
                ("dehumidifier_heat_factor", "Factor térmico deshumidificador"),
                ("heater_kw", "Potencia calefacción (kW térmicos)"),
                ("heating_type", "Tipo de calefacción"),
                ("heat_pump_cop", "COP bomba de calor"),
                ("combustion_moisture_g_kwh", "Humedad combustión (g/kWh)")
            ]
        )

        # ------------------------------------------------------------------
        # GRUPO 6: RADIACIÓN Y CONDENSACIÓN
        # ------------------------------------------------------------------

        add_group(
            "Radiación solar e indicador superficial",
            2,
            1,
            [
                ("solar_enabled", "Habilitar ganancias solares"),
                ("solar_factor", "Factor solar"),
                ("surface_factor", "Factor superficial fRsi")
            ]
        )

        ttk.Label(
            inner,
            text=(
                "Los parámetros de equipos de esta pestaña son valores "
                "generales de referencia. La disponibilidad real de cada "
                "equipo se establece individualmente en la pestaña Estancias."
            ),
            wraplength=900
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=10,
            pady=12
        )
    
    # -----------------------------------------------------------------------
    # PESTAÑA DE SIMULACION
    # -----------------------------------------------------------------------

    def _build_sim_tab(self):
        frame = self.tab_sim

        # ------------------------------------------------------------------
        # SELECCIÓN DEL ÁMBITO DE SIMULACIÓN
        # ------------------------------------------------------------------

        top = ttk.LabelFrame(
            frame,
            text="Ámbito de simulación"
        )
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(
            top,
            text="Estancia a simular"
        ).pack(side="left", padx=8, pady=8)

        self.room_choice = tk.StringVar(
            value="TODA LA VIVIENDA"
        )

        self.room_combo = ttk.Combobox(
            top,
            textvariable=self.room_choice,
            width=30,
            state="readonly"
        )
        self.room_combo.pack(side="left", padx=8, pady=8)

        ttk.Label(
            top,
            text="Los parámetros generales se configuran en la pestaña correspondiente."
        ).pack(side="left", padx=12, pady=8)

        # ------------------------------------------------------------------
        # BOTONERA
        # ------------------------------------------------------------------

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", padx=8, pady=5)

        ttk.Button(
            buttons,
            text="Simular 24 h",
            command=self._run
        ).pack(side="left", padx=4)

        ttk.Button(
            buttons,
            text="Guardar configuración",
            command=self._save
        ).pack(side="left", padx=4)

        ttk.Button(
            buttons,
            text="Cargar configuración",
            command=self._load
        ).pack(side="left", padx=4)

        ttk.Button(
            buttons,
            text="Exportar resultados CSV",
            command=self._export_csv
        ).pack(side="left", padx=4)

        # ------------------------------------------------------------------
        # RESULTADOS TEXTUALES
        # ------------------------------------------------------------------

        result_frame = ttk.LabelFrame(
            frame,
            text="Resultados"
        )
        result_frame.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=5
        )

        self.summary = tk.Text(
            result_frame,
            height=14,
            width=140,
            wrap="none",
            font=("Consolas", 9)
        )

        # Barra vertical.
        scroll_y = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.summary.yview
        )

        # Barra horizontal.
        scroll_x = ttk.Scrollbar(
            result_frame,
            orient="horizontal",
            command=self.summary.xview
        )

        self.summary.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )

        self.summary.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(4, 0),
            pady=(4, 0)
        )

        scroll_y.grid(
            row=0,
            column=1,
            sticky="ns",
            padx=(0, 4),
            pady=(4, 0)
        )

        scroll_x.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=(0, 4)
        )

        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.summary.insert(
            "end",
            "Configura los parámetros y pulsa «Simular 24 h».\n"
        )

        # ------------------------------------------------------------------
        # GRÁFICAS
        # ------------------------------------------------------------------

        self.plot_frame = ttk.Frame(frame)
        self.plot_frame.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=5
        )

    # -----------------------------------------------------------------------
    # PESTAÑA DE ESTANCIAS
    # -----------------------------------------------------------------------
    def _build_rooms_tab(self):
        frame = self.tab_rooms

        # ------------------------------------------------------------------
        # NAVEGACIÓN ENTRE ESTANCIAS
        # ------------------------------------------------------------------

        nav = ttk.Frame(frame)
        nav.pack(fill="x", padx=8, pady=6)

        ttk.Button(
            nav,
            text="◀ Anterior",
            command=self._prev_room
        ).pack(side="left", padx=4)

        self.room_label_var = tk.StringVar(value="")

        ttk.Label(
            nav,
            textvariable=self.room_label_var,
            font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=20)

        ttk.Button(
            nav,
            text="Siguiente ▶",
            command=self._next_room
        ).pack(side="left", padx=4)

        # ------------------------------------------------------------------
        # FORMULARIO DESPLAZABLE
        # ------------------------------------------------------------------

        form_container = ttk.Frame(frame)
        form_container.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=6
        )

        canvas = tk.Canvas(
            form_container,
            highlightthickness=0
        )

        scroll = ttk.Scrollbar(
            form_container,
            orient="vertical",
            command=canvas.yview
        )

        inner = ttk.Frame(canvas)

        window_id = canvas.create_window(
            (0, 0),
            window=inner,
            anchor="nw"
        )

        canvas.configure(yscrollcommand=scroll.set)

        inner.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window_id,
                width=event.width
            )
        )

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._room_form_inner = inner

        # ------------------------------------------------------------------
        # PARÁMETROS DE LA ESTANCIA
        # ------------------------------------------------------------------

        self._room_form_fields = [
            ("Nombre", "name", str),
            ("Altura (m)", "height", float),
            ("Superficie suelo (m²)", "floor_area", float),

            ("Ventanas (m²)", "window_area", float),
            ("U ventanas (W/m²K)", "window_u", float),

            ("Muros exteriores (m²)", "wall_area", float),
            ("U muros (W/m²K)", "wall_u", float),

            ("Cubierta exterior (m²)", "roof_area", float),
            ("U cubierta (W/m²K)", "roof_u", float),

            ("Suelo expuesto (m²)", "floor_exposed_area", float),
            ("U suelo (W/m²K)", "floor_u", float),

            ("Renovaciones base (1/h)", "air_changes_h", float),
            ("Masa térmica (J/m²K)", "thermal_mass_j_m2k", float),

            ("Personas habituales", "people", int),
            ("Ganancia interna (W)", "internal_gain_w", float),

            ("Deshumidificador (L/día)", "dehumidifier_l_day", float),
            ("Potencia deshumidificador (kW)", "dehumidifier_power_kw", float),

            ("Calefacción (kW térmicos)", "heater_kw", float),

            ("Área efectiva de apertura (m²)", "window_opening_area_m2", float),
            ("Factor exposición al viento", "wind_factor", float),
            ("Coeficiente descarga ventana", "window_discharge_coefficient", float)
        ]

        self.room_form_vars = {}

        for i, (label, key, _typ) in enumerate(
            self._room_form_fields
        ):

            ttk.Label(
                inner,
                text=label
            ).grid(
                row=i,
                column=0,
                sticky="w",
                padx=8,
                pady=3
            )

            var = tk.StringVar()
            self.room_form_vars[key] = var

            ttk.Entry(
                inner,
                textvariable=var,
                width=24
            ).grid(
                row=i,
                column=1,
                padx=8,
                pady=3
            )

        # ------------------------------------------------------------------
        # EQUIPOS INSTALADOS EN LA ESTANCIA
        # ------------------------------------------------------------------

        row = len(self._room_form_fields)

        equipment_frame = ttk.LabelFrame(
            inner,
            text="Equipos instalados en esta estancia"
        )

        equipment_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=8
        )

        self.room_heater_enabled_var = tk.BooleanVar(
            value=False
        )

        ttk.Checkbutton(
            equipment_frame,
            text="Calefacción disponible en esta estancia",
            variable=self.room_heater_enabled_var
        ).pack(
            anchor="w",
            padx=8,
            pady=4
        )

        self.room_dehumidifier_enabled_var = tk.BooleanVar(
            value=False
        )

        ttk.Checkbutton(
            equipment_frame,
            text="Deshumidificador disponible en esta estancia",
            variable=self.room_dehumidifier_enabled_var
        ).pack(
            anchor="w",
            padx=8,
            pady=4
        )

        ttk.Label(
            equipment_frame,
            text=(
                "Los equipos desmarcados no intervienen en la simulación, "
                "aunque tengan una capacidad o potencia indicada."
            ),
            wraplength=600
        ).pack(
            anchor="w",
            padx=8,
            pady=4
        )

        row += 1

        # ------------------------------------------------------------------
        # TIPO DE CALEFACCIÓN
        # ------------------------------------------------------------------

        ttk.Label(
            inner,
            text="Tipo de calefacción"
        ).grid(
            row=row,
            column=0,
            sticky="w",
            padx=8,
            pady=3
        )

        self.room_heating_type_var = tk.StringVar(
            value=""
        )

        ttk.Combobox(
            inner,
            textvariable=self.room_heating_type_var,
            values=(
                "",
                "butane",
                "electric",
                "heat_pump"
            ),
            state="readonly",
            width=21
        ).grid(
            row=row,
            column=1,
            padx=8,
            pady=3
        )

        row += 1

        # ------------------------------------------------------------------
        # VENTANAS
        # ------------------------------------------------------------------

        self.room_windows_open_var = tk.BooleanVar(
            value=False
        )

        ttk.Checkbutton(
            inner,
            text="Ventanas abiertas",
            variable=self.room_windows_open_var
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=5
        )

        row += 1

        ttk.Label(
            inner,
            text="Caudal manual ventana (m³/h, opcional)"
        ).grid(
            row=row,
            column=0,
            sticky="w",
            padx=8,
            pady=3
        )

        self.room_manual_flow_var = tk.StringVar()

        ttk.Entry(
            inner,
            textvariable=self.room_manual_flow_var,
            width=24
        ).grid(
            row=row,
            column=1,
            padx=8,
            pady=3
        )

        row += 1

        # ------------------------------------------------------------------
        # BOTONERA
        # ------------------------------------------------------------------

        buttons = ttk.Frame(inner)

        buttons.grid(
            row=row,
            column=0,
            columnspan=2,
            pady=10,
            sticky="w"
        )

        ttk.Button(
            buttons,
            text="Guardar cambios",
            command=self._save_room_form
        ).pack(side="left", padx=4)

        ttk.Button(
            buttons,
            text="Añadir estancia",
            command=self._add_room
        ).pack(side="left", padx=4)

        ttk.Button(
            buttons,
            text="Eliminar estancia",
            command=self._delete_room
        ).pack(side="left", padx=4)

        self._current_room_index = 0
    
    
    def _refresh_rooms(self):
        """Actualiza el combo de ámbitos y recarga el formulario."""
        self.room_combo["values"] = (
            ["TODA LA VIVIENDA"] +
            [r.get("name", "") for r in self.cfg.get("rooms", [])]
        )
        if self.room_choice.get() not in self.room_combo["values"]:
            self.room_choice.set("TODA LA VIVIENDA")
        if hasattr(self, "room_form_vars"):
            self._load_room_form()
    
    
    def _load_room_form(self):
        rooms = self.cfg.get("rooms", [])

        if not rooms:
            return

        self._current_room_index = max(
            0,
            min(
                self._current_room_index,
                len(rooms) - 1
            )
        )

        room = rooms[self._current_room_index]

        self.room_label_var.set(
            "Estancia %d de %d: %s" % (
                self._current_room_index + 1,
                len(rooms),
                room.get("name", "")
            )
        )

        # Campos numéricos y de texto.
        for key, var in self.room_form_vars.items():

            value = room.get(key, "")

            if value is None:
                value = ""

            var.set(str(value))

        # Disponibilidad de equipos.
        self.room_heater_enabled_var.set(
            bool(room.get("heater_enabled", False))
        )

        self.room_dehumidifier_enabled_var.set(
            bool(room.get("dehumidifier_enabled", False))
        )

        # Tipo de calefacción.
        self.room_heating_type_var.set(
            room.get("heating_type", "")
        )

        # Ventanas.
        self.room_windows_open_var.set(
            bool(room.get("windows_open", False))
        )

        manual = room.get("window_airflow_m3_h")

        self.room_manual_flow_var.set(
            "" if manual is None else str(manual)
        )
    
    
    def _collect_room_form(self):
        """
        Lee, valida y devuelve el diccionario de configuración
        correspondiente a la estancia actualmente seleccionada.
        """

        try:
            data = {}

            types = {
                key: typ
                for (_, key, typ) in self._room_form_fields
            }

            for key, var in self.room_form_vars.items():

                typ = types[key]
                value = var.get()

                if typ is str:
                    data[key] = value.strip()
                else:
                    data[key] = typ(
                        value.replace(",", ".")
                    )

            # Disponibilidad efectiva de equipos.
            data["heater_enabled"] = bool(
                self.room_heater_enabled_var.get()
            )

            data["dehumidifier_enabled"] = bool(
                self.room_dehumidifier_enabled_var.get()
            )

            # Tipo de calefacción.
            heating_type = self.room_heating_type_var.get().strip()

            if heating_type:
                data["heating_type"] = heating_type

            # Ventanas.
            data["windows_open"] = bool(
                self.room_windows_open_var.get()
            )

            flow = self.room_manual_flow_var.get().strip()

            data["window_airflow_m3_h"] = (
                self._to_float(flow)
                if flow else None
            )

            if not data["name"]:
                raise ValueError(
                    "El nombre no puede estar vacío."
                )

            # Nombres únicos.
            for idx, existing in enumerate(
                self.cfg.get("rooms", [])
            ):

                if idx == self._current_room_index:
                    continue

                if (
                    existing.get("name", "").strip().lower()
                    == data["name"].lower()
                ):
                    raise ValueError(
                        "Ya existe una estancia con ese nombre."
                    )

            # Geometría.
            for key in ("height", "floor_area"):

                if data[key] <= 0:
                    raise ValueError(
                        "%s debe ser positivo." % key
                    )

            # Parámetros no negativos.
            non_negative = (
                "window_area",
                "window_u",
                "wall_area",
                "wall_u",
                "roof_area",
                "roof_u",
                "floor_exposed_area",
                "floor_u",
                "air_changes_h",
                "thermal_mass_j_m2k",
                "people",
                "internal_gain_w",
                "dehumidifier_l_day",
                "dehumidifier_power_kw",
                "heater_kw",
                "window_opening_area_m2"
            )

            for key in non_negative:

                if data.get(key, 0) < 0:
                    raise ValueError(
                        "%s no puede ser negativo." % key
                    )

            if not 0 <= data["wind_factor"] <= 1:
                raise ValueError(
                    "El factor de viento debe estar entre 0 y 1."
                )

            if not 0 < data["window_discharge_coefficient"] <= 1:
                raise ValueError(
                    "El coeficiente de descarga debe estar entre 0 y 1."
                )

            if (
                data["windows_open"]
                and data["window_opening_area_m2"] <= 0
                and data["window_airflow_m3_h"] is None
            ):
                raise ValueError(
                    "Si las ventanas están abiertas, indica el área "
                    "efectiva de apertura o un caudal manual."
                )

            if data.get("heating_type") not in (
                None,
                "butane",
                "electric",
                "heat_pump"
            ):
                raise ValueError(
                    "El tipo de calefacción no es válido."
                )

            return data

        except Exception as exc:

            messagebox.showerror(
                "Datos de estancia",
                str(exc)
            )

            return None
    
    
    def _commit_room_form(self):
        """Valida y guarda el formulario en la estancia actual."""
        data = self._collect_room_form()
        if data is None:
            return False
        old_name = self.cfg["rooms"][self._current_room_index].get("name")
        self.cfg["rooms"][self._current_room_index] = data
        new_name = data["name"]
        if old_name != new_name:
            for conn in self.cfg.get("connections", []):
                if conn.get("room_a") == old_name:
                    conn["room_a"] = new_name
                if conn.get("room_b") == old_name:
                    conn["room_b"] = new_name
            self._refresh_connections()
        return True
    
    
    def _save_room_form(self):
        if self._commit_room_form():
            self._load_room_form()
            self._refresh_rooms()
            messagebox.showinfo("Estancia", "Cambios guardados.")
    
    
    def _next_room(self):
        if self._current_room_index >= len(self.cfg["rooms"]) - 1:
            return
        if not self._commit_room_form():
            return
        self._current_room_index += 1
        self._load_room_form()
    
    
    def _prev_room(self):
        if self._current_room_index <= 0:
            return
        if not self._commit_room_form():
            return
        self._current_room_index -= 1
        self._load_room_form()
    
    
    def _add_room(self):
        new_room = {
            "name": "NUEVA_%d" % (
                len(self.cfg["rooms"]) + 1
            ),

            "height": 2.6,
            "floor_area": 15.0,

            "window_area": 0.0,
            "window_u": 2.4,

            "wall_area": 20.0,
            "wall_u": 1.1,

            "roof_area": 0.0,
            "roof_u": 0.85,

            "floor_exposed_area": 0.0,
            "floor_u": 1.6,

            "air_changes_h": self.cfg.get(
                "air_changes_h",
                0.35
            ),

            "thermal_mass_j_m2k": self.cfg.get(
                "thermal_mass_j_m2k",
                100000.0
            ),

            "people": 0,
            "internal_gain_w": 0.0,

            # No se presupone la existencia de equipos.
            "heater_enabled": False,
            "heater_kw": 0.0,
            "heating_type": self.cfg.get(
                "heating_type",
                "butane"
            ),

            "dehumidifier_enabled": False,
            "dehumidifier_l_day": 0.0,
            "dehumidifier_power_kw": 0.0,

            # Ventanas.
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60
        }

        self.cfg["rooms"].append(new_room)

        self._current_room_index = (
            len(self.cfg["rooms"]) - 1
        )

        self._load_room_form()
        self._refresh_rooms()
    
    
    def _delete_room(self):
        if len(self.cfg["rooms"]) <= 1:
            messagebox.showwarning(
                "Estancias", "Debe quedar al menos una estancia.")
            return
        room_name = self.cfg["rooms"][self._current_room_index].get("name")
        if not messagebox.askyesno(
                "Eliminar", "¿Eliminar la estancia '%s'?" % room_name):
            return
        del self.cfg["rooms"][self._current_room_index]
        self.cfg["connections"] = [
            c for c in self.cfg.get("connections", [])
            if c.get("room_a") != room_name and c.get("room_b") != room_name
        ]
        self._current_room_index = max(0, self._current_room_index - 1)
        self._load_room_form()
        self._refresh_connections()
        self._refresh_rooms()
        
    # -----------------------------------------------------------------------
    # PESTAÑA DE CONEXIONES
    # -----------------------------------------------------------------------

    def _build_connections_tab(self):
        frame = self.tab_connections

        cols = (
            "room_a",
            "room_b",
            "type",
            "ventilation_transfer_factor",
            "airflow_m3_h"
        )

        self.connection_tree = ttk.Treeview(
            frame,
            columns=cols,
            show="headings",
            height=15
        )

        headings = {
            "room_a": "Estancia A",
            "room_b": "Estancia B",
            "type": "Tipo de conexión",
            "ventilation_transfer_factor": "Factor transferencia",
            "airflow_m3_h": "Caudal personalizado m³/h"
        }

        widths = {
            "room_a": 180,
            "room_b": 180,
            "type": 140,
            "ventilation_transfer_factor": 160,
            "airflow_m3_h": 190
        }

        for col in cols:
            self.connection_tree.heading(
                col,
                text=headings[col]
            )

            self.connection_tree.column(
                col,
                width=widths[col],
                anchor="center"
            )

        self.connection_tree.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=8, pady=5)

        ttk.Button(
            btns,
            text="Añadir conexión",
            command=self._add_connection
        ).pack(side="left", padx=3)

        ttk.Button(
            btns,
            text="Editar conexión",
            command=self._edit_connection
        ).pack(side="left", padx=3)

        ttk.Button(
            btns,
            text="Eliminar conexión",
            command=self._delete_connection
        ).pack(side="left", padx=3)

        note = (
            "Tipos disponibles: open (abierta), ajar (entreabierta), "
            "closed_gap (cerrada con holgura) y custom (caudal personalizado). "
            "El factor de transferencia de ventilación es un coeficiente "
            "empírico entre 0 y 1 que atenúa el intercambio inducido por "
            "la ventilación exterior. No representa un caudal medido."
        )

        ttk.Label(
            frame,
            text=note,
            wraplength=1100
        ).pack(anchor="w", padx=10, pady=6)

    def _refresh_connections(self):
        for item in self.connection_tree.get_children():
            self.connection_tree.delete(item)

        for idx, connection in enumerate(
            self.cfg.get("connections", [])
        ):
            self.connection_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    connection.get("room_a", ""),
                    connection.get("room_b", ""),
                    connection.get("type", ""),
                    connection.get("ventilation_transfer_factor", 0.5),
                    connection.get(
                        "airflow_m3_h",
                        connection.get("flow_m3_h", "")
                    )
                )
            )

    def _connection_dialog(self, connection=None):
        original = copy.deepcopy(connection) if connection else {
            "room_a": "",
            "room_b": "",
            "type": "open",
            "ventilation_transfer_factor": 0.5,
            "airflow_m3_h": None
        }

        room_names = [
            room.get("name", "")
            for room in self.cfg.get("rooms", [])
        ]

        if len(room_names) < 2:
            messagebox.showwarning(
                "Conexiones",
                "Se necesitan al menos dos estancias."
            )
            return None

        win = tk.Toplevel(self.root)
        win.title("Configuración de conexión")
        win.resizable(False, False)

        ttk.Label(win, text="Estancia A").grid(
            row=0, column=0, padx=8, pady=6, sticky="w"
        )

        var_a = tk.StringVar(
            value=original.get("room_a", room_names[0])
        )

        combo_a = ttk.Combobox(
            win,
            textvariable=var_a,
            values=room_names,
            state="readonly",
            width=25
        )
        combo_a.grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(win, text="Estancia B").grid(
            row=1, column=0, padx=8, pady=6, sticky="w"
        )

        default_b = room_names[1] if len(room_names) > 1 else room_names[0]

        var_b = tk.StringVar(
            value=original.get("room_b", default_b)
        )

        combo_b = ttk.Combobox(
            win,
            textvariable=var_b,
            values=room_names,
            state="readonly",
            width=25
        )
        combo_b.grid(row=1, column=1, padx=8, pady=6)

        ttk.Label(win, text="Tipo").grid(
            row=2, column=0, padx=8, pady=6, sticky="w"
        )

        var_type = tk.StringVar(
            value=original.get("type", "open")
        )

        ttk.Combobox(
            win,
            textvariable=var_type,
            values=("open", "ajar", "closed_gap", "custom"),
            state="readonly",
            width=25
        ).grid(row=2, column=1, padx=8, pady=6)

        ttk.Label(
            win,
            text="Factor transferencia ventilación (0-1)"
        ).grid(row=3, column=0, padx=8, pady=6, sticky="w")

        var_factor = tk.StringVar(
            value=str(original.get("ventilation_transfer_factor", 0.5))
        )

        ttk.Entry(
            win,
            textvariable=var_factor,
            width=28
        ).grid(row=3, column=1, padx=8, pady=6)

        ttk.Label(
            win,
            text="Caudal personalizado (m³/h)"
        ).grid(row=4, column=0, padx=8, pady=6, sticky="w")

        custom_flow = original.get(
            "airflow_m3_h",
            original.get("flow_m3_h", "")
        )

        var_flow = tk.StringVar(
            value="" if custom_flow is None else str(custom_flow)
        )

        ttk.Entry(
            win,
            textvariable=var_flow,
            width=28
        ).grid(row=4, column=1, padx=8, pady=6)

        ttk.Label(
            win,
            text=(
                "El caudal personalizado solo se utiliza cuando el tipo "
                "de conexión es custom."
            ),
            wraplength=350
        ).grid(row=5, column=0, columnspan=2, padx=8, pady=5)

        result = {"connection": None}

        def accept():
            try:
                room_a = var_a.get().strip()
                room_b = var_b.get().strip()
                connection_type = var_type.get()

                if not room_a or not room_b:
                    raise ValueError("Debes seleccionar ambas estancias.")

                if room_a == room_b:
                    raise ValueError(
                        "Una conexión debe unir dos estancias diferentes."
                    )

                factor = self._to_float(var_factor.get())

                if not 0 <= factor <= 1:
                    raise ValueError(
                        "El factor de transferencia debe estar entre 0 y 1."
                    )

                flow = None

                if var_flow.get().strip():
                    flow = self._to_float(var_flow.get())


                    if flow < 0:
                        raise ValueError(
                            "El caudal personalizado no puede ser negativo."
                        )

                if connection_type == "custom" and flow is None:
                    raise ValueError(
                        "Debes indicar el caudal para una conexión custom."
                    )

                result["connection"] = {
                    "room_a": room_a,
                    "room_b": room_b,
                    "type": connection_type,
                    "ventilation_transfer_factor": factor,
                    "airflow_m3_h": flow
                }

                win.destroy()

            except Exception as exc:
                messagebox.showerror(
                    "Conexión",
                    str(exc),
                    parent=win
                )

        buttons = ttk.Frame(win)
        buttons.grid(row=6, column=0, columnspan=2, pady=8)

        ttk.Button(
            buttons,
            text="Aceptar",
            command=accept
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons,
            text="Cancelar",
            command=win.destroy
        ).pack(side="left", padx=5)

        win.transient(self.root)
        win.grab_set()
        self.root.wait_window(win)

        return result["connection"]

    def _add_connection(self):
        connection = self._connection_dialog()

        if connection:
            self.cfg.setdefault("connections", []).append(connection)
            self._refresh_connections()

    def _edit_connection(self):
        selected = self.connection_tree.selection()

        if not selected:
            messagebox.showwarning(
                "Conexiones",
                "Selecciona una conexión."
            )
            return

        idx = int(selected[0])

        connection = self._connection_dialog(
            self.cfg["connections"][idx]
        )

        if connection:
            self.cfg["connections"][idx] = connection
            self._refresh_connections()

    def _delete_connection(self):
        selected = self.connection_tree.selection()

        if not selected:
            return

        idx = int(selected[0])

        if messagebox.askyesno(
            "Eliminar conexión",
            "¿Eliminar la conexión seleccionada?"
        ):
            del self.cfg["connections"][idx]
            self._refresh_connections()

    # -----------------------------------------------------------------------
    # PESTAÑA DE PERFIL EXTERIOR
    # -----------------------------------------------------------------------

    def _build_weather_tab(self):
        frame = self.tab_weather

        cols = (
            "hour",
            "temp",
            "rh",
            "solar",
            "wind",
            "direction"
        )

        self.weather_tree = ttk.Treeview(
            frame,
            columns=cols,
            show="headings",
            height=20
        )

        headings = {
            "hour": "Hora",
            "temp": "T exterior °C",
            "rh": "HR exterior %",
            "solar": "Radiación W/m²",
            "wind": "Viento m/s",
            "direction": "Dirección °"
        }

        widths = {
            "hour": 75,
            "temp": 145,
            "rh": 145,
            "solar": 145,
            "wind": 130,
            "direction": 130
        }

        for col in cols:
            self.weather_tree.heading(
                col,
                text=headings[col]
            )

            self.weather_tree.column(
                col,
                width=widths[col],
                anchor="center"
            )

        self.weather_tree.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        ttk.Button(
            frame,
            text="Editar hora seleccionada",
            command=self._edit_weather
        ).pack(anchor="w", padx=8, pady=5)

        ttk.Label(
            frame,
            text=(
                "La velocidad del viento se expresa en m/s. "
                "La dirección se expresa en grados: 0° norte, "
                "90° este, 180° sur y 270° oeste."
            ),
            wraplength=1000
        ).pack(anchor="w", padx=10, pady=6)

    def _refresh_weather(self):
        for item in self.weather_tree.get_children():
            self.weather_tree.delete(item)

        for idx, row in enumerate(self.cfg.get("weather", [])):
            # Compatibilidad con perfiles meteorológicos antiguos:
            # [hora, temperatura, HR, radiación]
            wind = row[4] if len(row) > 4 else 0.0
            direction = row[5] if len(row) > 5 else 0.0

            self.weather_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    wind,
                    direction
                )
            )

    def _edit_weather(self):
        selected = self.weather_tree.selection()

        if not selected:
            messagebox.showwarning(
                "Perfil exterior",
                "Selecciona una hora."
            )
            return

        idx = int(selected[0])
        row = self.cfg["weather"][idx]

        values = [
            row[1],
            row[2],
            row[3],
            row[4] if len(row) > 4 else 0.0,
            row[5] if len(row) > 5 else 0.0
        ]

        labels = [
            "Temperatura exterior (°C)",
            "HR exterior (%)",
            "Radiación solar (W/m²)",
            "Velocidad viento (m/s)",
            "Dirección viento (°)"
        ]

        win = tk.Toplevel(self.root)
        win.title("Perfil exterior - hora %d" % idx)
        win.resizable(False, False)

        vars_ = []

        for i, (label, value) in enumerate(zip(labels, values)):
            ttk.Label(
                win,
                text=label
            ).grid(
                row=i,
                column=0,
                padx=8,
                pady=5,
                sticky="w"
            )

            var = tk.StringVar(value=str(value))
            vars_.append(var)

            ttk.Entry(
                win,
                textvariable=var,
                width=18
            ).grid(
                row=i,
                column=1,
                padx=8,
                pady=5
            )

        def accept():
            try:
                vals = [
                    self._to_float(var.get())
                    for var in vars_
                ]

                temp, rh, solar, wind, direction = vals

                if not 0 <= rh <= 100:
                    raise ValueError(
                        "La humedad relativa debe estar entre 0 y 100 %."
                    )

                if solar < 0:
                    raise ValueError(
                        "La radiación no puede ser negativa."
                    )

                if wind < 0:
                    raise ValueError(
                        "La velocidad del viento no puede ser negativa."
                    )

                if not 0 <= direction <= 360:
                    raise ValueError(
                        "La dirección del viento debe estar entre 0 y 360°."
                    )

                self.cfg["weather"][idx] = [
                    idx,
                    temp,
                    rh,
                    solar,
                    wind,
                    direction
                ]

                self._refresh_weather()
                win.destroy()

            except Exception as exc:
                messagebox.showerror(
                    "Perfil exterior",
                    str(exc),
                    parent=win
                )

        buttons = ttk.Frame(win)
        buttons.grid(
            row=len(labels),
            column=0,
            columnspan=2,
            pady=8
        )

        ttk.Button(
            buttons,
            text="Aceptar",
            command=accept
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons,
            text="Cancelar",
            command=win.destroy
        ).pack(side="left", padx=5)

        win.transient(self.root)
        win.grab_set()
        self.root.wait_window(win)
        

    # -----------------------------------------------------------------------
    # LECTURA DE CONFIGURACION GENERAL
    # -----------------------------------------------------------------------

    def _collect_main_fields(self):
        # Parámetros numéricos y de selección.
        for key, var in self.general_vars.items():

            value = var.get().strip()

            if key == "heating_type":
                self.cfg[key] = value

            elif key in (
                "occupancy_start",
                "occupancy_end"
            ):
                self.cfg[key] = self._to_int(value)

            else:
                self.cfg[key] = self._to_float(value)

        # Parámetros booleanos.
        for key, var in self.general_bool_vars.items():
            self.cfg[key] = bool(var.get())

        # Validación horaria.
        for key in ("occupancy_start", "occupancy_end"):
            if not 0 <= int(self.cfg[key]) <= 23:
                raise ValueError(
                    "%s debe estar comprendida entre 0 y 23."
                    % key
                )

    # -----------------------------------------------------------------------
    # SIMULACION
    # -----------------------------------------------------------------------

    def _run(self):
        try:
            # Guarda los cambios pendientes de la estancia actual.
            if not self._commit_room_form():
                return

            # Recoge la configuración general.
            self._collect_main_fields()

            validate_config(self.cfg)

            choice = self.room_choice.get()
            room_index = None

            if choice != "TODA LA VIVIENDA":
                room_index = next(
                    i for i, room in enumerate(self.cfg["rooms"])
                    if room["name"] == choice
                )

            self.last_simulation = simulate(
                self.cfg,
                room_index,
                24
            )

            self._show_results(
                self.last_simulation
            )

            self._plot(
                self.last_simulation
            )

        except Exception as exc:
            messagebox.showerror(
                "Error de simulación",
                str(exc)
            )

    # -----------------------------------------------------------------------
    # PRESENTACION DE RESULTADOS
    # -----------------------------------------------------------------------

    def _show_results(self, sim):
        rows = sim.get("results", [])

        if not rows:
            self.summary.delete("1.0", "end")
            self.summary.insert(
                "end",
                "La simulación no ha generado resultados."
            )
            return

        mean_t = sum(x["tin"] for x in rows) / len(rows)
        mean_rh = sum(x["rh"] for x in rows) / len(rows)

        cond_h = sum(
            1 for x in rows
            if x.get("condensation", False)
        )

        vent = sum(x.get("vent_min", 0) for x in rows)
        dehum = sum(x.get("dehum_min", 0) for x in rows)
        heat = sum(x.get("heat_min", 0) for x in rows)

        dehum_kg = sum(
            x.get("dehum_kg", 0)
            for x in rows
        )

        condensate_kg = sum(
            x.get("condensate_kg", 0)
            for x in rows
        )

        heater_kwh = sum(
            x.get("heater_kwh", 0)
            for x in rows
        )

        heater_kwh_th = sum(
            x.get("heater_kwh_th", 0)
            for x in rows
        )

        fuel_kg = sum(
            x.get("heater_butane_kg", 0)
            for x in rows
        )

        txt = (
            "RESULTADOS: %s\n" % sim.get("room", "Simulación") +
            "Volumen: %.1f m³ | UA: %.1f W/K | "
            "Capacidad térmica: %.2f MJ/K\n" %
            (
                sim.get("volume", 0),
                sim.get("ua", 0),
                sim.get("capacity", 0) / 1e6
            ) +
            "Temperatura media: %.1f °C | HR media: %.1f %%\n" %
            (mean_t, mean_rh) +
            "Horas con riesgo de condensación superficial: %d\n" %
            cond_h +
            "Ventilación adicional: %.0f min/día\n" % vent +
            "Deshumidificador: %.0f min/día | Agua extraída: %.2f L\n" %
            (dehum, dehum_kg) +
            "Condensación acumulada: %.3f kg\n" % condensate_kg +
            "Calefacción: %.0f min/día\n" % heat +
            "Energía térmica suministrada: %.2f kWh\n" %
            heater_kwh_th +
            "Energía consumida: %.2f kWh\n" % heater_kwh +
            "Combustible butano: %.3f kg\n" % fuel_kg +
            "Temperatura final: %.1f °C | HR final: %.1f %%\n\n" %
            (rows[-1]["tin"], rows[-1]["rh"])
        )

        txt += (
            "Hora  T ext  T int  HR int  Rocío  Superf.  "
            "Vent  Desh  Cal  Cond.\n"
        )

        for row in rows:
            txt += (
                "%02d   %5.1f  %5.1f  %6.1f  %5.1f  %6.1f  "
                "%4.0f  %4.0f  %4.0f  %5.3f\n"
                % (
                    row.get("hour", 0),
                    row.get("tout", 0),
                    row.get("tin", 0),
                    row.get("rh", 0),
                    row.get("dew", 0),
                    row.get("surface", 0),
                    row.get("vent_min", 0),
                    row.get("dehum_min", 0),
                    row.get("heat_min", 0),
                    row.get("condensate_kg", 0)
                )
            )

        # Información adicional por estancia, si la devuelve el motor.
        room_results = sim.get("room_results", {})

        if room_results:
            txt += "\nRESULTADOS POR ESTANCIA\n"

            for room_name, room_data in room_results.items():
                txt += (
                    "%s: T %.1f °C | HR %.1f %% | "
                    "Condensados %.3f kg\n"
                    % (
                        room_name,
                        room_data.get("tin", 0),
                        room_data.get("rh", 0),
                        room_data.get("condensate_kg", 0)
                    )
                )

        self.summary.delete("1.0", "end")
        self.summary.insert("end", txt)

    # -----------------------------------------------------------------------
    # GRAFICAS
    # -----------------------------------------------------------------------

    def _plot(self, sim):
        for child in self.plot_frame.winfo_children():
            child.destroy()

        try:
            import matplotlib
            matplotlib.use("TkAgg")

            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg
            )

            rows = sim.get("results", [])

            x = [
                row.get("hour", i)
                for i, row in enumerate(rows)
            ]

            fig = Figure(
                figsize=(9, 4.2),
                dpi=90
            )

            # Eje principal: temperaturas.
            ax = fig.add_subplot(111)

            ax.plot(
                x,
                [r.get("tin", 0) for r in rows],
                label="T interior"
            )

            ax.plot(
                x,
                [r.get("tout", 0) for r in rows],
                label="T exterior"
            )

            ax.plot(
                x,
                [r.get("dew", 0) for r in rows],
                label="Punto de rocío"
            )

            ax.plot(
                x,
                [r.get("surface", 0) for r in rows],
                label="Temperatura superficial"
            )

            ax.set_xlabel("Hora")
            ax.set_ylabel("Temperatura (°C)")
            ax.grid(True)

            # Segundo eje: humedad relativa interior.
            ax_rh = ax.twinx()

            ax_rh.plot(
                x,
                [r.get("rh", 0) for r in rows],
                linestyle="--",
                marker="o",
                markersize=3,
                label="HR interior"
            )

            ax_rh.set_ylabel("Humedad relativa (%)")
            ax_rh.set_ylim(0, 100)

            # Leyenda conjunta de ambos ejes.
            lines_1, labels_1 = ax.get_legend_handles_labels()
            lines_2, labels_2 = ax_rh.get_legend_handles_labels()

            ax.legend(
                lines_1 + lines_2,
                labels_1 + labels_2,
                loc="best"
            )

            canvas = FigureCanvasTkAgg(
                fig,
                master=self.plot_frame
            )

            canvas.draw()

            canvas.get_tk_widget().pack(
                fill="both",
                expand=True
            )

        except Exception as exc:
            ttk.Label(
                self.plot_frame,
                text="Gráfico no disponible: %s" % exc
            ).pack()

    # -----------------------------------------------------------------------
    # GUARDAR Y CARGAR CONFIGURACION
    # -----------------------------------------------------------------------

    def _save(self):
        try:
            # Guarda primero los cambios pendientes de la estancia.
            if not self._commit_room_form():
                return

            # Recoge la configuración general.
            self._collect_main_fields()

            validate_config(self.cfg)

            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[
                    ("Configuración JSON", "*.json")
                ],
                initialfile=CONFIG_FILE
            )

            if path:
                save_config(
                    self.cfg,
                    path
                )

                messagebox.showinfo(
                    "Configuración",
                    "Configuración guardada correctamente."
                )

        except Exception as exc:
            messagebox.showerror(
                "Error",
                str(exc)
            )

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Configuración JSON", "*.json")
            ]
        )

        if not path:
            return

        try:
            self.cfg = load_config(path)

            self._current_room_index = 0

            # Normalización y valores predeterminados.
            self._normalise_config()

            validate_config(self.cfg)

            # Actualiza los campos generales.
            for key, var in self.general_vars.items():
                var.set(
                    str(self.cfg.get(key, ""))
                )

            for key, var in self.general_bool_vars.items():
                var.set(
                    bool(self.cfg.get(key, False))
                )

            self.last_simulation = None

            # Limpia los resultados anteriores.
            self.summary.delete(
                "1.0",
                "end"
            )

            self.summary.insert(
                "end",
                "Configuración cargada. Ejecuta una simulación.\n"
            )

            # Limpia las gráficas anteriores.
            for child in self.plot_frame.winfo_children():
                child.destroy()

            # Actualiza todas las pestañas.
            self._refresh_all()

            self._load_room_form()

            messagebox.showinfo(
                "Configuración",
                "Configuración cargada correctamente."
            )

        except Exception as exc:
            messagebox.showerror(
                "Error de carga",
                str(exc)
            )

    # -----------------------------------------------------------------------
    # EXPORTACION CSV
    # -----------------------------------------------------------------------

    def _export_csv(self):
        if not self.last_simulation:
            messagebox.showwarning(
                "Exportar",
                "Primero ejecuta una simulación."
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV", "*.csv")
            ],
            initialfile="resultados_vivienda.csv"
        )

        if not path:
            return

        try:
            import csv

            rows = self.last_simulation.get("results", [])

            if not rows:
                raise ValueError(
                    "No hay resultados que exportar."
                )

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as f:

                writer = csv.DictWriter(
                    f,
                    fieldnames=list(rows[0].keys()),
                    delimiter=";"
                )

                writer.writeheader()
                writer.writerows(rows)

            messagebox.showinfo(
                "Exportar",
                "Resultados exportados correctamente."
            )

        except Exception as exc:
            messagebox.showerror(
                "Exportación",
                str(exc)
            )
            

# ---------------------------------------------------------------------------
# ARRANQUE DE LA APLICACION
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()