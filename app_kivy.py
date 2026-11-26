# -*- coding: utf-8 -*-
"""
Interfaz Kivy para el simulador higrotérmico de vivienda.
Requiere 'engine.py' (extraído de perdidasTermicas2_modGPT3.py) en el mismo directorio.
"""

import copy
from datetime import date

from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'systemanddock')
Config.set('kivy', 'exit_on_escape', '0')

from kivy.core.window import Window
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp
from kivy.clock import Clock

import engine
load_config = engine.load_config
save_config = engine.save_config
validate_config = engine.validate_config
simulate = engine.simulate
CONFIG_FILE = getattr(engine, 'CONFIG_FILE', 'vivienda_config.json')

# --- Matplotlib opcional ---
HAS_MPL = False
Figure = None
FigureCanvasKivyAgg = None
try:
    from matplotlib.figure import Figure as _Figure
    Figure = _Figure
    for _mod, _attr in [
        ('kivy_garden.matplotlib.backend_kivyagg', 'FigureCanvasKivyAgg'),
        ('kivy_garden.matplotlib', 'FigureCanvasKivyAgg'),
        ('matplotlib.backends.backend_kivyagg', 'FigureCanvasKivyAgg'),
    ]:
        try:
            _m = __import__(_mod, fromlist=[_attr])
            FigureCanvasKivyAgg = getattr(_m, _attr)
            HAS_MPL = True
            break
        except Exception:
            continue
except Exception:
    pass


# ------------------------------------------------------------------ helpers

GLOBAL_DEFAULTS = {
    "latitude_deg": 42.5,
    "longitude_deg": -8.0,
    "altitude_m": 0.0,
    "solar_date": None,
    "solar_utc_offset_hours": None,
    "solar_glazing_area_factor": 0.90,
    "solar_ground_reflectance": 0.20,
    "solar_shading_factor": 1.0,
    "solar_hour_reference": "interval_end",
}

ROOM_DEFAULTS = {
    "heater_enabled": False,
    "dehumidifier_enabled": False,
    "window_groups": [],
}


def show_popup(title, message):
    content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
    content.add_widget(Label(
        text=str(message), halign='left', valign='top',
        text_size=(dp(280), None)))
    btn = Button(text="OK", size_hint_y=None, height=dp(44))
    content.add_widget(btn)
    popup = Popup(title=title, content=content,
                  size_hint=(0.85, None), height=dp(260))
    btn.bind(on_release=lambda *a: popup.dismiss())
    popup.open()


def prompt_filename(default, callback):
    content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
    ti = TextInput(text=default, multiline=False,
                   size_hint_y=None, height=dp(44))
    content.add_widget(ti)
    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    ok = Button(text="Aceptar")
    cancel = Button(text="Cancelar")
    btns.add_widget(ok)
    btns.add_widget(cancel)
    content.add_widget(btns)
    popup = Popup(title="Fichero", content=content,
                  size_hint=(0.85, None), height=dp(220))
    def _ok(*a):
        popup.dismiss()
        callback(ti.text.strip() or default)
    def _cancel(*a):
        popup.dismiss()
        callback(None)
    ok.bind(on_release=_ok)
    cancel.bind(on_release=_cancel)
    popup.open()


def make_row(label, widget):
    box = BoxLayout(orientation='vertical', size_hint_y=None,
                    height=dp(72), spacing=dp(2))
    box.add_widget(Label(text=label, size_hint_y=None, height=dp(24),
                         halign='left', valign='middle',
                         text_size=(None, dp(24))))
    box.add_widget(widget)
    return box


def make_text(value, numeric=False):
    ti = TextInput(
        text="" if value is None else str(value),
        multiline=False,
        size_hint_y=None,
        height=dp(44),
        font_size=sp(15),
    )
    if numeric:
        ti.input_type = 'number'
    return ti


def make_spinner(values, value):
    return Spinner(
        text="" if value is None else str(value),
        values=[str(v) for v in values],
        size_hint_y=None, height=dp(44), font_size=sp(15))


def read_float(text, default=0.0):
    try:
        return float(str(text).replace(",", ".").strip())
    except (TypeError, ValueError, AttributeError):
        return default


# ------------------------------------------------------------------- specs

