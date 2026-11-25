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
    ua_vent = 0.33 * ach * room_geometry(room)
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

def dehumidifier_capacity_kg_h(config, t_c, rh):
    """Capacidad horaria aproximada del deshumidificador."""
    nominal = max(
        0.0, float(config.get("dehumidifier_l_day", 0.0))
    ) / 24.0

    temp_factor = clamp((t_c + 5.0) / 25.0, 0.20, 1.0)
    rh_factor = clamp((rh - 35.0) / 45.0, 0.0, 1.0)

    return nominal * temp_factor * rh_factor


def heater_efficiency(config):
    """Rendimiento térmico del sistema de calefacción."""
    heating_type = config.get("heating_type", "butane")

    if heating_type == "heat_pump":
        return max(1.0, float(config.get("heat_pump_cop", 3.0)))

    if heating_type == "electric":
        return 1.0

    return 0.90


def heater_energy_kwh(thermal_kwh, config):
    """Energía consumida por el equipo, kWh."""
    heating_type = config.get("heating_type", "butane")

    if heating_type == "heat_pump":
        return thermal_kwh / max(
            1.0, float(config.get("heat_pump_cop", 3.0))
        )

    if heating_type == "electric":
        return thermal_kwh

    return thermal_kwh / max(0.1, heater_efficiency(config))


def heater_butane_kg(thermal_kwh, config):
    """Consumo de butano en kg."""
    if config.get("heating_type") != "butane":
        return 0.0

    fuel_kwh = heater_energy_kwh(thermal_kwh, config)

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
    """Número de personas presentes en la estancia."""
    start = int(config.get("occupancy_start", 8))
    end = int(config.get("occupancy_end", 23))

    if not (start <= hour < end):
        return 0

    return max(0, int(room.get("people", 0)))


# ---------------------------------------------------------------------------
# BALANCES DE MASA Y ENERGIA
# ---------------------------------------------------------------------------

def exchange_air_between_rooms(states, connections, rooms, pressure,
                               dt_s):
    """
    Intercambio de aire entre estancias.

    Se realizan dos contribuciones:
      - Intercambio bidireccional por flotabilidad.
      - Intercambio bidireccional inducido por ventilación.

    La transferencia de humedad se calcula con la masa de aire seco
    intercambiada. La transferencia térmica utiliza el calor específico
    del aire húmedo.

    Las transferencias se acumulan antes de modificar los estados,
    evitando que el orden de las conexiones altere el resultado.
    """
    moisture_delta = dict((name, 0.0) for name in states)
    energy_delta = dict((name, 0.0) for name in states)

    for connection in connections:
        name_a = connection.get("room_a")
        name_b = connection.get("room_b")

        if name_a not in states or name_b not in states:
            continue

        a = states[name_a]
        b = states[name_b]

        room_a = rooms[name_a]
        room_b = rooms[name_b]

        q_buoyancy = door_buoyancy_exchange(
            room_a, room_b, a, b, connection, pressure
        )

        q_vent = connection_ventilation_exchange(
            connection,
            max(
                float(a.get("_window_airflow", 0.0)),
                float(b.get("_window_airflow", 0.0))
            )
        )

        q_total = q_buoyancy + q_vent

        if q_total <= 0:
            continue

        # m³ intercambiados por sentido durante el subpaso.
        exchanged_volume = q_total * dt_s / 3600.0

        # Limitación para evitar intercambiar más aire del disponible.
        exchanged_a = min(
            exchanged_volume,
            0.45 * a["volume"]
        )

        exchanged_b = min(
            exchanged_volume,
            0.45 * b["volume"]
        )

        mass_a = dry_air_mass(
            exchanged_a,
            a["temperature"],
            a["w"],
            pressure
        )

        mass_b = dry_air_mass(
            exchanged_b,
            b["temperature"],
            b["w"],
            pressure
        )

        # Humedad: intercambio bidireccional.
        moisture_delta[name_a] += mass_b * b["w"] - mass_a * a["w"]
        moisture_delta[name_b] += mass_a * a["w"] - mass_b * b["w"]

        # Energía sensible: intercambio bidireccional.
        energy_delta[name_a] += (
            mass_b * CP_AIR * b["temperature"] -
            mass_a * CP_AIR * a["temperature"]
        )

        energy_delta[name_b] += (
            mass_a * CP_AIR * a["temperature"] -
            mass_b * CP_AIR * b["temperature"]
        )

    for name, state in states.items():
        state["w"] = max(
            0.0,
            state["w"] +
            moisture_delta[name] / max(0.01, state["dry_air_kg"])
        )

        state["temperature"] += (
            energy_delta[name] /
            max(1.0, state["capacity"])
        )


