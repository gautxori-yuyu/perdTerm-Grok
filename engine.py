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
    ]
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
        
    @staticmethod
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
    """Transmitancia térmica global de los cerramientos exteriores, W/K."""
    return (
        float(room.get("window_area", 0.0)) *
        float(room.get("window_u", 0.0)) +
        float(room.get("wall_area", 0.0)) *
        float(room.get("wall_u", 0.0)) +
        float(room.get("roof_area", 0.0)) *
        float(room.get("roof_u", 0.0)) +
        float(room.get("floor_exposed_area", 0.0)) *
        float(room.get("floor_u", 0.0))
    )


def room_ua(room, ach_override=None):
    """UA total incluyendo transmisión y ventilación, W/K."""
    ach = (
        float(room.get("air_changes_h", 0.0))
        if ach_override is None else max(0.0, float(ach_override))
    )
    ua_vent = VENT_HEAT_W_PER_M3H_K * ach * room_geometry(room)
    return max(0.0, room_envelope_ua(room) + ua_vent)


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


# ---------------------------------------------------------------------------
# CONEXIONES ENTRE ESTANCIAS
# ---------------------------------------------------------------------------

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

def exchange_air_between_rooms(states, connections, rooms, pressure,
                               dt_s):
    """
    Calcula los intercambios de aire entre estancias mediante
    un modelo de parámetros concentrados.

    Cada estancia se considera un volumen de control homogéneo,
    caracterizado por una temperatura y una humedad específicas.

    Se conserva:
      - La masa total de aire seco intercambiada.
      - La masa total de vapor de agua intercambiada.
      - La energía total transportada por el aire húmedo.

    El intercambio se considera bidireccional y simétrico en masa
    de aire seco. Las transferencias se acumulan antes de modificar
    los estados, evitando dependencias del orden de las conexiones.

    El intercambio máximo acumulado de cada estancia queda limitado
    al 45 % de su masa de aire seco durante cada subpaso.
    """

    if dt_s <= 0:
        return

    # ---------------------------------------------------------------
    # 1. PREPARACIÓN DE LOS INTERCAMBIOS
    # ---------------------------------------------------------------

    exchanges = []

    requested_mass = {
        name: 0.0 for name in states
    }

    for connection in connections:

        name_a = connection.get("room_a")
        name_b = connection.get("room_b")

        if name_a not in states or name_b not in states:
            continue

        if name_a == name_b:
            continue

        state_a = states[name_a]
        state_b = states[name_b]

        room_a = rooms[name_a]
        room_b = rooms[name_b]

        # Caudal bidireccional equivalente.
        q_m3_h = connection_exchange_m3_h(
            connection,
            state_a,
            state_b,
            room_a,
            room_b,
            pressure
        )

        if q_m3_h <= 0:
            continue

        # Volumen intercambiado por sentido.
        exchanged_volume = (
            q_m3_h * dt_s / 3600.0
        )

        # Masa de aire seco correspondiente al volumen intercambiado
        # en cada estancia.
        mass_a = dry_air_mass(
            exchanged_volume,
            state_a["temperature"],
            state_a["w"],
            pressure
        )

        mass_b = dry_air_mass(
            exchanged_volume,
            state_b["temperature"],
            state_b["w"],
            pressure
        )

        # Se utiliza una masa común de intercambio.
        # Esto mantiene el balance de masa seca en cada estancia:
        # la masa que sale es igual a la que entra.
        exchanged_mass = (
            mass_a + mass_b
        ) / 2.0

        if exchanged_mass <= 0:
            continue

        exchanges.append({
            "room_a": name_a,
            "room_b": name_b,
            "mass": exchanged_mass
        })

        requested_mass[name_a] += exchanged_mass
        requested_mass[name_b] += exchanged_mass

    if not exchanges:
        return

    # ---------------------------------------------------------------
    # 2. LIMITACIÓN CONJUNTA POR ESTANCIA
    # ---------------------------------------------------------------

    # Evita que una estancia con muchas conexiones intercambie
    # una masa de aire superior a la disponible en el subpaso.

    scale = {}

    for name, state in states.items():

        available_mass = max(
            0.01,
            float(state["dry_air_kg"])
        )

        requested = requested_mass[name]

        maximum_exchange = 0.45 * available_mass

        if requested > maximum_exchange:

            scale[name] = (
                maximum_exchange / requested
            )

        else:

            scale[name] = 1.0

    # ---------------------------------------------------------------
    # 3. ESTADOS INSTANTÁNEOS
    # ---------------------------------------------------------------

    # Se toman instantáneas para que todas las transferencias
    # utilicen las condiciones existentes al inicio del intercambio.

    snapshots = {}

    for name, state in states.items():

        temperature = float(state["temperature"])
        humidity_ratio = float(state["w"])

        snapshots[name] = {
            "temperature": temperature,
            "w": humidity_ratio,
            "dry_air_kg": float(state["dry_air_kg"]),

            # Entalpía del aire húmedo en kJ/kg de aire seco.
            "enthalpy": (
                Psychrometrics.enthalpy_kj_kg(
                    temperature,
                    humidity_ratio
                )
            )
        }

    # ---------------------------------------------------------------
    # 4. ACUMULACIÓN DE TRANSFERENCIAS
    # ---------------------------------------------------------------

    moisture_delta = {
        name: 0.0 for name in states
    }

    energy_delta = {
        name: 0.0 for name in states
    }

    for exchange in exchanges:

        name_a = exchange["room_a"]
        name_b = exchange["room_b"]

        a = snapshots[name_a]
        b = snapshots[name_b]

        # Se aplica la limitación más restrictiva de las dos
        # estancias conectadas.
        exchanged_mass = (
            exchange["mass"] *
            min(scale[name_a], scale[name_b])
        )

        if exchanged_mass <= 0:
            continue

        # -----------------------------------------------------------
        # Balance de humedad
        # -----------------------------------------------------------

        # Masa de vapor que recibe A desde B, menos la que entrega.
        moisture_a = (
            exchanged_mass * (b["w"] - a["w"])
        )

        # Transferencia inversa para B.
        moisture_b = -moisture_a

        moisture_delta[name_a] += moisture_a
        moisture_delta[name_b] += moisture_b

        # -----------------------------------------------------------
        # Balance energético
        # -----------------------------------------------------------

        # Energía transportada por el aire húmedo.
        # La entalpía está expresada en kJ/kg de aire seco.

        energy_a = (
            exchanged_mass *
            (b["enthalpy"] - a["enthalpy"]) *
            1000.0
        )

        energy_b = -energy_a

        energy_delta[name_a] += energy_a
        energy_delta[name_b] += energy_b

    # ---------------------------------------------------------------
    # 5. APLICACIÓN SIMULTÁNEA DE LOS BALANCES
    # ---------------------------------------------------------------

    for name, state in states.items():

        dry_mass = max(
            0.01,
            float(state["dry_air_kg"])
        )

        # La masa de aire seco permanece constante porque
        # cada estancia recibe la misma masa que entrega.
        #
        # Actualización de humedad específica.
        state["w"] = max(
            0.0,
            float(state["w"]) +
            moisture_delta[name] / dry_mass
        )

        # Actualización de temperatura.
        #
        # La capacidad térmica incluye la capacidad efectiva
        # del aire y de la masa térmica asociada a la estancia.
        state["temperature"] += (
            energy_delta[name] /
            max(1.0, float(state["capacity"]))
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
    Integra un subpaso térmico e higrométrico de una estancia.

    Los equipos pueden configurarse individualmente por estancia.
    Cuando no existe un valor específico, se utiliza el valor global
    de la configuración.

    Incluye:
      - Ventilación exterior e intercambio de humedad.
      - Ocupación y ganancias internas.
      - Ganancias solares.
      - Deshumidificación y su aportación térmica.
      - Calefacción y consumo energético.
      - Humedad generada por combustión.
      - Condensación y recuperación de calor latente.

    Los contadores acumulados se mantienen en el estado de la estancia.
    """

    # ---------------------------------------------------------------
    # 1. CONDICIONES INICIALES
    # ---------------------------------------------------------------

    pressure = float(config["pressure_pa"])

    t = float(state["temperature"])
    w = float(state["w"])

    tout = float(weather["temperature"])
    rhout = float(weather["rh"])
    solar = float(weather["solar"])

    wout = psych.humidity_ratio(
        tout, rhout, pressure
    )

    volume = float(state["volume"])
    dry_mass = max(0.01, float(state["dry_air_kg"]))

    dt_h = dt_s / 3600.0

    target_temperature = float(
        config["target_temperature"]
    )

    target_rh = float(
        config["target_rh"]
    )

    # ---------------------------------------------------------------
    # 2. CONFIGURACIÓN DE EQUIPOS
    # ---------------------------------------------------------------

    heater_enabled = bool(
        resolve_room_param(
            room, config, "heater_enabled", True
        )
    )

    dehumidifier_enabled = bool(
        resolve_room_param(
            room, config, "dehumidifier_enabled", True
        )
    )

    heater_kw = max(
        0.0,
        float(resolve_room_param(
            room, config, "heater_kw", 0.0
        ))
    )

    heating_type = resolve_room_param(
        room, config, "heating_type", "butane"
    )

    dehumidifier_l_day = max(
        0.0,
        float(resolve_room_param(
            room, config, "dehumidifier_l_day", 0.0
        ))
    )

    dehumidifier_power_kw = max(
        0.0,
        float(resolve_room_param(
            room, config, "dehumidifier_power_kw", 0.0
        ))
    )

    cop = max(
        1.0,
        float(config.get("heat_pump_cop", 3.0))
    )

    internal_gain_w = max(
        0.0,
        float(resolve_room_param(
            room, config, "internal_gain_w", 0.0
        ))
    )

    # ---------------------------------------------------------------
    # 3. VENTILACIÓN EXTERIOR
    # ---------------------------------------------------------------

    ach_base = max(
        0.0,
        float(room.get("air_changes_h", 0.0))
    )

    # El caudal de ventana ya se calcula en simulate(), antes
    # del intercambio entre estancias.
    # No volver a calcularlo aquí.
    q_window = max(
        0.0,
        float(state.get("_window_airflow", 0.0))
    )

    ach_window = q_window / max(0.1, volume)

    w_target = psych.humidity_ratio(
        t, target_rh, pressure
    )

    ach_control = ventilation_control_ach(
        w,
        wout,
        w_target,
        ach_base + ach_window,
        float(config.get("ventilation_max_ach", 2.0)),
        bool(config.get("ventilation_control", True))
    )

    ach_total = ach_base + ach_window + ach_control

    # Renovación de humedad mediante una solución exponencial.
    if ach_total > 0.0:

        decay = math.exp(-ach_total * dt_h)

        w = wout + (w - wout) * decay

        state["ventilation_m3"] += (
            ach_total * volume * dt_h
        )

    # Se contabilizan minutos únicamente cuando existe
    # ventilación adicional controlada o apertura de ventanas.
    if ach_control > 0.0 or ach_window > 0.0:

        state["ventilation_minutes"] += dt_h * 60.0

    # ---------------------------------------------------------------
    # 4. OCUPACIÓN Y GANANCIAS INTERNAS
    # ---------------------------------------------------------------

    people = room_occupancy(
        room, config, hour
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
        people *
        moisture_per_person /
        1000.0 *
        dt_h
    )

    w += moisture_kg / dry_mass

    sensible_w = (
        people * sensible_gain_per_person +
        internal_gain_w
    )

    # ---------------------------------------------------------------
    # 5. GANANCIAS SOLARES
    # ---------------------------------------------------------------

    solar_w = 0.0

    if config.get("solar_enabled", True):

        solar_w = (
            max(0.0, solar) *
            max(0.0, float(room.get("window_area", 0.0))) *
            max(0.0, float(config.get("solar_factor", 0.55)))
        )

    # ---------------------------------------------------------------
    # 6. DESHUMIDIFICACIÓN
    # ---------------------------------------------------------------

    extracted_kg = 0.0
    dehum_heat_w = 0.0
    dehum_electric_kwh = 0.0

    if dehumidifier_enabled and dehumidifier_l_day > 0.0:

        rh = psych.relative_humidity(
            t, w, pressure
        )

        cap_kg_h = dehumidifier_capacity_kg_h(
            dehumidifier_l_day,
            t,
            rh
        )

        target_w = psych.humidity_ratio(
            t, target_rh, pressure
        )

        excess_kg = max(
            0.0,
            (w - target_w) * dry_mass
        )

        extracted_kg = min(
            excess_kg,
            cap_kg_h * dt_h
        )

        if extracted_kg > 0.0:

            w -= extracted_kg / dry_mass

            state["dehumidified_kg"] += extracted_kg

            # Tiempo efectivo de funcionamiento.
            dehum_minutes = (
                extracted_kg / cap_kg_h * 60.0
            )

            state["dehumidifier_minutes"] += dehum_minutes

            # Calor latente liberado por el agua extraída.
            latent_kwh = (
                extracted_kg * H_FG / 3600000.0
            )

            # Consumo eléctrico.
            dehum_electric_kwh = (
                dehumidifier_power_kw *
                dehum_minutes / 60.0
            )

            # El calor liberado por el condensador incluye
            # el calor latente recuperado y el trabajo eléctrico.
            dehum_heat_kwh = (
                latent_kwh + dehum_electric_kwh
            ) * float(
                config.get("dehumidifier_heat_factor", 1.0)
            )

            dehum_heat_w = (
                dehum_heat_kwh / dt_h * 1000.0
            )

    state["dehumidifier_kwh"] += dehum_electric_kwh

    # ---------------------------------------------------------------
    # 7. TRANSMISIÓN TÉRMICA Y VENTILACIÓN
    # ---------------------------------------------------------------

    ua = (
        float(state["ua_envelope"]) +
        VENT_HEAT_W_PER_M3H_K *
        ach_total *
        volume
    )

    gains_without_heating = (
        sensible_w +
        solar_w +
        dehum_heat_w
    )

    # Evolución térmica sin calefacción.
    t_free = exact_thermal_step(
        t,
        tout,
        ua,
        state["capacity"],
        gains_without_heating,
        dt_s
    )

    # ---------------------------------------------------------------
    # 8. CALEFACCIÓN
    # ---------------------------------------------------------------

    heater_w = 0.0

    if (
        heater_enabled and
        heater_kw > 0.0 and
        t_free < target_temperature
    ):

        if ua > 1e-9:

            decay = math.exp(
                -ua * dt_s / state["capacity"]
            )

            response = (
                1.0 - decay
            ) / ua

        else:

            response = (
                dt_s / state["capacity"]
            )

        required_w = max(
            0.0,
            (target_temperature - t_free) /
            max(1e-12, response)
        )

        heater_w = min(
            heater_kw * 1000.0,
            required_w
        )

    # Temperatura final del subpaso.
    t_new = exact_thermal_step(
        t,
        tout,
        ua,
        state["capacity"],
        gains_without_heating + heater_w,
        dt_s
    )

    # ---------------------------------------------------------------
    # 9. HUMEDAD GENERADA POR COMBUSTIÓN
    # ---------------------------------------------------------------

    combustion_g = 0.0

    if heating_type == "butane" and heater_w > 0.0:

        thermal_kwh = (
            heater_w * dt_s / 3600000.0
        )

        fuel_kwh = (
            thermal_kwh /
            max(0.1, heater_efficiency("butane"))
        )

        combustion_g = (
            fuel_kwh *
            float(config.get(
                "combustion_moisture_g_kwh", 75.0
            ))
        )

        w += (
            combustion_g / 1000.0
        ) / dry_mass

    # ---------------------------------------------------------------
    # 10. ACTUALIZACIÓN DEL ESTADO
    # ---------------------------------------------------------------

    state["temperature"] = t_new
    state["w"] = max(0.0, w)

    # Energía térmica suministrada por la calefacción.
    heater_kwh_th = (
        heater_w * dt_s / 3600000.0
    )

    # Energía consumida según el tipo de equipo.
    heater_kwh = heater_energy_kwh(
        heater_kwh_th,
        heating_type,
        cop
    )

    state["heater_kwh_th"] += heater_kwh_th
    state["heater_kwh"] += heater_kwh

    state["heater_butane_kg"] += heater_butane_kg(
        heater_kwh_th,
        heating_type
    )

    if heater_kw > 0.0 and heater_w > 0.0:

        state["heater_minutes"] += (
            60.0 * dt_h *
            heater_w / (heater_kw * 1000.0)
        )

    # ---------------------------------------------------------------
    # 11. CONDENSACIÓN Y CALOR LATENTE
    # ---------------------------------------------------------------

    update_dry_air_mass(
        state, pressure
    )

    condensate = apply_condensation(
        state, psych, pressure
    )

    if condensate > 0.0:

        latent_heat_j = (
            condensate * H_FG
        )

        state["temperature"] += (
            latent_heat_j /
            max(1.0, state["capacity"])
        )

    update_dry_air_mass(
        state, pressure
    )

    # ---------------------------------------------------------------
    # 12. RESULTADOS DEL SUBPASO
    # ---------------------------------------------------------------

    return {
        "people": people,
        "solar_w": solar_w,
        "ua": ua,
        "heater_w": heater_w,
        "dehum_heat_w": dehum_heat_w,
        "combustion_g": combustion_g,
        "ventilation_ach": ach_total,
        "heater_kw": heater_kw,
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
    """Construye el resultado horario de una estancia.

    Los consumos, caudales y minutos son el incremento de esa hora,
    no el total desde el inicio de la simulación. Los campos *_total
    conservan el acumulado.
    """
    pressure = float(config["pressure_pa"])

    t = state["temperature"]
    w = state["w"]

    rh = psych.relative_humidity(t, w, pressure)
    dew = psych.dew_point(t, w, pressure)

    tout = float(weather["temperature"])

    t_surface = (
        t -
        (t - tout) *
        (1.0 - float(config.get("surface_factor", 0.75)))
    )

    result = {
        "hour": hour,
        "tout": tout,
        "rhout": float(weather["rh"]),
        "solar": float(weather["solar"]),
        "tin": t,
        "rh": rh,
        "w_g_kg": w * 1000.0,
        "dew": dew,
        "surface": t_surface,
        "condensation": t_surface <= dew,
        "condensate_kg": state["condensate_hour_kg"],
        "condensate_total_kg": state["condensate_kg"],
        "dehum_kg": counter_delta(state, "dehumidified_kg"),
        "dehum_kg_total": state["dehumidified_kg"],
        "dehum_kwh": counter_delta(state, "dehumidifier_kwh"),
        "dehum_kwh_total": state["dehumidifier_kwh"],
        "heater_kwh": counter_delta(state, "heater_kwh"),
        "heater_kwh_total": state["heater_kwh"],
        "heater_kwh_th": counter_delta(state, "heater_kwh_th"),
        "heater_kwh_th_total": state["heater_kwh_th"],
        "heater_butane_kg": counter_delta(state, "heater_butane_kg"),
        "heater_butane_kg_total": state["heater_butane_kg"],
        "ventilation_m3": counter_delta(state, "ventilation_m3"),
        "ventilation_m3_total": state["ventilation_m3"],
        "vent_min": counter_delta(state, "ventilation_minutes"),
        "vent_min_total": state["ventilation_minutes"],
        "dehum_min": counter_delta(state, "dehumidifier_minutes"),
        "dehum_min_total": state["dehumidifier_minutes"],
        "heat_min": counter_delta(state, "heater_minutes"),
        "heat_min_total": state["heater_minutes"],
        "dry_air_kg": state["dry_air_kg"],
        "ua": hour_data["ua"],
        "capacity_mj_k": state["capacity"] / 1000000.0,
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
    Simula la evolución térmica e higrométrica de una vivienda.

    selected_room:
        None -> simula todas las estancias conectadas.
        int  -> simula exclusivamente la estancia indicada.

    hours:
        Número de horas a simular.

    substep_minutes:
        Resolución interna de integración. Por defecto, 5 minutos.

    Devuelve:
        {
            "room": etiqueta,
            "results": resultados horarios (modo estancia),
            "rooms": resultados por estancia,
            "ua": UA de referencia,
            "volume": volumen,
            "capacity": capacidad térmica
        }
    """
    psych = Psychrometrics()

    rooms_cfg = config["rooms"]

    if not rooms_cfg:
        raise ValueError("No hay estancias configuradas.")

    if len(config["weather"]) < 24:
        raise ValueError(
            "El perfil meteorológico debe contener 24 horas."
        )

    if substep_minutes <= 0:
        raise ValueError("El subpaso debe ser positivo.")

    # ---------------------------------------------------------------
    # SELECCION DE ESTANCIAS
    # ---------------------------------------------------------------

    if selected_room is None:
        selected_rooms = copy.deepcopy(rooms_cfg)
        room_label = "TODA LA VIVIENDA"
    else:
        if selected_room < 0 or selected_room >= len(rooms_cfg):
            raise ValueError("Índice de estancia no válido.")

        selected_rooms = [
            copy.deepcopy(rooms_cfg[selected_room])
        ]

        room_label = selected_rooms[0]["name"]

    room_map = {
        room["name"]: room for room in selected_rooms
    }

    room_names = set(room_map.keys())

    connections = normalize_connections(
        config, room_names
    )

    # ---------------------------------------------------------------
    # ESTADOS INICIALES
    # ---------------------------------------------------------------

    states = {}

    for room in selected_rooms:
        states[room["name"]] = create_room_state(
            room, config, psych
        )

    results_by_room = {
        room["name"]: [] for room in selected_rooms
    }

    # ---------------------------------------------------------------
    # INTEGRACION TEMPORAL
    # ---------------------------------------------------------------

    dt_s = substep_minutes * 60.0
    steps_per_hour = int(round(3600.0 / dt_s))

    if abs(steps_per_hour * dt_s - 3600.0) > 1e-6:
        raise ValueError(
            "El subpaso debe dividir exactamente una hora."
        )

    for hour in range(int(hours)):
        wx_row = config["weather"][hour % 24]
        weather = normalize_weather_row(wx_row)

        # Reinicio de acumuladores horarios.
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

        hour_data = {}

        for name in states:
            hour_data[name] = {
                "ua": 0.0,
                "solar_w": 0.0,
                "people": 0
            }

        # -----------------------------------------------------------
        # SUBPASOS
        # -----------------------------------------------------------

        for step in range(steps_per_hour):

            # El caudal de ventanas de esta hora tiene que existir
            # antes del intercambio entre estancias.
            for room in selected_rooms:
                states[room["name"]]["_window_airflow"] = (
                    window_airflow(room, weather)
                )

            # 1. Intercambio de aire entre estancias.
            exchange_air_between_rooms(
                states,
                connections,
                room_map,
                float(config["pressure_pa"]),
                dt_s
            )

            # 2. Evolución individual de cada estancia.
            for room in selected_rooms:
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

                hour_data[name]["ua"] += data["ua"]
                hour_data[name]["solar_w"] += data["solar_w"]
                hour_data[name]["people"] = data["people"]

        # -----------------------------------------------------------
        # RESULTADOS AL FINAL DE LA HORA
        # -----------------------------------------------------------

        # -----------------------------------------------------------
        # RESULTADOS AL FINAL DE LA HORA
        # -----------------------------------------------------------

        for room in selected_rooms:
            name = room["name"]

            # Se utiliza el valor medio de UA durante la hora.
            hour_data[name]["ua"] /= steps_per_hour
            hour_data[name]["solar_w"] /= steps_per_hour

            result = room_hour_result(
                room,
                states[name],
                config,
                psych,
                weather,
                hour,
                hour_data[name]
            )

            results_by_room[name].append(result)

    # ---------------------------------------------------------------
    # RESULTADO GLOBAL
    # ---------------------------------------------------------------

    total_volume = sum(
        state["volume"] for state in states.values()
    )

    total_capacity = sum(
        state["capacity"] for state in states.values()
    )

    total_ua = sum(
        state["ua_envelope"] for state in states.values()
    )

    room_summary = {}

    for name, rows in results_by_room.items():
        if not rows:
            continue
        last = rows[-1]
        room_summary[name] = {
            "tin": last["tin"],
            "rh": last["rh"],
            "condensate_kg": sum(
                row.get("condensate_kg", 0.0) for row in rows
            )
        }

    if selected_room is not None:
        name = selected_rooms[0]["name"]

        return {
            "room": room_label,
            "results": results_by_room[name],
            "rooms": results_by_room,
            "room_results": room_summary,
            "ua": total_ua,
            "volume": total_volume,
            "capacity": total_capacity
        }

    # Resultados agregados de vivienda:
    # se ponderan temperatura y humedad por la masa de aire seco
    # de cada estancia al final de esa hora.
    global_results = []

    for index in range(int(hours)):
        total_dry_mass = 0.0
        weighted_temperature = 0.0
        weighted_w = 0.0
        weighted_surface = 0.0

        room_rows = [
            results_by_room[name][index]
            for name in results_by_room
        ]

        for result in room_rows:
            mass = float(result.get("dry_air_kg", 0.0))
            total_dry_mass += mass
            weighted_temperature += result["tin"] * mass
            weighted_w += result["w_g_kg"] / 1000.0 * mass
            weighted_surface += result.get("surface", result["tin"]) * mass

        mean_t = weighted_temperature / max(0.01, total_dry_mass)
        mean_w = weighted_w / max(0.01, total_dry_mass)
        mean_surface = weighted_surface / max(0.01, total_dry_mass)

        mean_rh = psych.relative_humidity(
            mean_t, mean_w, config["pressure_pa"]
        )

        mean_dew = psych.dew_point(
            mean_t, mean_w, config["pressure_pa"]
        )

        def _sum_key(key):
            return sum(row.get(key, 0.0) for row in room_rows)

        global_results.append({
            "hour": index,
            "tin": mean_t,
            "rh": mean_rh,
            "w_g_kg": mean_w * 1000.0,
            "dew": mean_dew,
            "surface": mean_surface,
            "condensation": any(
                row.get("condensation", False) for row in room_rows
            ),
            "tout": room_rows[0]["tout"],
            "rhout": room_rows[0]["rhout"],
            "solar": room_rows[0]["solar"],
            "condensate_kg": _sum_key("condensate_kg"),
            "dehum_kg": _sum_key("dehum_kg"),
            "dehum_kwh": _sum_key("dehum_kwh"),
            "heater_kwh": _sum_key("heater_kwh"),
            "heater_kwh_th": _sum_key("heater_kwh_th"),
            "heater_butane_kg": _sum_key("heater_butane_kg"),
            "ventilation_m3": _sum_key("ventilation_m3"),
            "vent_min": _sum_key("vent_min"),
            "dehum_min": _sum_key("dehum_min"),
            "heat_min": _sum_key("heat_min")
        })

    return {
        "room": room_label,
        "results": global_results,
        "rooms": results_by_room,
        "room_results": room_summary,
        "ua": total_ua,
        "volume": total_volume,
        "capacity": total_capacity
    }


# ---------------------------------------------------------------------------
# CONFIGURACION Y VALIDACION
# ---------------------------------------------------------------------------

def _ensure_room_defaults(rooms):
    """
    Completa los parámetros predeterminados de las estancias.

    Mantiene la compatibilidad con configuraciones JSON anteriores.
    """

    for room in rooms:

        room.setdefault("windows_open", False)
        room.setdefault("window_opening_area_m2", 0.0)
        room.setdefault("window_airflow_m3_h", None)
        room.setdefault("wind_factor", 0.60)
        room.setdefault("window_discharge_coefficient", 0.60)

        room.setdefault("internal_gain_w", 0.0)

        room.setdefault("dehumidifier_l_day", 12.0)
        room.setdefault("dehumidifier_power_kw", 0.22)
        room.setdefault("dehumidifier_enabled", True)

        room.setdefault("heater_kw", 3.8)
        room.setdefault("heating_type", "butane")
        room.setdefault("heater_enabled", True)
        
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