# Campos numéricos/texto de la estancia (se renderizan como TextInput).
ROOM_FIELDS = [
    ("name", "Nombre", "text"),
    ("height", "Altura (m)", "num"),
    ("floor_area", "Superficie suelo (m²)", "num"),
    ("window_area", "Ventanas (m²)", "num"),
    ("window_u", "U ventanas (W/m²K)", "num"),
    ("wall_area", "Muros exteriores (m²)", "num"),
    ("wall_u", "U muros (W/m²K)", "num"),
    ("roof_area", "Cubierta exterior (m²)", "num"),
    ("roof_u", "U cubierta (W/m²K)", "num"),
    ("floor_exposed_area", "Suelo expuesto (m²)", "num"),
    ("floor_u", "U suelo (W/m²K)", "num"),
    ("air_changes_h", "Renovaciones base (1/h)", "num"),
    ("thermal_mass_j_m2k", "Masa térmica (J/m²K)", "num"),
    ("people", "Personas habituales", "num"),
    ("internal_gain_w", "Ganancia interna (W)", "num"),
    ("dehumidifier_l_day", "Deshumidificador (L/día)", "num"),
    ("dehumidifier_power_kw", "Potencia deshumidificador (kW)", "num"),
    ("heater_kw", "Calefacción (kW térmicos)", "num"),
    ("window_opening_area_m2", "Área efectiva apertura (m²)", "num"),
    ("wind_factor", "Factor exposición viento (0-1)", "num"),
    ("window_discharge_coefficient", "Coef. descarga ventana (0-1)", "num"),
]

ROOM_FALLBACK_KEYS = {"dehumidifier_l_day", "dehumidifier_power_kw",
                       "heater_kw"}

HEATING_TYPES = ("", "butane", "electric", "heat_pump")

SIM_FIELDS = [
    ("initial_temperature", "Temperatura inicial (°C)"),
    ("initial_rh", "HR inicial (%)"),
    ("target_temperature", "Temperatura objetivo (°C)"),
    ("target_rh", "HR objetivo (%)"),
    ("occupancy_start", "Hora inicio ocupación"),
    ("occupancy_end", "Hora fin ocupación"),
    ("moisture_per_person_g_h", "Humedad por persona (g/h)"),
    ("sensible_gain_per_person_w", "Ganancia sensible/persona (W)"),
    ("ventilation_max_ach", "ACH ventilación máxima"),
    ("surface_factor", "Factor superficie (fRsi)"),
    ("heat_pump_cop", "COP bomba de calor"),
    ("dehumidifier_heat_factor", "Factor térmico deshumidificador"),
    ("solar_factor", "Factor solar (si no hay grupos)"),
    ("combustion_moisture_g_kwh", "Humedad combustión (g/kWh)"),
    # --- Geometría solar ---
    ("latitude_deg", "Latitud (°)"),
    ("longitude_deg", "Longitud (°)"),
    ("altitude_m", "Altitud (m)"),
    ("solar_glazing_area_factor", "Factor área acristalada"),
    ("solar_ground_reflectance", "Reflectancia del suelo"),
    ("solar_shading_factor", "Factor de sombreado global"),
]

SIM_TEXT_FIELDS = [
    ("solar_date", "Fecha solar (YYYY-MM-DD)"),
]