def apply_condensation(state, psych, pressure):
    """
    Condensación del exceso de vapor sobre saturación.

    Se retira del aire la masa de agua que excede la humedad específica
    de saturación a la temperatura actual.

    La energía latente de condensación no se incorpora en esta fase.
    """
    w_sat = saturation_humidity_ratio(
        psych, state["temperature"], pressure
    )

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
    Integra un subpaso de una estancia.

    Orden:
      1. Ventilación exterior.
      2. Generación de humedad y calor interno.
      3. Deshumidificación.
      4. Calefacción.
      5. Balance térmico con cerramientos.
      6. Condensación.
    """
    pressure = float(config["pressure_pa"])

    t = state["temperature"]
    w = state["w"]

    tout = float(weather["temperature"])
    rhout = float(weather["rh"])
    solar = float(weather["solar"])

    wout = psych.humidity_ratio(tout, rhout, pressure)

    volume = state["volume"]
    dry_mass = max(0.01, state["dry_air_kg"])

    dt_h = dt_s / 3600.0

    # ---------------------------------------------------------------
    # VENTILACION EXTERIOR
    # ---------------------------------------------------------------

    ach_base = max(0.0, float(room.get("air_changes_h", 0.0)))

    q_window = window_airflow(room, weather)

    state["_window_airflow"] = q_window

    ach_window = q_window / max(0.1, volume)

    ach_control = ventilation_control_ach(
        w,
        wout,
        psych.humidity_ratio(
            t,
            config["target_rh"],
            pressure
        ),
        ach_base + ach_window,
        float(config.get("ventilation_max_ach", 2.0)),
        bool(config.get("ventilation_control", True))
    )

    ach_total = ach_base + ach_window + ach_control

    # Renovación de aire con solución exponencial.
    if ach_total > 0:
        decay = math.exp(-ach_total * dt_h)

        w = (
            wout +
            (w - wout) * decay
        )

        state["ventilation_m3"] += (
            ach_total * volume * dt_h
        )

    state["ventilation_minutes"] += (
        dt_h * 60.0 if ach_control > 0 or ach_window > 0 else 0.0
    )

    # ---------------------------------------------------------------
    # OCUPACION Y GANANCIAS INTERNAS
    # ---------------------------------------------------------------

    people = room_occupancy(room, config, hour)

    moisture_kg = (
        people *
        float(config["moisture_per_person_g_h"]) /
        1000.0 *
        dt_h
    )

    sensible_w = (
        people *
        float(config["sensible_gain_per_person_w"]) +
        float(config.get("internal_gain_w", 0.0))
    )

    w += moisture_kg / dry_mass

    solar_w = 0.0

    if config.get("solar_enabled", True):
        solar_w = (
            max(0.0, solar) *
            float(room.get("window_area", 0.0)) *
            float(config.get("solar_factor", 0.55))
        )

    # ---------------------------------------------------------------
    # DESHUMIDIFICACION
    # ---------------------------------------------------------------

    rh = psych.relative_humidity(t, w, pressure)

    cap_kg_h = dehumidifier_capacity_kg_h(
        config, t, rh
    )

    target_w = psych.humidity_ratio(
        t,
        float(config["target_rh"]),
        pressure
    )

    excess_kg = max(
        0.0,
        (w - target_w) * dry_mass
    )

    extracted_kg = min(
        excess_kg,
        cap_kg_h * dt_h
    )

    w -= extracted_kg / dry_mass

    state["dehumidified_kg"] += extracted_kg

    dehum_minutes = 0.0

    if extracted_kg > 0 and cap_kg_h > 0:
        dehum_minutes = (
            extracted_kg / cap_kg_h * 60.0 / dt_h
        ) * dt_h

    state["dehumidifier_minutes"] += dehum_minutes

    # Potencia térmica media del deshumidificador durante el subpaso.
    dehum_heat_w = 0.0
    dehum_electric_kwh = 0.0

    if extracted_kg > 0:
        latent_kwh = (
            extracted_kg * H_FG / 3600000.0
        )

        electric_kwh = (
            float(config.get("dehumidifier_power_kw", 0.0)) *
            dt_h *
            dehum_minutes / max(1e-9, dt_h * 60.0)
        )

        dehum_electric_kwh = electric_kwh

        dehum_heat_kwh = (
            latent_kwh + electric_kwh
        ) * float(config.get("dehumidifier_heat_factor", 1.0))

        dehum_heat_w = dehum_heat_kwh / dt_h * 1000.0

    state["dehumidifier_kwh"] += dehum_electric_kwh

    # ---------------------------------------------------------------
    # CALEFACCION
    # ---------------------------------------------------------------

    ua = state["ua_envelope"] + (
        0.33 * ach_total * volume
    )

    gains_without_heating = (
        sensible_w +
        solar_w +
        dehum_heat_w
    )

    t_free = exact_thermal_step(
        t, tout, ua, state["capacity"],
        gains_without_heating, dt_s
    )

    heater_w = 0.0

    if t_free < float(config["target_temperature"]):
        if ua > 1e-9:
            decay = math.exp(
                -ua * dt_s / state["capacity"]
            )

            response = (
                (1.0 - decay) / ua
            )
        else:
            response = dt_s / state["capacity"]

        required_w = max(
            0.0,
            (float(config["target_temperature"]) - t_free) /
            max(1e-12, response)
        )

        heater_w = min(
            float(config["heater_kw"]) * 1000.0,
            required_w
        )

    t_new = exact_thermal_step(
        t,
        tout,
        ua,
        state["capacity"],
        gains_without_heating + heater_w,
        dt_s
    )

    # ---------------------------------------------------------------
    # HUMEDAD DE COMBUSTION
    # ---------------------------------------------------------------

    combustion_g = 0.0

    if (
        config.get("heating_type") == "butane" and
        heater_w > 0
    ):
        thermal_kwh = heater_w * dt_s / 3600000.0

        combustion_g = (
            thermal_kwh *
            float(config.get("combustion_moisture_g_kwh", 75.0))
        )

        w += (
            combustion_g / 1000.0
        ) / dry_mass

    # ---------------------------------------------------------------
    # ACTUALIZACION TERMICA E HIGROMETRICA
    # ---------------------------------------------------------------

    state["temperature"] = t_new
    state["w"] = max(0.0, w)

    heater_kwh_th = heater_w * dt_s / 3600000.0

    heater_kwh = heater_energy_kwh(
        heater_kwh_th, config
    )

    state["heater_kwh_th"] += heater_kwh_th
    state["heater_kwh"] += heater_kwh

    state["heater_butane_kg"] += heater_butane_kg(
        heater_kwh_th, config
    )

    state["heater_minutes"] += (
        60.0 * dt_h *
        heater_w / max(1.0, float(config["heater_kw"]) * 1000.0)
    )

    # Condensación: se calcula después de las ganancias de humedad
    # y de la actualización de temperatura.
    update_dry_air_mass(state, pressure)

    apply_condensation(
        state, psych, pressure
    )

    update_dry_air_mass(state, pressure)

    return {
        "people": people,
        "solar_w": solar_w,
        "ua": ua,
        "heater_w": heater_w,
        "dehum_heat_w": dehum_heat_w,
        "combustion_g": combustion_g,
        "ventilation_ach": ach_total
    }


# ---------------------------------------------------------------------------
# RESULTADOS HORARIOS
# ---------------------------------------------------------------------------

def room_hour_result(room, state, config, psych, weather,
                     hour, hour_data):
    """Construye el resultado horario de una estancia."""
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
        "dehum_kg": state["dehumidified_kg"],
        "dehum_kwh": state["dehumidifier_kwh"],
        "heater_kwh": state["heater_kwh"],
        "heater_kwh_th": state["heater_kwh_th"],
        "heater_butane_kg": state["heater_butane_kg"],
        "ventilation_m3": state["ventilation_m3"],
        "vent_min": state["ventilation_minutes"],
        "dehum_min": state["dehumidifier_minutes"],
        "heat_min": state["heater_minutes"],
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

    if selected_room is not None:
        name = selected_rooms[0]["name"]

        return {
            "room": room_label,
            "results": results_by_room[name],
            "rooms": results_by_room,
            "ua": total_ua,
            "volume": total_volume,
            "capacity": total_capacity
        }

    # Resultados agregados de vivienda:
    # se ponderan temperatura y humedad por masa de aire seco.
    global_results = []

    for index in range(int(hours)):
        total_dry_mass = 0.0
        weighted_temperature = 0.0
        weighted_w = 0.0

        for name, state in states.items():
            result = results_by_room[name][index]

            mass = state["dry_air_kg"]

            total_dry_mass += mass
            weighted_temperature += result["tin"] * mass
            weighted_w += result["w_g_kg"] / 1000.0 * mass

        mean_t = weighted_temperature / max(0.01, total_dry_mass)
        mean_w = weighted_w / max(0.01, total_dry_mass)

        mean_rh = psych.relative_humidity(
            mean_t, mean_w, config["pressure_pa"]
        )

        mean_dew = psych.dew_point(
            mean_t, mean_w, config["pressure_pa"]
        )

        room_results = [
            results_by_room[name][index]
            for name in results_by_room
        ]

        global_results.append({
            "hour": index,
            "tin": mean_t,
            "rh": mean_rh,
            "w_g_kg": mean_w * 1000.0,
            "dew": mean_dew,
            "tout": room_results[0]["tout"],
            "rhout": room_results[0]["rhout"],
            "solar": room_results[0]["solar"],
            "condensate_kg": sum(
                r["condensate_kg"] for r in room_results
            ),
            "dehum_kg": sum(
                r["dehum_kg"] for r in room_results
            ),
            "dehum_kwh": sum(
                r["dehum_kwh"] for r in room_results
            ),
            "heater_kwh": sum(
                r["heater_kwh"] for r in room_results
            ),
            "heater_kwh_th": sum(
                r["heater_kwh_th"] for r in room_results
            ),
            "heater_butane_kg": sum(
                r["heater_butane_kg"] for r in room_results
            ),
            "ventilation_m3": sum(
                r["ventilation_m3"] for r in room_results
            )
        })

    return {
        "room": room_label,
        "results": global_results,
        "rooms": results_by_room,
        "ua": total_ua,
        "volume": total_volume,
        "capacity": total_capacity
    }


# ---------------------------------------------------------------------------
# CONFIGURACION Y VALIDACION
# ---------------------------------------------------------------------------

def load_config(path=CONFIG_FILE):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        merged = copy.deepcopy(DEFAULT_CONFIG)
        merged.update(data)

        merged.setdefault("connections", [])

        for room in merged["rooms"]:
            room.setdefault("windows_open", False)
            room.setdefault("window_opening_area_m2", 0.0)
            room.setdefault("window_airflow_m3_h", None)
            room.setdefault("wind_factor", 0.60)
            room.setdefault("window_discharge_coefficient", 0.60)

        return merged

    merged = copy.deepcopy(DEFAULT_CONFIG)
    merged["connections"] = []

    for room in merged["rooms"]:
        room.setdefault("windows_open", False)
        room.setdefault("window_opening_area_m2", 0.0)
        room.setdefault("window_airflow_m3_h", None)
        room.setdefault("wind_factor", 0.60)
        room.setdefault("window_discharge_coefficient", 0.60)

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

    if not cfg["rooms"]:
        raise ValueError("Debe existir al menos una estancia.")

    room_names = set()

    for room in cfg["rooms"]:
        name = room["name"]

        if name in room_names:
            raise ValueError(
                "Nombre de estancia duplicado: %s" % name
            )

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

        style.configure(
            "Treeview",
            font=("Segoe UI", 8),
            rowheight=28
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 8, "bold"),
            padding=(4, 6)
        )

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_sim = ttk.Frame(self.nb)
        self.tab_rooms = ttk.Frame(self.nb)
        self.tab_connections = ttk.Frame(self.nb)
        self.tab_weather = ttk.Frame(self.nb)

        self.nb.add(self.tab_sim, text="Simulación")
        self.nb.add(self.tab_rooms, text="Estancias")
        self.nb.add(self.tab_connections, text="Conexiones")
        self.nb.add(self.tab_weather, text="Perfil exterior")

        self._build_sim_tab()
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
        Aplica los valores predeterminados del motor a las configuraciones
        cargadas, incluyendo configuraciones JSON de versiones anteriores.
        """
        if "normalize_config" in globals():
            self.cfg = normalize_config(self.cfg)

    def _refresh_all(self):
        self._normalise_config()
        self._refresh_rooms()
        self._refresh_connections()
        self._refresh_weather()

    # -----------------------------------------------------------------------
    # PESTAÑA DE SIMULACION
    # -----------------------------------------------------------------------

    def _build_sim_tab(self):
        frame = self.tab_sim

        top = ttk.LabelFrame(frame, text="Condiciones y equipos")
        top.pack(fill="x", padx=8, pady=6)

        fields = [
            ("Temperatura inicial (°C)", "initial_temperature"),
            ("HR inicial (%)", "initial_rh"),
            ("Temperatura objetivo (°C)", "target_temperature"),
            ("HR objetivo (%)", "target_rh"),
            ("Personas (global)", "people"),
            ("Deshumidificador (L/día)", "dehumidifier_l_day"),
            ("Potencia deshumidificador (kW)", "dehumidifier_power_kw"),
            ("Calefacción (kW térmicos)", "heater_kw"),
            ("ACH ventilación máxima", "ventilation_max_ach"),
            ("Factor superficie fRsi", "surface_factor"),
            ("COP bomba de calor", "heat_pump_cop"),
            ("Factor térmico deshumidificador", "dehumidifier_heat_factor")
        ]

        self.vars = {}

        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 4)

            ttk.Label(
                top,
                text=label
            ).grid(
                row=row * 2,
                column=col,
                sticky="w",
                padx=5,
                pady=(5, 0)
            )

            var = tk.StringVar(value=str(self.cfg.get(key, 0)))
            self.vars[key] = var

            ttk.Entry(
                top,
                textvariable=var,
                width=15
            ).grid(
                row=row * 2 + 1,
                column=col,
                sticky="w",
                padx=5,
                pady=(0, 5)
            )

        # Tipo de calefacción.
        ttk.Label(top, text="Tipo de calefacción").grid(
            row=6, column=0, sticky="w", padx=5
        )

        self.vars["heating_type"] = tk.StringVar(
            value=self.cfg.get("heating_type", "butane")
        )

        ttk.Combobox(
            top,
            textvariable=self.vars["heating_type"],
            values=("butane", "electric", "heat_pump"),
            width=13,
            state="readonly"
        ).grid(row=7, column=0, sticky="w", padx=5)

        # Selección de estancia.
        ttk.Label(top, text="Ámbito de simulación").grid(
            row=6, column=1, sticky="w", padx=5
        )

        self.room_choice = tk.StringVar(value="TODA LA VIVIENDA")

        self.room_combo = ttk.Combobox(
            top,
            textvariable=self.room_choice,
            width=23,
            state="readonly"
        )

        self.room_combo.grid(row=7, column=1, sticky="w", padx=5)

        # Controles generales.
        self.var_vent = tk.BooleanVar(
            value=self.cfg.get("ventilation_control", True)
        )

        ttk.Checkbutton(
            top,
            text="Ventilación automática por humedad",
            variable=self.var_vent
        ).grid(row=7, column=2, sticky="w", padx=5)

        self.var_solar = tk.BooleanVar(
            value=self.cfg.get("solar_enabled", True)
        )

        ttk.Checkbutton(
            top,
            text="Ganancia solar",
            variable=self.var_solar
        ).grid(row=7, column=3, sticky="w", padx=5)

        # Botonera.
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

        # Resumen.
        result_frame = ttk.LabelFrame(frame, text="Resultados")
        result_frame.pack(fill="both", expand=True, padx=8, pady=5)

        self.summary = tk.Text(
            result_frame,
            height=14,
            wrap="none",
            font=("Consolas", 9)
        )

        self.summary.pack(
            side="left",
            fill="both",
            expand=True,
            padx=4,
            pady=4
        )

        scroll_y = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.summary.yview
        )

        scroll_y.pack(side="right", fill="y")
        self.summary.configure(yscrollcommand=scroll_y.set)

        self.summary.insert(
            "end",
            "Configura los parámetros y pulsa «Simular 24 h».\n"
        )

        # Gráficas.
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

        cols = (
            "name",
            "height",
            "floor_area",
            "window_area",
            "wall_area",
            "roof_area",
            "floor_exposed_area",
            "air_changes_h",
            "people",
            "windows_open",
            "window_opening_area_m2"
        )

        self.room_cols = cols

        self.room_tree = ttk.Treeview(
            frame,
            columns=cols,
            show="headings",
            height=15
        )

        headings = {
            "name": "Estancia",
            "height": "Altura m",
            "floor_area": "Suelo m²",
            "window_area": "Ventanas m²",
            "wall_area": "Muros ext. m²",
            "roof_area": "Cubierta m²",
            "floor_exposed_area": "Suelo ext. m²",
            "air_changes_h": "ACH",
            "people": "Personas",
            "windows_open": "Ventanas",
            "window_opening_area_m2": "Abertura m²"
        }

        widths = {
            "name": 110,
            "height": 65,
            "floor_area": 75,
            "window_area": 85,
            "wall_area": 90,
            "roof_area": 80,
            "floor_exposed_area": 90,
            "air_changes_h": 60,
            "people": 65,
            "windows_open": 75,
            "window_opening_area_m2": 95
        }

        for col in cols:
            self.room_tree.heading(
                col,
                text=headings[col]
            )

            self.room_tree.column(
                col,
                width=widths[col],
                anchor="center"
            )

        self.room_tree.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=8, pady=5)

        ttk.Button(
            btns,
            text="Añadir",
            command=self._add_room
        ).pack(side="left", padx=3)

        ttk.Button(
            btns,
            text="Editar",
            command=self._edit_room
        ).pack(side="left", padx=3)

        ttk.Button(
            btns,
            text="Eliminar",
            command=self._delete_room
        ).pack(side="left", padx=3)

        note = (
            "Las superficies de ventanas, muros, cubierta y suelo expuesto "
            "representan los cerramientos que intercambian calor con el "
            "exterior. La superficie de apertura de ventanas es el área "
            "efectiva libre para el paso del aire, no la superficie acristalada."
        )

        ttk.Label(
            frame,
            text=note,
            wraplength=1100
        ).pack(anchor="w", padx=10, pady=6)

    def _refresh_rooms(self):
        for item in self.room_tree.get_children():
            self.room_tree.delete(item)

        for idx, room in enumerate(self.cfg.get("rooms", [])):
            self.room_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    room.get("name", ""),
                    room.get("height", 0),
                    room.get("floor_area", 0),
                    room.get("window_area", 0),
                    room.get("wall_area", 0),
                    room.get("roof_area", 0),
                    room.get("floor_exposed_area", 0),
                    room.get("air_changes_h", 0),
                    room.get("people", 0),
                    "ABIERTAS" if room.get("windows_open", False) else "CERRADAS",
                    room.get("window_opening_area_m2", 0)
                )
            )

        self.room_combo["values"] = (
            ["TODA LA VIVIENDA"] +
            [r.get("name", "") for r in self.cfg.get("rooms", [])]
        )

        if self.room_choice.get() not in self.room_combo["values"]:
            self.room_choice.set("TODA LA VIVIENDA")

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
        for key, var in self.vars.items():
            if key == "heating_type":
                self.cfg[key] = var.get()
            else:
                value = self._to_float(var.get())

                if key == "people":
                    value = int(value)

                self.cfg[key] = value

        self.cfg["ventilation_control"] = self.var_vent.get()
        self.cfg["solar_enabled"] = self.var_solar.get()

    # -----------------------------------------------------------------------
    # SIMULACION
    # -----------------------------------------------------------------------

    def _run(self):
        try:
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

            self._show_results(self.last_simulation)
            self._plot(self.last_simulation)

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
            x.get("fuel_kg", 0)
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
            ax.legend(loc="best")

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
                save_config(self.cfg, path)

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
            # load_config debe encargarse de normalizar las configuraciones
            # antiguas y completar las nuevas propiedades.
            self.cfg = load_config(path)

            self._normalise_config()

            validate_config(self.cfg)

            for key, var in self.vars.items():
                var.set(str(self.cfg.get(key, "")))

            self.var_vent.set(
                self.cfg.get("ventilation_control", True)
            )

            self.var_solar.set(
                self.cfg.get("solar_enabled", True)
            )

            self.last_simulation = None

            self.summary.delete("1.0", "end")
            self.summary.insert(
                "end",
                "Configuración cargada. Ejecuta una simulación.\n"
            )

            for child in self.plot_frame.winfo_children():
                child.destroy()

            self._refresh_all()

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

    # -----------------------------------------------------------------------
    # DIALOGO DE EDICION DE ESTANCIAS
    # -----------------------------------------------------------------------

    def _room_dialog(self, room=None):
        original = copy.deepcopy(room) if room else {
            "name": "NUEVA",
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
            "air_changes_h": 0.35,
            "thermal_mass_j_m2k": self.cfg.get(
                "thermal_mass_j_m2k",
                100000.0
            ),
            "people": 0,
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60
        }

        fields = [
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
            ("Área efectiva de apertura (m²)", "window_opening_area_m2", float),
            ("Factor exposición al viento", "wind_factor", float),
            ("Coeficiente descarga ventana", "window_discharge_coefficient", float)
        ]

        win = tk.Toplevel(self.root)
        win.title("Editar estancia")
        win.resizable(False, False)

        entries = {}

        for i, (label, key, typ) in enumerate(fields):
            ttk.Label(
                win,
                text=label
            ).grid(
                row=i,
                column=0,
                sticky="w",
                padx=8,
                pady=3
            )

            var = tk.StringVar(
                value=str(original.get(key, ""))
            )

            ttk.Entry(
                win,
                textvariable=var,
                width=22
            ).grid(
                row=i,
                column=1,
                padx=8,
                pady=3
            )

            entries[key] = (var, typ)

        # Apertura de ventanas.
        row_check = len(fields)

        var_windows_open = tk.BooleanVar(
            value=original.get("windows_open", False)
        )

        ttk.Checkbutton(
            win,
            text="Ventanas abiertas",
            variable=var_windows_open
        ).grid(
            row=row_check,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=5
        )

        # Caudal manual de ventana.
        ttk.Label(
            win,
            text="Caudal manual ventana (m³/h, opcional)"
        ).grid(
            row=row_check + 1,
            column=0,
            sticky="w",
            padx=8,
            pady=3
        )

        manual_flow = original.get("window_airflow_m3_h")

        var_manual_flow = tk.StringVar(
            value="" if manual_flow is None else str(manual_flow)
        )

        ttk.Entry(
            win,
            textvariable=var_manual_flow,
            width=22
        ).grid(
            row=row_check + 1,
            column=1,
            padx=8,
            pady=3
        )

        result = {"room": None}

        def accept():
            try:
                data = {}

                for key, (var, typ) in entries.items():
                    value = var.get()

                    if typ is str:
                        data[key] = value.strip()
                    else:
                        data[key] = typ(
                            value.replace(",", ".")
                        )

                data["windows_open"] = var_windows_open.get()

                if var_manual_flow.get().strip():
                    data["window_airflow_m3_h"] = self._to_float(
                        var_manual_flow.get()
                    )
                else:
                    data["window_airflow_m3_h"] = None

                if not data["name"]:
                    raise ValueError(
                        "El nombre no puede estar vacío."
                    )

                # Comprobación de nombres duplicados.
                for existing in self.cfg.get("rooms", []):
                    if existing is room:
                        continue

                    if existing.get("name", "").strip().lower() == (
                        data["name"].lower()
                    ):
                        raise ValueError(
                            "Ya existe una estancia con ese nombre."
                        )

                for key in ("height", "floor_area"):
                    if data[key] <= 0:
                        raise ValueError(
                            "%s debe ser positivo." % key
                        )

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
                    "window_opening_area_m2",
                    "window_airflow_m3_h"
                )

                for key in non_negative:
                    value = data.get(key)

                    if value is not None and value < 0:
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
                    data["windows_open"] and
                    data["window_opening_area_m2"] <= 0 and
                    data["window_airflow_m3_h"] is None
                ):
                    raise ValueError(
                        "Si las ventanas están abiertas, debes indicar "
                        "el área efectiva de apertura o un caudal manual."
                    )

                result["room"] = data
                win.destroy()

            except Exception as exc:
                messagebox.showerror(
                    "Datos de estancia",
                    str(exc),
                    parent=win
                )

        buttons = ttk.Frame(win)
        buttons.grid(
            row=row_check + 2,
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

        return result["room"]
    # -----------------------------------------------------------------------
    # OPERACIONES SOBRE ESTANCIAS
    # -----------------------------------------------------------------------

    def _add_room(self):
        room = self._room_dialog()

        if room:
            self.cfg["rooms"].append(room)
            self._refresh_all()

    def _edit_room(self):
        selected = self.room_tree.selection()

        if not selected:
            messagebox.showwarning(
                "Estancias",
                "Selecciona una estancia."
            )
            return

        idx = int(selected[0])

        old_name = self.cfg["rooms"][idx].get("name")

        room = self._room_dialog(
            self.cfg["rooms"][idx]
        )

        if room:
            self.cfg["rooms"][idx] = room

            new_name = room.get("name")

            # Si cambia el nombre, actualizar las conexiones asociadas.
            if old_name != new_name:
                for connection in self.cfg.get("connections", []):
                    if connection.get("room_a") == old_name:
                        connection["room_a"] = new_name

                    if connection.get("room_b") == old_name:
                        connection["room_b"] = new_name

            self._refresh_all()

    def _delete_room(self):
        selected = self.room_tree.selection()

        if not selected:
            return

        idx = int(selected[0])

        if len(self.cfg["rooms"]) <= 1:
            messagebox.showwarning(
                "Estancias",
                "Debe quedar al menos una estancia."
            )
            return

        room_name = self.cfg["rooms"][idx].get("name")

        if not messagebox.askyesno(
            "Eliminar",
            "¿Eliminar la estancia '%s'?" % room_name
        ):
            return

        del self.cfg["rooms"][idx]

        # Eliminar conexiones que hagan referencia a la estancia borrada.
        self.cfg["connections"] = [
            connection
            for connection in self.cfg.get("connections", [])
            if (
                connection.get("room_a") != room_name and
                connection.get("room_b") != room_name
            )
        ]

        self._refresh_all()


# ---------------------------------------------------------------------------
# ARRANQUE DE LA APLICACION
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()