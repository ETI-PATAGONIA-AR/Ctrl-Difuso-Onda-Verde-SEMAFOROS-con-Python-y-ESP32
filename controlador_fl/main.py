import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from tkintermapview import TkinterMapView
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import yaml
import time
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import coordinacion  # <<< integración de módulo de coordinación

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class FuzzyTraffic:
    def __init__(self):
        self.vehiculos = ctrl.Antecedent(np.arange(0, 51, 1), 'vehiculos')
        self.detencion = ctrl.Antecedent(np.arange(0, 61, 1), 'detencion')
        self.tiempo_verde = ctrl.Consequent(np.arange(10, 91, 1), 'tiempo_verde')

        self.vehiculos['bajo'] = fuzz.trimf(self.vehiculos.universe, [0, 0, 15])
        self.vehiculos['medio'] = fuzz.trimf(self.vehiculos.universe, [10, 25, 40])
        self.vehiculos['alto'] = fuzz.trimf(self.vehiculos.universe, [35, 50, 50])

        self.detencion['corto'] = fuzz.trimf(self.detencion.universe, [0, 0, 20])
        self.detencion['medio'] = fuzz.trimf(self.detencion.universe, [15, 30, 45])
        self.detencion['largo'] = fuzz.trimf(self.detencion.universe, [40, 60, 60])

        self.tiempo_verde['corto'] = fuzz.trimf(self.tiempo_verde.universe, [10, 10, 30])
        self.tiempo_verde['medio'] = fuzz.trimf(self.tiempo_verde.universe, [25, 45, 65])
        self.tiempo_verde['largo'] = fuzz.trimf(self.tiempo_verde.universe, [60, 90, 90])

        rule1 = ctrl.Rule(self.vehiculos['bajo'] & self.detencion['corto'], self.tiempo_verde['corto'])
        rule2 = ctrl.Rule(self.vehiculos['medio'] | self.detencion['medio'], self.tiempo_verde['medio'])
        rule3 = ctrl.Rule(self.vehiculos['alto'] | self.detencion['largo'], self.tiempo_verde['largo'])

        self.control_system = ctrl.ControlSystem([rule1, rule2, rule3])
        self.fuzzy_controller = ctrl.ControlSystemSimulation(self.control_system)

    def calcular_tiempo(self, vehiculos, detencion):
        self.fuzzy_controller.input['vehiculos'] = vehiculos
        self.fuzzy_controller.input['detencion'] = detencion
        self.fuzzy_controller.compute()
        return max(10, min(90, int(self.fuzzy_controller.output['tiempo_verde'])))