class SimulatorApp(App):

    def build(self):
        try:
            Window.softinput_mode = 'below_target'
        except Exception:
            pass
        self.title = "Simulador higrotérmico"

        self.cfg = self._load_cfg_safe()
        self.last_simulation = None
        self.current_room_index = 0

        root = BoxLayout(orientation='vertical')

        nav = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(2))
        self.nav_buttons = {}
        for name, title in [
            ('sim', 'Simular'),
            ('rooms', 'Estancias'),
            ('connections', 'Conexiones'),
            ('weather', 'Meteo'),
        ]:
            btn = Button(text=title, font_size=sp(13))
            btn.bind(on_release=lambda b, n=name: self._go_to(n))
            nav.add_widget(btn)
            self.nav_buttons[name] = btn
        root.add_widget(nav)

        self.sm = ScreenManager()
        self.sm.add_widget(self._build_sim_screen())
        self.sm.add_widget(self._build_rooms_screen())
        self.sm.add_widget(self._build_connections_screen())
        self.sm.add_widget(self._build_weather_screen())
        root.add_widget(self.sm)

        self._go_to('sim')
        Clock.schedule_once(lambda dt: self._load_room_form(), 0.1)
        return root

    def _load_cfg_safe(self):
        cfg = load_config()
        cfg.setdefault("connections", [])
        for key, default in GLOBAL_DEFAULTS.items():
            if key not in cfg or cfg[key] is None:
                if key == "solar_date" and cfg.get(key) is None:
                    cfg[key] = date.today().isoformat()
                else:
                    cfg.setdefault(key, default)
        for room in cfg.get("rooms", []):
            for key, default in ROOM_DEFAULTS.items():
                room.setdefault(key, default if not isinstance(default, list) else list(default))
        return cfg

    def _normalise_cfg(self):
        self.cfg.setdefault("connections", [])
        for key, default in GLOBAL_DEFAULTS.items():
            if key == "solar_date" and self.cfg.get(key) is None:
                self.cfg[key] = date.today().isoformat()
            else:
                self.cfg.setdefault(key, default)
        for room in self.cfg.get("rooms", []):
            for key, default in ROOM_DEFAULTS.items():
                room.setdefault(
                    key, default if not isinstance(default, list) else list(default))

    def _go_to(self, name):
        self.sm.current = name
        for n, btn in self.nav_buttons.items():
            btn.background_color = ((0.25, 0.5, 0.85, 1)
                                     if n == name
                                     else (0.65, 0.65, 0.65, 1))

    # ================================================= SIMULATION

    def _build_sim_screen(self):
        screen = Screen(name='sim')
        outer = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        screen.add_widget(outer)

        scroll = ScrollView(size_hint_y=0.55)
        self.sim_form = BoxLayout(orientation='vertical',
                                    size_hint_y=None, spacing=dp(2),
                                    padding=dp(4))
        self.sim_form.bind(minimum_height=self.sim_form.setter('height'))
        scroll.add_widget(self.sim_form)
        outer.add_widget(scroll)

        self.sim_fields = {}
        for key, label in SIM_FIELDS:
            ti = make_text(self.cfg.get(key, ""), numeric=True)
            self.sim_fields[key] = ti
            self.sim_form.add_widget(make_row(label, ti))

        self.sim_text_fields = {}
        for key, label in SIM_TEXT_FIELDS:
            ti = make_text(self.cfg.get(key, ""), numeric=False)
            self.sim_text_fields[key] = ti
            self.sim_form.add_widget(make_row(label, ti))

        self.sim_heating_type = make_spinner(
            ("butane", "electric", "heat_pump"),
            self.cfg.get("heating_type", "butane"))
        self.sim_form.add_widget(make_row(
            "Tipo calefacción (global)", self.sim_heating_type))

        room_names = ["TODA LA VIVIENDA"] + [
            r.get("name", "") for r in self.cfg.get("rooms", [])]
        self.sim_room_choice = make_spinner(room_names, "TODA LA VIVIENDA")
        self.sim_form.add_widget(make_row(
            "Ámbito de simulación", self.sim_room_choice))

        sw1 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        sw1.add_widget(Label(text="Ventilación automática", size_hint_x=0.7))
        self.sim_vent_control = Switch(active=bool(
            self.cfg.get("ventilation_control", True)))
        sw1.add_widget(self.sim_vent_control)
        self.sim_form.add_widget(sw1)

        sw2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        sw2.add_widget(Label(text="Ganancia solar", size_hint_x=0.7))
        self.sim_solar_enabled = Switch(active=bool(
            self.cfg.get("solar_enabled", True)))
        sw2.add_widget(self.sim_solar_enabled)
        self.sim_form.add_widget(sw2)

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        run = Button(text="Simular 24 h")
        run.bind(on_release=lambda *a: self._run_simulation())
        btns.add_widget(run)
        save = Button(text="Guardar cfg")
        save.bind(on_release=lambda *a: self._save_config())
        btns.add_widget(save)
        load = Button(text="Cargar cfg")
        load.bind(on_release=lambda *a: self._load_config())
        btns.add_widget(load)
        csv = Button(text="CSV")
        csv.bind(on_release=lambda *a: self._export_csv())
        btns.add_widget(csv)
        outer.add_widget(btns)

        self.results_text = TextInput(
            text="Configura los parámetros y pulsa «Simular 24 h».\n",
            readonly=True, multiline=True, font_size=sp(10),
            size_hint_y=0.45)
        outer.add_widget(self.results_text)

        self.plot_box = BoxLayout(size_hint_y=None, height=0)
        outer.add_widget(self.plot_box)

        return screen

    def _collect_sim_fields(self):
        for key, ti in self.sim_fields.items():
            self.cfg[key] = read_float(ti.text, self.cfg.get(key, 0.0))
        for key, ti in self.sim_text_fields.items():
            text = ti.text.strip()
            if key == "solar_date" and not text:
                text = date.today().isoformat()
            self.cfg[key] = text
        self.cfg["heating_type"] = self.sim_heating_type.text or "butane"
        self.cfg["ventilation_control"] = bool(self.sim_vent_control.active)
        self.cfg["solar_enabled"] = bool(self.sim_solar_enabled.active)

    def _run_simulation(self):
        try:
            self._collect_sim_fields()
            validate_config(self.cfg)
            choice = self.sim_room_choice.text
            selected = None
            if choice and choice != "TODA LA VIVIENDA":
                selected = choice  # el engine acepta nombre o índice
            self.last_simulation = simulate(self.cfg, selected, 24)
            self._show_results(self.last_simulation)
            self._plot_results(self.last_simulation)
        except Exception as exc:
            show_popup("Error de simulación", str(exc))

    def _show_results(self, sim):
        rows = sim.get("results", []) or []
        if not rows:
            self.results_text.text = "Sin resultados."
            return
        n = len(rows)

        def avg(key):
            vals = [r.get(key) for r in rows if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else 0.0

        mean_t = avg("tin_avg") or avg("tin")
        mean_rh = avg("rh_avg") or avg("rh")
        mean_wb = avg("wet_bulb_c")
        cond_h = sum(1 for r in rows if r.get("condensation"))
        vent = sum(r.get("vent_min", 0) for r in rows)
        dehum = sum(r.get("dehum_min", 0) for r in rows)
        heat = sum(r.get("heat_min", 0) for r in rows)
        dehum_kg = sum(r.get("dehum_kg", 0) for r in rows)
        cond_kg = sum(r.get("condensate_kg", 0) for r in rows)
        heat_th = sum(r.get("heater_kwh_th", 0) for r in rows)
        heat_el = sum(r.get("heater_kwh", 0) for r in rows)
        fuel = sum(r.get("heater_butane_kg", 0) for r in rows)

        lines = [
            "RESULTADOS: %s" % sim.get("room", "?"),
            "Volumen %.1f m³ | UA %.1f W/K | C %.2f MJ/K" % (
                sim.get("volume", 0), sim.get("ua", 0),
                sim.get("capacity", 0) / 1e6),
            "T media %.1f °C | HR media %.1f %% | Tbh media %.1f °C | "
            "Horas cond. %d" % (mean_t, mean_rh, mean_wb, cond_h),
            "Vent %.0f min | Desh %.0f min (%.2f L) | "
            "Cond %.3f kg" % (vent, dehum, dehum_kg, cond_kg),
            "Cal %.0f min | Eth %.2f kWh | Eel %.2f kWh | "
            "Butano %.3f kg" % (heat, heat_th, heat_el, fuel),
            "",
            "Hr  Text  Tint   HR  Tbh  Rocio Superf Vent Desh Cal  Cond",
        ]
        for r in rows:
            t_disp = r.get("tin_avg", r.get("tin", 0))
            rh_disp = r.get("rh_avg", r.get("rh", 0))
            wb_disp = r.get("wet_bulb_c", r.get("tin", 0))
            lines.append(
                "%02d %5.1f %5.1f %5.1f %5.1f %5.1f %6.1f %3.0f %3.0f %3.0f %.3f" % (
                    r.get("hour", 0), r.get("tout", 0), t_disp, rh_disp,
                    wb_disp, r.get("dew", 0), r.get("surface", 0),
                    r.get("vent_min", 0), r.get("dehum_min", 0),
                    r.get("heat_min", 0), r.get("condensate_kg", 0)))

        room_results = sim.get("room_results", {})
        if room_results:
            lines.append("")
            lines.append("POR ESTANCIA:")
            for name, data in room_results.items():
                lines.append(
                    "  %s: T=%.1f °C HR=%.1f %% Tbh=%.1f °C cond=%.3f kg" % (
                        name, data.get("tin", 0), data.get("rh", 0),
                        data.get("wet_bulb_c", 0),
                        data.get("condensate_kg", 0)))
        self.results_text.text = "\n".join(lines)

    def _plot_results(self, sim):
        for child in list(self.plot_box.children):
            self.plot_box.remove_widget(child)
        if not HAS_MPL:
            self.plot_box.height = 0
            return
        try:
            rows = sim.get("results", [])
            if not rows:
                self.plot_box.height = 0
                return
            x = [r.get("hour", i) for i, r in enumerate(rows)]
            fig = Figure(figsize=(6, 2.8), dpi=80)
            ax = fig.add_subplot(111)
            ax.plot(x, [r.get("tin", 0) for r in rows], label="Tint")
            ax.plot(x, [r.get("tout", 0) for r in rows], label="Text")
            ax.plot(x, [r.get("dew", 0) for r in rows], label="Rocío")
            ax.plot(x, [r.get("surface", 0) for r in rows], label="Sup")
            wb = [r.get("wet_bulb_c") for r in rows]
            if any(v is not None for v in wb):
                ax.plot(x, [v if v is not None else 0 for v in wb],
                        label="Tbh", linestyle="--")
            ax.set_xlabel("Hora")
            ax.set_ylabel("°C")
            ax.grid(True)
            ax.legend(loc="best", fontsize=8)
            fig.tight_layout()
            canvas = FigureCanvasKivyAgg(fig)
            self.plot_box.add_widget(canvas)
            self.plot_box.height = dp(240)
        except Exception as exc:
            self.plot_box.height = 0
            print("Plot error:", exc)

    def _save_config(self):
        try:
            self._collect_sim_fields()
            validate_config(self.cfg)
        except Exception as exc:
            show_popup("Error", str(exc))
            return
        def do_save(path):
            if not path:
                return
            try:
                save_config(self.cfg, path)
                show_popup("Guardar", "Guardado en %s" % path)
            except Exception as exc:
                show_popup("Error", str(exc))
        prompt_filename(CONFIG_FILE, do_save)

    def _load_config(self):
        def do_load(path):
            if not path:
                return
            try:
                loaded = load_config(path)
                self.cfg = loaded
                self._normalise_cfg()
                self._reload_all_fields()
                show_popup("Cargar", "Cargado desde %s" % path)
            except Exception as exc:
                show_popup("Error", str(exc))
        prompt_filename(CONFIG_FILE, do_load)

    def _reload_all_fields(self):
        for key, ti in self.sim_fields.items():
            ti.text = str(self.cfg.get(key, ""))
        for key, ti in self.sim_text_fields.items():
            ti.text = str(self.cfg.get(key, "") or "")
        self.sim_heating_type.text = self.cfg.get("heating_type", "butane")
        self.sim_vent_control.active = bool(
            self.cfg.get("ventilation_control", True))
        self.sim_solar_enabled.active = bool(
            self.cfg.get("solar_enabled", True))
        room_names = ["TODA LA VIVIENDA"] + [
            r.get("name", "") for r in self.cfg.get("rooms", [])]
        self.sim_room_choice.values = room_names
        if self.sim_room_choice.text not in room_names:
            self.sim_room_choice.text = "TODA LA VIVIENDA"
        self.current_room_index = 0
        self._load_room_form()
        self._refresh_weather_table()
        self._refresh_connections_list()

    def _export_csv(self):
        if not self.last_simulation:
            show_popup("Exportar", "Primero simula.")
            return
        rows = self.last_simulation.get("results", [])
        if not rows:
            show_popup("Exportar", "Sin resultados.")
            return
        def do_export(path):
            if not path:
                return
            try:
                import csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(
                        f, fieldnames=list(rows[0].keys()), delimiter=";")
                    w.writeheader()
                    w.writerows(rows)
                show_popup("Exportar", "Exportado a %s" % path)
            except Exception as exc:
                show_popup("Error", str(exc))
        prompt_filename("resultados_vivienda.csv", do_export)

    # ================================================= ROOMS

    def _build_rooms_screen(self):
        screen = Screen(name='rooms')
        outer = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        screen.add_widget(outer)

        nav = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        prev = Button(text="◀ Anterior", size_hint_x=0.3)
        prev.bind(on_release=lambda *a: self._nav_room(-1))
        nav.add_widget(prev)
        self.room_label = Label(text="", size_hint_x=0.4, font_size=sp(13))
        nav.add_widget(self.room_label)
        nxt = Button(text="Siguiente ▶", size_hint_x=0.3)
        nxt.bind(on_release=lambda *a: self._nav_room(1))
        nav.add_widget(nxt)
        outer.add_widget(nav)

        scroll = ScrollView(size_hint_y=1)
        self.room_form = BoxLayout(orientation='vertical', size_hint_y=None,
                                    spacing=dp(2), padding=dp(4))
        self.room_form.bind(minimum_height=self.room_form.setter('height'))
        scroll.add_widget(self.room_form)
        outer.add_widget(scroll)

        self.room_inputs = {}
        for key, label, kind in ROOM_FIELDS:
            ti = make_text("", numeric=(kind == "num"))
            self.room_inputs[key] = ti
            self.room_form.add_widget(make_row(label, ti))

        # Interruptores de disponibilidad de equipos.
        eq_frame = BoxLayout(orientation='vertical', size_hint_y=None,
                              height=dp(108), spacing=dp(2))
        row1 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        row1.add_widget(Label(text="Calefacción disponible",
                              size_hint_x=0.7))
        self.room_heater_enabled = Switch(active=False)
        row1.add_widget(self.room_heater_enabled)
        eq_frame.add_widget(row1)
        row2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        row2.add_widget(Label(text="Deshumidificador disponible",
                              size_hint_x=0.7))
        self.room_dehumidifier_enabled = Switch(active=False)
        row2.add_widget(self.room_dehumidifier_enabled)
        eq_frame.add_widget(row2)
        self.room_form.add_widget(eq_frame)

        self.room_heating_type = make_spinner(HEATING_TYPES, "")
        self.room_form.add_widget(make_row(
            "Tipo calefacción (vacío = global)", self.room_heating_type))

        sw = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        sw.add_widget(Label(text="Ventanas abiertas", size_hint_x=0.7))
        self.room_windows_open = Switch(active=False)
        sw.add_widget(self.room_windows_open)
        self.room_form.add_widget(sw)

        self.room_manual_flow = make_text("")
        self.room_form.add_widget(make_row(
            "Caudal manual ventana (m³/h, vacío = no)", self.room_manual_flow))

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        save = Button(text="Guardar cambios")
        save.bind(on_release=lambda *a: self._save_room(silent=False))
        btns.add_widget(save)
        add = Button(text="Añadir")
        add.bind(on_release=lambda *a: self._add_room())
        btns.add_widget(add)
        delete = Button(text="Eliminar")
        delete.bind(on_release=lambda *a: self._delete_room())
        btns.add_widget(delete)
        outer.add_widget(btns)

        return screen

    def _current_room(self):
        rooms = self.cfg.get("rooms", [])
        if not rooms:
            return None
        idx = max(0, min(self.current_room_index, len(rooms) - 1))
        return rooms[idx]

    def _load_room_form(self):
        room = self._current_room()
        if room is None:
            self.room_label.text = "(sin estancias)"
            return
        rooms = self.cfg.get("rooms", [])
        self.room_label.text = "%d/%d: %s" % (
            self.current_room_index + 1, len(rooms),
            room.get("name", ""))
        for key, ti in self.room_inputs.items():
            value = room.get(key, "")
            ti.text = "" if value is None else str(value)
        self.room_heater_enabled.active = bool(
            room.get("heater_enabled", False))
        self.room_dehumidifier_enabled.active = bool(
            room.get("dehumidifier_enabled", False))
        self.room_heating_type.text = room.get("heating_type", "") or ""
        self.room_windows_open.active = bool(room.get("windows_open", False))
        manual = room.get("window_airflow_m3_h")
        self.room_manual_flow.text = "" if manual is None else str(manual)

    def _collect_room_form(self):
        if self._current_room() is None:
            raise ValueError("No hay estancias.")
        data = {}
        for key, ti in self.room_inputs.items():
            text = ti.text.strip()
            if key == "name":
                if not text:
                    raise ValueError("El nombre no puede estar vacío.")
                data[key] = text
            elif key == "people":
                data[key] = int(read_float(text, 0))
            elif key in ROOM_FALLBACK_KEYS:
                # None = usar el valor global
                data[key] = None if text == "" else read_float(text, 0.0)
            else:
                data[key] = read_float(text, 0.0)
        data["heater_enabled"] = bool(self.room_heater_enabled.active)
        data["dehumidifier_enabled"] = bool(self.room_dehumidifier_enabled.active)
        ht = self.room_heating_type.text.strip()
        data["heating_type"] = ht if ht else None
        data["windows_open"] = bool(self.room_windows_open.active)
        manual = self.room_manual_flow.text.strip()
        data["window_airflow_m3_h"] = (
            None if manual == "" else read_float(manual, 0.0))
        data["window_groups"] = list(
            self._current_room().get("window_groups", []) or [])

        for i, other in enumerate(self.cfg.get("rooms", [])):
            if i == self.current_room_index:
                continue
            if (other.get("name", "").lower() == data["name"].lower()):
                raise ValueError("Ya existe una estancia con ese nombre.")

        if data["height"] <= 0 or data["floor_area"] <= 0:
            raise ValueError("Altura y superficie deben ser positivas.")
        if not 0 <= data["wind_factor"] <= 1:
            raise ValueError("Factor de viento entre 0 y 1.")
        if not 0 < data["window_discharge_coefficient"] <= 1:
            raise ValueError("Coef. descarga entre 0 y 1.")
        return data

    def _save_room(self, silent):
        try:
            data = self._collect_room_form()
        except Exception as exc:
            if not silent:
                show_popup("Estancia", str(exc))
            return False
        old = self.cfg["rooms"][self.current_room_index]
        old_name = old.get("name")
        new_name = data["name"]
        self.cfg["rooms"][self.current_room_index] = data
        if old_name != new_name:
            for conn in self.cfg.get("connections", []):
                if conn.get("room_a") == old_name:
                    conn["room_a"] = new_name
                if conn.get("room_b") == old_name:
                    conn["room_b"] = new_name
            self._refresh_connections_list()
            names = ["TODA LA VIVIENDA"] + [
                r.get("name", "") for r in self.cfg.get("rooms", [])]
            self.sim_room_choice.values = names
        return True

    def _nav_room(self, delta):
        if not self._save_room(silent=True):
            show_popup("Estancia", "Corrige los datos antes de continuar.")
            return
        rooms = self.cfg.get("rooms", [])
        new_idx = self.current_room_index + delta
        if 0 <= new_idx < len(rooms):
            self.current_room_index = new_idx
            self._load_room_form()

    def _add_room(self):
        if not self._save_room(silent=True):
            show_popup("Estancia", "Corrige los datos antes de continuar.")
            return
        new_room = {
            "name": "NUEVA_%d" % (len(self.cfg["rooms"]) + 1),
            "height": 2.6, "floor_area": 15.0,
            "window_area": 0.0, "window_u": 2.4,
            "wall_area": 20.0, "wall_u": 1.1,
            "roof_area": 0.0, "roof_u": 0.85,
            "floor_exposed_area": 0.0, "floor_u": 1.6,
            "air_changes_h": self.cfg.get("air_changes_h", 0.35),
            "thermal_mass_j_m2k": self.cfg.get(
                "thermal_mass_j_m2k", 100000.0),
            "people": 0, "internal_gain_w": 0.0,
            # Equipos: sin habilitar por defecto
            "heater_enabled": False,
            "heater_kw": 0.0,
            "heating_type": None,
            "dehumidifier_enabled": False,
            "dehumidifier_l_day": 0.0,
            "dehumidifier_power_kw": 0.0,
            "windows_open": False,
            "window_opening_area_m2": 0.0,
            "window_airflow_m3_h": None,
            "window_groups": [],
            "wind_factor": 0.60,
            "window_discharge_coefficient": 0.60,
        }
        self.cfg["rooms"].append(new_room)
        self.current_room_index = len(self.cfg["rooms"]) - 1
        self._load_room_form()
        names = ["TODA LA VIVIENDA"] + [
            r.get("name", "") for r in self.cfg.get("rooms", [])]
        self.sim_room_choice.values = names

    def _delete_room(self):
        if len(self.cfg.get("rooms", [])) <= 1:
            show_popup("Estancias", "Debe quedar al menos una.")
            return
        room = self._current_room()
        name = room.get("name")
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        content.add_widget(Label(text="¿Eliminar '%s'?" % name))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        yes = Button(text="Sí")
        no = Button(text="No")
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title="Eliminar", content=content,
                      size_hint=(0.8, None), height=dp(180))
        def do_delete(*a):
            popup.dismiss()
            del self.cfg["rooms"][self.current_room_index]
            self.cfg["connections"] = [
                c for c in self.cfg.get("connections", [])
                if c.get("room_a") != name and c.get("room_b") != name]
            self.current_room_index = max(0, self.current_room_index - 1)
            self._load_room_form()
            self._refresh_connections_list()
            names = ["TODA LA VIVIENDA"] + [
                r.get("name", "") for r in self.cfg.get("rooms", [])]
            self.sim_room_choice.values = names
        no.bind(on_release=lambda *a: popup.dismiss())
        yes.bind(on_release=do_delete)
        popup.open()

    # ================================================= CONNECTIONS

    def _build_connections_screen(self):
        screen = Screen(name='connections')
        outer = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        screen.add_widget(outer)

        scroll = ScrollView(size_hint_y=1)
        self.connections_list = BoxLayout(orientation='vertical',
                                            size_hint_y=None, spacing=dp(2),
                                            padding=dp(4))
        self.connections_list.bind(
            minimum_height=self.connections_list.setter('height'))
        scroll.add_widget(self.connections_list)
        outer.add_widget(scroll)

        add = Button(text="Añadir conexión", size_hint_y=None, height=dp(48))
        add.bind(on_release=lambda *a: self._add_connection())
        outer.add_widget(add)

        self._refresh_connections_list()
        return screen

    def _refresh_connections_list(self):
        self.connections_list.clear_widgets()
        conns = self.cfg.get("connections", [])
        if not conns:
            self.connections_list.add_widget(
                Label(text="(sin conexiones)", size_hint_y=None,
                      height=dp(40)))
            return
        for idx, conn in enumerate(conns):
            row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(4))
            info = "%s ↔ %s [%s]" % (
                conn.get("room_a", ""), conn.get("room_b", ""),
                conn.get("type", ""))
            row.add_widget(Label(text=info, size_hint_x=0.7,
                                  halign='left', valign='middle',
                                  text_size=(dp(260), dp(60))))
            edit = Button(text="Editar", size_hint_x=0.15)
            edit.bind(on_release=lambda b, i=idx: self._edit_connection(i))
            row.add_widget(edit)
            dele = Button(text="X", size_hint_x=0.15)
            dele.bind(on_release=lambda b, i=idx: self._delete_connection(i))
            row.add_widget(dele)
            self.connections_list.add_widget(row)

    def _connection_dialog(self, idx=None):
        original = {}
        if idx is not None and 0 <= idx < len(self.cfg.get("connections", [])):
            original = copy.deepcopy(self.cfg["connections"][idx])

        room_names = [r.get("name", "") for r in self.cfg.get("rooms", [])]
        if len(room_names) < 2:
            show_popup("Conexiones", "Necesitas al menos 2 estancias.")
            return

        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))
        scroll = ScrollView(size_hint_y=1)
        form = BoxLayout(orientation='vertical', size_hint_y=None,
                          spacing=dp(2))
        form.bind(minimum_height=form.setter('height'))
        scroll.add_widget(form)
        content.add_widget(scroll)

        room_a = Spinner(text=original.get("room_a", room_names[0]),
                          values=room_names, size_hint_y=None, height=dp(44))
        form.add_widget(make_row("Estancia A", room_a))
        room_b = Spinner(text=original.get("room_b", room_names[1]),
                          values=room_names, size_hint_y=None, height=dp(44))
        form.add_widget(make_row("Estancia B", room_b))
        type_w = Spinner(
            text=original.get("type", "open"),
            values=("open", "ajar", "closed_gap", "custom"),
            size_hint_y=None, height=dp(44))
        form.add_widget(make_row("Tipo", type_w))
        airflow_ti = make_text(
            original.get("airflow_m3_h",
                          original.get("flow_m3_h", "")) or "",
            numeric=True)
        form.add_widget(make_row(
            "Caudal (m³/h, solo custom)", airflow_ti))

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        ok = Button(text="Aceptar")
        cancel = Button(text="Cancelar")
        btns.add_widget(ok)
        btns.add_widget(cancel)
        content.add_widget(btns)

        popup = Popup(title="Conexión", content=content,
                      size_hint=(0.9, 0.9))
        def accept(*a):
            try:
                a_name = room_a.text
                b_name = room_b.text
                if a_name == b_name:
                    raise ValueError("Deben ser estancias distintas.")
                typ = type_w.text
                data = {"room_a": a_name, "room_b": b_name, "type": typ}
                if typ == "custom":
                    data["airflow_m3_h"] = read_float(airflow_ti.text, 0.0)
                if idx is None:
                    self.cfg.setdefault("connections", []).append(data)
                else:
                    self.cfg["connections"][idx] = data
                popup.dismiss()
                self._refresh_connections_list()
            except Exception as exc:
                show_popup("Conexión", str(exc))
        ok.bind(on_release=accept)
        cancel.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

    def _add_connection(self):
        self._connection_dialog(None)

    def _edit_connection(self, idx):
        self._connection_dialog(idx)

    def _delete_connection(self, idx):
        try:
            del self.cfg["connections"][idx]
            self._refresh_connections_list()
        except Exception:
            pass

    # ================================================= WEATHER (tabla)

    def _build_weather_screen(self):
        screen = Screen(name='weather')
        outer = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        screen.add_widget(outer)

        scroll = ScrollView(size_hint_y=1)
        self.weather_table = GridLayout(cols=6, size_hint_y=None,
                                          spacing=dp(1), padding=dp(2))
        self.weather_table.bind(
            minimum_height=self.weather_table.setter('height'))
        scroll.add_widget(self.weather_table)
        outer.add_widget(scroll)

        self._refresh_weather_table()
        return screen

    def _refresh_weather_table(self):
        self.weather_table.clear_widgets()
        for h in ["Hora", "Text", "HR", "Solar", "Viento", "Dir"]:
            self.weather_table.add_widget(Label(
                text=h, bold=True, font_size=sp(11),
                size_hint_y=None, height=dp(32)))
        for idx, row in enumerate(self.cfg.get("weather", [])):
            btn = Button(text=str(row[0]), font_size=sp(11),
                         size_hint_y=None, height=dp(40))
            btn.bind(on_release=lambda b, i=idx: self._edit_weather_hour(i))
            self.weather_table.add_widget(btn)
            for j in range(1, 6):
                value = row[j] if j < len(row) else 0
                self.weather_table.add_widget(Label(
                    text=str(value), font_size=sp(11),
                    size_hint_y=None, height=dp(40)))

    def _edit_weather_hour(self, idx):
        weather = self.cfg.get("weather", [])
        if not 0 <= idx < len(weather):
            return
        row = weather[idx]
        labels = [
            ("temperature", "Temperatura (°C)"),
            ("rh", "HR (%)"),
            ("solar", "Radiación (W/m²)"),
            ("wind", "Viento (m/s)"),
            ("direction", "Dirección (°)"),
        ]
        values = {
            "temperature": row[1],
            "rh": row[2],
            "solar": row[3],
            "wind": row[4] if len(row) > 4 else 0,
            "direction": row[5] if len(row) > 5 else 0,
        }
        content = BoxLayout(orientation='vertical', padding=dp(8),
                              spacing=dp(2))
        inputs = {}
        for key, label in labels:
            ti = make_text(values[key], numeric=True)
            inputs[key] = ti
            content.add_widget(make_row(label, ti))
        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        ok = Button(text="Aceptar")
        cancel = Button(text="Cancelar")
        btns.add_widget(ok)
        btns.add_widget(cancel)
        content.add_widget(btns)
        popup = Popup(title="Hora %d" % idx, content=content,
                      size_hint=(0.9, 0.85))
        def accept(*a):
            try:
                temp = read_float(inputs["temperature"].text, 0.0)
                rh = read_float(inputs["rh"].text, 0.0)
                solar = read_float(inputs["solar"].text, 0.0)
                wind = read_float(inputs["wind"].text, 0.0)
                direction = read_float(inputs["direction"].text, 0.0)
                if not 0 <= rh <= 100:
                    raise ValueError("HR entre 0 y 100.")
                if solar < 0 or wind < 0:
                    raise ValueError("Solar y viento >= 0.")
                if not 0 <= direction <= 360:
                    raise ValueError("Dirección entre 0 y 360.")
                weather[idx] = [idx, temp, rh, solar, wind, direction]
                popup.dismiss()
                self._refresh_weather_table()
            except Exception as exc:
                show_popup("Meteo", str(exc))
        ok.bind(on_release=accept)
        cancel.bind(on_release=lambda *a: popup.dismiss())
        popup.open()


if __name__ == "__main__":
    SimulatorApp().run()