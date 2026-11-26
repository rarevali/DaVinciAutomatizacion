# -*- coding: utf-8 -*-
"""Módulo dinámico para la asignación de colores por bins del Media Pool.

Escanea exclusivamente los Bins que contienen ficheros multimedia activos,
generando una interfaz gráfica para asignar colores de forma precisa.
"""

import tkinter as tk
from tkinter import messagebox, ttk


class PestañaColores(ttk.Frame):
    """Pestaña de interfaz de usuario para la asignación dinámica de colores por Bins con ficheros."""

    def __init__(
        self,
        parent: tk.Widget,
        callback_logger: callable,
        ejecutor_hilos: callable,
        resolve_instance: object
    ) -> None:
        """Inicializa la pestaña de coloración dinámica y sus dependencias."""
        super().__init__(parent)
        self.logger = callback_logger
        self.ejecutar_hilo = ejecutor_hilos
        self.resolve = resolve_instance

        # Diccionario para almacenar los combobox de cada ruta de Bin
        self.combos_carpetas = {}

        # Construcción visual inicial de la interfaz
        self.construir_interfaz()

    def construir_interfaz(self) -> None:
        """Crea el contenedor principal y los botones de control."""
        self.frame_principal = ttk.LabelFrame(
            self,
            text=" Configuración dinámica de colores por Bins con ficheros ",
            padding=12
        )
        self.frame_principal.pack(fill="both", expand=True, padx=10, pady=10)

        # Etiqueta orientativa inicial
        self.lbl_info = ttk.Label(
            self.frame_principal,
            text="Haz clic en 'Escanear Bins con ficheros' para detectar el contenido."
        )
        self.lbl_info.pack(anchor="w", pady=5)

        # Botón para activar el escaneo automático
        self.btn_escanear = ttk.Button(
            self.frame_principal,
            text="Escanear Bins con ficheros",
            command=lambda: self.ejecutar_hilo(self.escanear_y_construir_controles)
        )
        self.btn_escanear.pack(anchor="w", pady=5)

        # Botón de ejecución final para colorear los clips
        self.btn_run_colors = ttk.Button(
            self,
            text="🎨 Aplicar colores al Media Pool",
            command=lambda: self.ejecutar_hilo(self.proceso_colorear)
        )
        self.btn_run_colors.pack(fill="x", padx=15, pady=10)

    def escanear_y_construir_controles(self) -> None:
        """Escanea los Bins del Media Pool filtrando únicamente los que contienen ficheros."""
        resolve = self.resolve
        if not resolve:
            raise RuntimeError("No se detectó la instancia activa de DaVinci Resolve.")

        current_project = resolve.GetProjectManager().GetCurrentProject()
        if not current_project:
            raise RuntimeError("No hay ningún proyecto abierto en DaVinci Resolve.")

        media_pool = current_project.GetMediaPool()
        root_bin = media_pool.GetRootFolder()

        self.logger(" Escaneando Bins que contienen ficheros multimedia...")
        bins_con_ficheros = {}

        def recolectar_bins_con_clips(current_bin: object, ruta_actual: str) -> None:
            """Recorre los Bins y solo almacena los que tienen clips físicos."""
            nombre_bin = current_bin.GetName()
            ruta_bin = f"{ruta_actual} / {nombre_bin}" if ruta_actual else nombre_bin
            
            # Comprobamos estrictamente si el bin contiene clips
            clips = current_bin.GetClipList() or []
            if clips:
                bins_con_ficheros[ruta_bin] = current_bin

            sub_folders = current_bin.GetSubFolderList() or []
            for sub in sub_folders:
                recolectar_bins_con_clips(sub, ruta_bin)

        recolectar_bins_con_clips(root_bin, "")

        # Actualiza la interfaz gráfica en el hilo principal de Tkinter
        self.after(0, lambda: self._actualizar_interfaz_con_bins(bins_con_ficheros))

    def _actualizar_interfaz_con_bins(self, dict_bins: dict) -> None:
        """Genera un selector exclusivamente para los Bins con ficheros detectados."""
        for widget in self.frame_principal.winfo_children():
            if widget not in (self.lbl_info, self.btn_escanear):
                widget.destroy()

        self.combos_carpetas.clear()

        if not dict_bins:
            ttk.Label(
                self.frame_principal,
                text="No se encontraron Bins que contengan ficheros multimedia."
            ).pack(anchor="w", pady=5)
            return

        self.lbl_info.config(
            text=f"Se han detectado {len(dict_bins)} Bins con ficheros multimedia:"
        )

        resolve_colors = [
            "Orange", "Apricot", "Yellow", "Lime", "Olive", "Green",
            "Teal", "Navy", "Blue", "Purple", "Violet", "Pink", "Tan", "Chocolate"
        ]

        for idx, ruta_bin in enumerate(sorted(dict_bins.keys())):
            fila_frame = ttk.Frame(self.frame_principal)
            fila_frame.pack(fill="x", pady=3)

            # Muestra la ruta lógica del Bin
            lbl_ruta = ttk.Label(fila_frame, text=ruta_bin, width=50, anchor="w")
            lbl_ruta.pack(side="left", padx=5)

            # Selector de color asociado al Bin con ficheros
            combo = ttk.Combobox(fila_frame, values=resolve_colors, state="readonly", width=15)
            combo.set("Yellow" if idx % 2 == 0 else "Blue")
            combo.pack(side="right", padx=5)

            self.combos_carpetas[ruta_bin] = {
                "combo": combo,
                "bin_obj": dict_bins[ruta_bin]
            }

        self.logger(f"Se han generado controles para {len(dict_bins)} Bins con ficheros.")

    def proceso_colorear(self) -> None:
        """Aplica los colores a los clips de los Bins seleccionados."""
        resolve = self.resolve
        if not resolve:
            raise RuntimeError("No se detectó la instancia activa de DaVinci Resolve.")

        current_project = resolve.GetProjectManager().GetCurrentProject()
        if not current_project:
            raise RuntimeError("No hay ningún proyecto abierto en DaVinci Resolve.")

        if not self.combos_carpetas:
            messagebox.showwarning("Atención", "Primero debes escanear los Bins del proyecto.")
            return

        self.logger("Aplicando colores a los clips de los Bins seleccionados...")

        for ruta_bin, datos in self.combos_carpetas.items():
            color_elegido = datos["combo"].get()
            bin_obj = datos["bin_obj"]
            
            clips = bin_obj.GetClipList() or []
            for clip in clips:
                clip.SetClipColor(color_elegido)
                self.logger(
                    f"✔ Clip '{clip.GetName()}' en Bin [{ruta_bin}] "
                    f"coloreado como [{color_elegido}]"
                )

        self.logger("Asignación de colores completada con éxito.")
        messagebox.showinfo("Completado", "Los colores se han aplicado correctamente a los clips.")