def haversine(lat1, lon1, lat2, lon2):
    R = 6371e3
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class EditorMapaSemaforos(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🚦 Control Semáforos RN3 - Editor Mapa + Onda Verde + ESP")
        self.geometry("1700x950")

        self.fuzzy = FuzzyTraffic()
        self.marcadores_via1 = []         # azul: norte→sur (lat, lon, marker)
        self.marcadores_via2 = []         # rojo: sur→norte (lat, lon, marker)
        self.controladores_esp = []       # lista de dicts: {"id":int,"lat":..,"lon":..,"marker":obj}
        self.via_activa = 1
        self.modo_esp = False             # False = marcar semáforos, True = marcar ESP

        # pila de acciones para undo
        self.undo_stack = []  # cada item: ("V1"/"V2"/"ESP", marker)

        # cargar datos guardados
        self.semaforos_guardados_via1 = []
        self.semaforos_guardados_via2 = []
        self.controladores_esp_guardados = []
        try:
            with open("semaforos_rn3.yaml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.semaforos_guardados_via1 = data.get("via1", [])
            self.semaforos_guardados_via2 = data.get("via2", [])
            self.controladores_esp_guardados = data.get("controladores_esp", [])
        except FileNotFoundError:
            pass

        self.crear_gui()
        self.re_dibujar_todo()

        # diccionario para velocidades manuales por tramo (via, i, j) -> vel_kmh
        self.tramos_vel_manuales = {}

        # binding global para Ctrl+Z
        self.bind_all("<Control-z>", self.deshacer_ultima_accion)

    def crear_gui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_mapa = self.tabview.add("Mapa y Semáforos / ESP")
        self.tab_tiempos = self.tabview.add("Onda Verde / Tiempos")
        self.tab_fuzzy = self.tabview.add("Ajuste Difuso")

        self._crear_tab_mapa()
        self._crear_tab_tiempos()
        self._crear_tab_fuzzy()

    # ---------- TAB MAPA ----------
    def _crear_tab_mapa(self):
        frame_superior = ctk.CTkFrame(self.tab_mapa)
        frame_superior.pack(fill="x", padx=5, pady=5)

        self.entry_buscar = ctk.CTkEntry(
            frame_superior,
            placeholder_text="Buscar dirección (ej: Ruta 3 Comodoro Rivadavia)"
        )
        self.entry_buscar.pack(side="left", padx=5, pady=5, fill="x", expand=True)

        ctk.CTkButton(frame_superior, text="Ir", width=80,
                      command=self.buscar_direccion).pack(side="left", padx=5)
        ctk.CTkButton(frame_superior, text="Centrar RN3",
                      command=self.centrar_rn3).pack(side="left", padx=5)
        ctk.CTkButton(frame_superior, text="Guardar YAML",
                      command=self.guardar_config).pack(side="left", padx=5)

        self.btn_via1 = ctk.CTkButton(frame_superior, text="VÍA 1 (AZUL) N→S",
                                      width=140, command=lambda: self.seleccionar_via(1))
        self.btn_via1.pack(side="left", padx=5)

        self.btn_via2 = ctk.CTkButton(frame_superior, text="VÍA 2 (ROJO) S→N",
                                      width=140, command=lambda: self.seleccionar_via(2))
        self.btn_via2.pack(side="left", padx=5)

        self.btn_esp = ctk.CTkButton(frame_superior, text="MODO ESP OFF",
                                     width=140, command=self.toggle_modo_esp)
        self.btn_esp.pack(side="left", padx=5)

        self.label_estado = ctk.CTkLabel(
            self.tab_mapa,
            text="Modo semáforos. Vía activa: 1 (AZUL, N→S). Click izquierdo = semáforo de la vía seleccionada."
        )
        self.label_estado.pack(pady=5)

        frame_mapa = ctk.CTkFrame(self.tab_mapa)
        frame_mapa.pack(fill="both", expand=True, padx=5, pady=5)

        self.map_widget = TkinterMapView(frame_mapa, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)

        # self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=es&x={x}&y={y}&z={z}&s=Ga", max_zoom=19)
        self.centrar_rn3()
        self.map_widget.add_left_click_map_command(self.click_mapa)

        self.seleccionar_via(1)

    def re_dibujar_todo(self):
        # semáforos via1
        for idx, p in enumerate(self.semaforos_guardados_via1):
            lat, lon = p["lat"], p["lon"]
            marker = self.map_widget.set_marker(
                lat, lon,
                text=f"V1-{idx}",
                marker_color_outside="#00aaff"
            )
            self.marcadores_via1.append((lat, lon, marker))

        # semáforos via2
        for idx, p in enumerate(self.semaforos_guardados_via2):
            lat, lon = p["lat"], p["lon"]
            marker = self.map_widget.set_marker(
                lat, lon,
                text=f"V2-{idx}",
                marker_color_outside="#ff4444"
            )
            self.marcadores_via2.append((lat, lon, marker))

        # controladores ESP
        for ctrl in self.controladores_esp_guardados:
            cid = ctrl["id"]
            lat, lon = ctrl["lat"], ctrl["lon"]
            marker = self.map_widget.set_marker(
                lat, lon,
                text=f"ESP-{cid}",
                marker_color_outside="#aa55ff"
            )
            self.controladores_esp.append(
                {"id": cid, "lat": lat, "lon": lon, "marker": marker}
            )

        self.actualizar_resumen_tiempos()

    def toggle_modo_esp(self):
        self.modo_esp = not self.modo_esp
        if self.modo_esp:
            self.btn_esp.configure(fg_color="#aa55ff", text="MODO ESP ON")
            self.label_estado.configure(
                text="Modo ESP: Click izquierdo = marcar controlador ESP (violeta). Vías azul/rojo deshabilitadas."
            )
        else:
            self.btn_esp.configure(fg_color="#444444", text="MODO ESP OFF")
            self.label_estado.configure(
                text=f"Modo semáforos. Vía activa: {self.via_activa} ({'AZUL N→S' if self.via_activa==1 else 'ROJO S→N'}). Click = semáforo."
            )

    def seleccionar_via(self, via):
        self.via_activa = via
        if via == 1:
            self.btn_via1.configure(fg_color="#1f6aa5")
            self.btn_via2.configure(fg_color="#444444")
        else:
            self.btn_via2.configure(fg_color="#a51f3b")
            self.btn_via1.configure(fg_color="#444444")

        if not self.modo_esp:
            self.label_estado.configure(
                text=f"Modo semáforos. Vía activa: {via} ({'AZUL N→S' if via==1 else 'ROJO S→N'}). Click = semáforo."
            )

    def centrar_rn3(self):
        self.map_widget.set_position(-45.868, -67.485)
        self.map_widget.set_zoom(13)

    def buscar_direccion(self):
        texto = self.entry_buscar.get().strip()
        if not texto:
            return
        try:
            self.map_widget.set_address(texto)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo buscar dirección:\n{e}")

    def click_mapa(self, coords):
        lat, lon = coords
        if self.modo_esp:
            self.agregar_controlador_esp(lat, lon)
        else:
            self.agregar_semaforo(lat, lon)

    def agregar_semaforo(self, lat, lon):
        if self.via_activa == 1:
            marker = self.map_widget.set_marker(
                lat, lon,
                text=f"V1-{len(self.marcadores_via1)}",
                marker_color_outside="#00aaff"
            )
            self.marcadores_via1.append((lat, lon, marker))
            self.undo_stack.append(("V1", marker))
        else:
            marker = self.map_widget.set_marker(
                lat, lon,
                text=f"V2-{len(self.marcadores_via2)}",
                marker_color_outside="#ff4444"
            )
            self.marcadores_via2.append((lat, lon, marker))
            self.undo_stack.append(("V2", marker))
        self.actualizar_resumen_tiempos()

    def agregar_controlador_esp(self, lat, lon):
        nuevos_ids = [c["id"] for c in self.controladores_esp]
        next_id = max(nuevos_ids) + 1 if nuevos_ids else 1
        marker = self.map_widget.set_marker(
            lat, lon,
            text=f"ESP-{next_id}",
            marker_color_outside="#aa55ff"
        )
        self.controladores_esp.append(
            {"id": next_id, "lat": lat, "lon": lon, "marker": marker}
        )
        self.undo_stack.append(("ESP", marker))
        messagebox.showinfo("Controlador ESP",
                            f"Controlador ESP-{next_id} agregado en lat={lat:.6f}, lon={lon:.6f}.")

    def deshacer_ultima_accion(self, event=None):
        """
        Undo simple: elimina el último semáforo o ESP agregado.
        Ctrl+Z está bindeado a este método.
        """
        if not self.undo_stack:
            return

        tipo, marker = self.undo_stack.pop()

        if tipo == "V1":
            for idx in range(len(self.marcadores_via1) - 1, -1, -1):
                lat, lon, m = self.marcadores_via1[idx]
                if m is marker:
                    self.marcadores_via1.pop(idx)
                    break
        elif tipo == "V2":
            for idx in range(len(self.marcadores_via2) - 1, -1, -1):
                lat, lon, m = self.marcadores_via2[idx]
                if m is marker:
                    self.marcadores_via2.pop(idx)
                    break
        elif tipo == "ESP":
            for idx in range(len(self.controladores_esp) - 1, -1, -1):
                if self.controladores_esp[idx]["marker"] is marker:
                    self.controladores_esp.pop(idx)
                    break

        try:
            marker.delete()
        except Exception:
            pass

        self.actualizar_resumen_tiempos()

    def guardar_config(self):
        data = {
            "via1": [{"lat": lat, "lon": lon} for lat, lon, _ in self.marcadores_via1],
            "via2": [{"lat": lat, "lon": lon} for lat, lon, _ in self.marcadores_via2],
            "controladores_esp": [
                {"id": c["id"], "lat": c["lat"], "lon": c["lon"]} for c in self.controladores_esp
            ],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open("semaforos_rn3.yaml", "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
        messagebox.showinfo("Guardado", "Datos guardados en semaforos_rn3.yaml")

    # ---------- TAB ONDA VERDE / TIEMPOS ----------
    def _crear_tab_tiempos(self):
        top = ctk.CTkFrame(self.tab_tiempos)
        top.pack(fill="x", padx=10, pady=10)

        self.label_resumen_tiempos = ctk.CTkLabel(
            top, text="Configura onda verde por vía. Vía 1 = azul (N→S), Vía 2 = rojo (S→N)."
        )
        self.label_resumen_tiempos.pack(side="left", padx=5)

        # label para mostrar C y B por vía
        self.label_coord = ctk.CTkLabel(
            top, text="Ciclo/Banda: aún sin calcular."
        )
        self.label_coord.pack(side="right", padx=5)

        form = ctk.CTkFrame(self.tab_tiempos)
        form.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(form, text="Vía:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.combo_via_tramo = ctk.CTkComboBox(
            form, values=["Vía 1 (AZUL, N→S)", "Vía 2 (ROJO, S→N)"], width=180
        )
        self.combo_via_tramo.set("Vía 1 (AZUL, N→S)")
        self.combo_via_tramo.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form, text="Semáforo inicio (i):").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.entry_idx_i = ctk.CTkEntry(form, width=60, placeholder_text="i")
        self.entry_idx_i.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(form, text="Semáforo fin (j):").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.entry_idx_j = ctk.CTkEntry(form, width=60, placeholder_text="j")
        self.entry_idx_j.grid(row=0, column=5, padx=5, pady=5)

        ctk.CTkLabel(form, text="Velocidad tramo (km/h):").grid(row=0, column=6, padx=5, pady=5, sticky="e")
        self.entry_vel_tramo = ctk.CTkEntry(form, width=80, placeholder_text="km/h")
        self.entry_vel_tramo.grid(row=0, column=7, padx=5, pady=5)

        ctk.CTkButton(form, text="Agregar/Actualizar tramo",
                      command=self.agregar_tramo_manual).grid(row=0, column=8, padx=10, pady=5)

        form2 = ctk.CTkFrame(self.tab_tiempos)
        form2.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(form2, text="Velocidad global mín (km/h):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.entry_vel_min = ctk.CTkEntry(form2, width=80, placeholder_text="Min")
        self.entry_vel_min.insert(0, "30")
        self.entry_vel_min.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form2, text="Velocidad global máx (km/h):").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.entry_vel_max = ctk.CTkEntry(form2, width=80, placeholder_text="Max")
        self.entry_vel_max.insert(0, "60")
        self.entry_vel_max.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkButton(form2, text="Calcular Onda Verde (toda la vía)",
                      command=self.calcular_onda_verde).grid(row=0, column=4, padx=10, pady=5)

        ctk.CTkButton(form2, text="Calcular coordinación avanzada",
                      fg_color="#2b9348",
                      command=self.calcular_coordinacion_avanzada).grid(row=0, column=5, padx=10, pady=5)

        bottom = ctk.CTkFrame(self.tab_tiempos)
        bottom.pack(fill="both", expand=True, padx=10, pady=10)

        # columnas ampliadas: via, i, j, dist_m, vel_kmh, offset_s, t_seg
        self.tree = ttk.Treeview(
            bottom,
            columns=("via", "i", "j", "dist_m", "vel_kmh", "offset_s", "t_seg"),
            show="headings",
            height=18
        )
        self.tree.heading("via", text="Vía")
        self.tree.heading("i", text="Semáforo i")
        self.tree.heading("j", text="Semáforo j")
        self.tree.heading("dist_m", text="Distancia (m)")
        self.tree.heading("vel_kmh", text="Vel (km/h)")
        self.tree.heading("offset_s", text="Offset Oi (s)")
        self.tree.heading("t_seg", text="Tiempo base (s)")

        self.tree.column("via", width=80)
        self.tree.column("i", width=80)
        self.tree.column("j", width=80)
        self.tree.column("dist_m", width=110)
        self.tree.column("vel_kmh", width=100)
        self.tree.column("offset_s", width=110)
        self.tree.column("t_seg", width=120)

        self.tree.pack(fill="both", expand=True)

    def actualizar_resumen_tiempos(self):
        n1 = len(self.marcadores_via1)
        n2 = len(self.marcadores_via2)
        n_esp = len(self.controladores_esp)
        self.label_resumen_tiempos.configure(
            text=f"Vía 1 (AZUL N→S): {n1} semáforos | Vía 2 (ROJO S→N): {n2} semáforos | Controladores ESP: {n_esp}"
        )

    def agregar_tramo_manual(self):
        via_sel = self.combo_via_tramo.get()
        via_id = "V1" if "Vía 1" in via_sel else "V2"
        try:
            i = int(self.entry_idx_i.get())
            j = int(self.entry_idx_j.get())
            vel = float(self.entry_vel_tramo.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Índices i, j o velocidad inválidos.")
            return

        if vel < 5 or vel > 110:
            messagebox.showerror("Error", "Velocidad fuera de rango (5–110 km/h).")
            return

        self.tramos_vel_manuales[(via_id, i, j)] = vel
        messagebox.showinfo(
            "Tramo guardado",
            f"Vía {via_id}: Semáforo {i} → {j} a {vel:.1f} km/h."
        )

    def calcular_onda_verde(self):
        via_sel = self.combo_via_tramo.get()
        if "Vía 1" in via_sel:
            marcadores = self.marcadores_via1
            via_id = "V1"
        else:
            marcadores = self.marcadores_via2
            via_id = "V2"

        if len(marcadores) < 2:
            messagebox.showwarning(
                "Atención",
                "Necesitás al menos 2 semáforos en la vía seleccionada."
            )
            return

        try:
            vel_min = float(self.entry_vel_min.get().replace(",", "."))
            vel_max = float(self.entry_vel_max.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Velocidades globales inválidas.")
            return

        vel_min = max(5.0, min(vel_min, vel_max))
        vel_max = max(vel_min, min(vel_max, 110.0))

        sorted_markers = sorted(marcadores, key=lambda x: x[1])

        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx in range(len(sorted_markers) - 1):
            lat1, lon1, _ = sorted_markers[idx]
            lat2, lon2, _ = sorted_markers[idx + 1]
            d_m = haversine(lat1, lon1, lat2, lon2)

            vel_tramo = self.tramos_vel_manuales.get((via_id, idx, idx + 1), vel_max)
            vel_tramo = max(vel_min, min(vel_tramo, vel_max))

            v_ms = vel_tramo * 1000.0 / 3600.0
            t_seg = d_m / v_ms if v_ms > 0 else 999

            self.tree.insert(
                "",
                "end",
                values=(
                    via_id,
                    idx,
                    idx + 1,
                    int(d_m),
                    round(vel_tramo, 1),
                    round(t_seg, 1),  # offset_s ~ tiempo de viaje a Vd
                    int(t_seg)
                )
            )

    def calcular_coordinacion_avanzada(self):
        """
        Usa coordinacion.generar_plan_global para calcular D_i, Vd, O_i, ciclo C y banda B
        para ambas vías, en base a los marcadores y tramos definidos en la GUI.
        """
        via1_semaforos = []
        for idx, (lat, lon, _) in enumerate(sorted(self.marcadores_via1, key=lambda x: x[1])):
            via1_semaforos.append({"id": idx, "lat": lat, "lon": lon})

        via2_semaforos = []
        for idx, (lat, lon, _) in enumerate(sorted(self.marcadores_via2, key=lambda x: x[1])):
            via2_semaforos.append({"id": idx, "lat": lat, "lon": lon})

        if len(via1_semaforos) < 2 and len(via2_semaforos) < 2:
            messagebox.showwarning("Atención", "Necesitás al menos 2 semáforos en alguna vía para coordinar.")
            return

        try:
            vel_min = float(self.entry_vel_min.get().replace(",", "."))
            vel_max = float(self.entry_vel_max.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Velocidades globales inválidas.")
            return

        vel_min = max(5.0, min(vel_min, vel_max))
        vel_max = max(vel_min, min(vel_max, 110.0))
        vd_default_via1 = vel_max
        vd_default_via2 = vel_max

        via1_tramos_vd = []
        via2_tramos_vd = []
        for (via_id, i, j), vel in self.tramos_vel_manuales.items():
            if via_id == "V1":
                via1_tramos_vd.append({"i_inicio": i, "i_fin": j, "vd_kmh": vel})
            else:
                via2_tramos_vd.append({"i_inicio": i, "i_fin": j, "vd_kmh": vel})

        plan = coordinacion.generar_plan_global(
            via1_semaforos=via1_semaforos,
            via2_semaforos=via2_semaforos,
            via1_tramos_vd=via1_tramos_vd,
            via2_tramos_vd=via2_tramos_vd,
            vd_default_via1_kmh=vd_default_via1,
            vd_default_via2_kmh=vd_default_via2
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        texto_coord = []

        for via_key in ("V1", "V2"):
            p = plan.get(via_key)
            if not p:
                continue
            ciclo = p["ciclo_base_s"]
            banda = p["banda_objetivo_s"]
            texto_coord.append(f"{via_key}: C≈{ciclo:.1f}s, B≈{banda:.1f}s")

            for t in p["tramos"]:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        via_key,
                        t["i"],
                        t["j"],
                        int(t["dist_m"]),
                        round(t["vd_kmh"], 1),
                        round(t["offset_s"], 1),
                        int(t["tiempo_viaje_s"])
                    )
                )

        if texto_coord:
            self.label_coord.configure(text=" | ".join(texto_coord))
        else:
            self.label_coord.configure(text="Ciclo/Banda: sin datos suficientes.")

    # ---------- TAB AJUSTE DIFUSO ----------
    def _crear_tab_fuzzy(self):
        frame_top = ctk.CTkFrame(self.tab_fuzzy)
        frame_top.pack(fill="x", padx=10, pady=10)

        self.label_fuzzy = ctk.CTkLabel(
            frame_top,
            text="Ajuste dinámico (lógica difusa) sobre tiempos base de onda verde."
        )
        self.label_fuzzy.pack(side="left", padx=5)

        ctk.CTkButton(
            frame_top, text="Simular Ajuste Difuso",
            command=self.simular_ajuste_difuso
        ).pack(side="left", padx=10)

        frame_plot = ctk.CTkFrame(self.tab_fuzzy)
        frame_plot.pack(fill="both", expand=True, padx=10, pady=10)

        self.fig_fuzzy, self.ax_fuzzy = plt.subplots(figsize=(10, 4))
        self.canvas_fuzzy = FigureCanvasTkAgg(self.fig_fuzzy, master=frame_plot)
        self.canvas_fuzzy.get_tk_widget().pack(fill="both", expand=True)

    def simular_ajuste_difuso(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning(
                "Atención",
                "Primero calculá la onda verde o la coordinación avanzada en la solapa 'Onda Verde / Tiempos'."
            )
            return

        tiempos_base = []
        tiempos_ajust = []
        for item in items:
            vals = self.tree.item(item, "values")
            t_seg = float(vals[6])  # columna Tiempo base (s)
            tiempos_base.append(t_seg)
            veh = min(50, int(t_seg / 2))
            det = min(60, max(5, int(70 - t_seg)))
            t_new = self.fuzzy.calcular_tiempo(veh, det)
            tiempos_ajust.append(t_new)

        idx = np.arange(len(tiempos_base))
        self.ax_fuzzy.clear()
        self.ax_fuzzy.bar(idx - 0.2, tiempos_base, width=0.4, label="Onda verde base")
        self.ax_fuzzy.bar(idx + 0.2, tiempos_ajust, width=0.4, label="Ajuste difuso", color="#ff8844")
        self.ax_fuzzy.set_xlabel("Tramo")
        self.ax_fuzzy.set_ylabel("Tiempo verde (s)")
        self.ax_fuzzy.set_title("Ajuste de tiempos por lógica difusa (demo)")
        self.ax_fuzzy.grid(True, alpha=0.3)
        self.ax_fuzzy.legend()
        self.canvas_fuzzy.draw()


if __name__ == "__main__":
    app = EditorMapaSemaforos()
    app.mainloop()