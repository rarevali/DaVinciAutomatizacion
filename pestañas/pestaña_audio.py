# -*- coding: utf-8 -*-
"""Módulo para la configuración y normalización inteligente de audio.

Gestiona el análisis de niveles de sonoridad (LUFS) mediante FFmpeg,
la normalización automática de pistas en la línea de tiempo activa de 
DaVinci Resolve según diferentes estándares (YouTube, TV, Cine) y la
generación de informes en formato CSV con marcado de errores en clips.
"""

from pathlib import Path
import subprocess
import csv
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


class PestañaAudio(ttk.Frame):
    """Pestaña de interfaz de usuario para el control, normalización

    y auditoría de sonoridad en los elementos de audio de la secuencia.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callback_logger: callable,
        ejecutor_hilos: callable,
        resolve_instance: object,
    ) -> None:
        """Inicializa la pestaña de gestión de audio y sus dependencias."""
        super().__init__(parent)
        self.logger = callback_logger
        self.ejecutar_hilo = ejecutor_hilos
        self.resolve = resolve_instance
        self.construir_interfaz()

    def construir_interfaz(self) -> None:
        """Crea el contenedor principal y los elementos visuales de control."""
        frame = ttk.LabelFrame(
            self,
            text=" Configuración y normalización inteligente de audio ",
            padding=10,
        )
        frame.pack(fill="x", padx=10, pady=5)

        # Selección de perfil estándar de sonoridad
        ttk.Label(frame, text="Estándar / Perfil:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.audio_profiles = [
            "YouTube / Podcast (-14 dB)",
            "Televisión / Broadcast (-23 dB)",
            "Cine (-24 dB)",
            "Personalizado (indicar valor)",
        ]
        self.combo_audio_profile = ttk.Combobox(
            frame, values=self.audio_profiles, state="readonly", width=30
        )
        self.combo_audio_profile.current(0)
        self.combo_audio_profile.grid(
            row=0, column=1, columnspan=2, sticky="w", padx=5, pady=5
        )
        self.combo_audio_profile.bind(
            "<<ComboboxSelected>>", self._cambiar_perfil_audio
        )

        # Campo de objetivo en LUFS
        ttk.Label(frame, text="Objetivo (LUFS):").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.entry_gain = ttk.Entry(frame, width=15)
        self.entry_gain.insert(0, "-14.0")
        self.entry_gain.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Contenedor de botones de acción
        btn_action_frame = ttk.Frame(frame)
        btn_action_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

        # Botón para normalizar la timeline activa
        self.btn_run_audio = ttk.Button(
            btn_action_frame,
            text="🎚️ Normalizar timeline inteligente",
            command=lambda: self.ejecutar_hilo(self.proceso_normalizar),
        )
        self.btn_run_audio.pack(side="left", fill="x", expand=True, padx=2)

        # Botón para exportar informe y marcar errores
        self.btn_run_lufs = ttk.Button(
            btn_action_frame,
            text="📊 Exportar informe LUFS y marcar errores",
            command=lambda: self.ejecutar_hilo(self.proceso_informe_lufs),
        )
        self.btn_run_lufs.pack(side="left", fill="x", expand=True, padx=2)

    def _cambiar_perfil_audio(self, event: object) -> None:
        """Actualiza automáticamente el valor objetivo LUFS en función

        del perfil estándar seleccionado en el menú desplegable.
        """
        sel = self.combo_audio_profile.get()
        if "YouTube" in sel:
            val = "-14.0"
        elif "Televisión" in sel:
            val = "-23.0"
        elif "Cine" in sel:
            val = "-24.0"
        else:
            return
        self.entry_gain.delete(0, tk.END)
        self.entry_gain.insert(0, val)

    def _verificar_ffmpeg(self) -> bool:
        """Comprueba si la utilidad FFmpeg se encuentra instalada

        y accesible en el entorno del sistema operativo.
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except Exception:
            return False

    def proceso_normalizar(self) -> None:
        """Analiza los niveles de audio de la secuencia activa, procesa

        los ficheros mediante FFmpeg y reemplaza los clips normalizados.
        """
        if not self._verificar_ffmpeg():
            raise RuntimeError("Se requiere 'FFmpeg' instalado en el sistema.")

        resolve = self.resolve
        if not resolve:
            raise RuntimeError(
                "No se detectó la instancia activa de DaVinci Resolve."
            )
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("No hay ningún proyecto abierto.")
        timeline = project.GetCurrentTimeline()
        if not timeline:
            raise RuntimeError("No hay ninguna timeline activa seleccionada.")

        target_lufs = float(self.entry_gain.get().strip())
        track_count = timeline.GetTrackCount("audio")
        total_adjusted = 0

        self.logger(
            f"🎚️ Analizando y normalizando timeline: {timeline.GetName()}"
        )

        for track_idx in range(1, track_count + 1):
            audio_items = timeline.GetItemsInTrack("audio", track_idx) or {}
            for _, timeline_item in audio_items.items():
                if not timeline_item:
                    continue
                media_item = timeline_item.GetMediaPoolItem()
                if not media_item:
                    continue
                file_path = media_item.GetClipProperty("File Path")
                if not file_path or not Path(file_path).exists():
                    continue

                orig_path = Path(file_path)
                if "_norm" in orig_path.stem:
                    continue

                probe_cmd = [
                    "ffmpeg",
                    "-i",
                    str(orig_path),
                    "-af",
                    "ebur128=framelog=verbose",
                    "-f",
                    "null",
                    "-",
                ]
                res = subprocess.run(probe_cmd, capture_output=True, text=True)
                match = re.search(
                    r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", res.stderr
                )
                if not match:
                    continue

                current_lufs = float(match.group(1))
                gain_adj = round(target_lufs - current_lufs, 2)
                if abs(gain_adj) < 0.2:
                    continue

                norm_out = (
                    orig_path.parent
                    / f"{orig_path.stem}_norm{orig_path.suffix}"
                )
                if norm_out.exists():
                    try:
                        if media_item.ReplaceClip(str(norm_out)):
                            total_adjusted += 1
                    except Exception:
                        pass
                    continue

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(orig_path),
                    "-af",
                    f"volume={gain_adj}dB",
                    str(norm_out),
                ]
                if (
                    subprocess.run(cmd, capture_output=True, text=True).returncode
                    == 0
                ):
                    try:
                        if media_item.ReplaceClip(str(norm_out)):
                            total_adjusted += 1
                    except Exception:
                        pass

        self.logger(
            f" Normalización completada. Clips actualizados: {total_adjusted}"
        )
        messagebox.showinfo(
            "Completado",
            f"Normalización finalizada. Clips ajustados: {total_adjusted}",
        )

    def proceso_informe_lufs(self) -> None:
        """Audita los niveles de sonoridad de la secuencia, exporta

        un informe detallado en CSV y añade marcas de color en los clips erróneos.
        """
        csv_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not csv_path:
            return
        if not self._verificar_ffmpeg():
            raise RuntimeError(
                "Se requiere 'FFmpeg' instalado en el sistema."
            )

        resolve = self.resolve
        if not resolve:
            raise RuntimeError(
                "No se detectó la instancia activa de DaVinci Resolve."
            )
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("No hay ningún proyecto abierto.")
        timeline = project.GetCurrentTimeline()
        if not timeline:
            raise RuntimeError("No hay ninguna timeline activa.")

        target_lufs = float(self.entry_gain.get().strip())
        track_count = timeline.GetTrackCount("audio")
        report = []
        evaluated = 0

        for track_idx in range(1, track_count + 1):
            items = timeline.GetItemsInTrack("audio", track_idx) or {}
            for _, item in items.items():
                if not item:
                    continue
                media_item = item.GetMediaPoolItem()
                if not media_item:
                    continue
                fpath = media_item.GetClipProperty("File Path")
                if not fpath or not Path(fpath).exists():
                    continue

                res = subprocess.run(
                    [
                        "ffmpeg",
                        "-i",
                        fpath,
                        "-af",
                        "ebur128=framelog=verbose",
                        "-f",
                        "null",
                        "-",
                    ],
                    capture_output=True,
                    text=True,
                )
                lufs_match = re.search(
                    r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", res.stderr
                )
                peak_match = re.search(
                    r"LRA low:\s+[-\d\.]+\s+High:\s+[-\d\.]+\s+Peak:\s+([-\d\.]+)\s+dBFS",
                    res.stderr,
                )

                lufs = float(lufs_match.group(1)) if lufs_match else -70.0
                peak = float(peak_match.group(1)) if peak_match else 0.0

                status = "Cumple"
                if lufs > (target_lufs + 1.0):
                    status = "Excesivo"
                    item.AddMarker(
                        item.GetStart(),
                        "Red",
                        "LUFS excesivo",
                        f"Mide {lufs} LUFS",
                        1,
                    )
                elif lufs < (target_lufs - 1.0):
                    status = "Deficiente"
                    item.AddMarker(
                        item.GetStart(),
                        "Yellow",
                        "LUFS deficiente",
                        f"Mide {lufs} LUFS",
                        1,
                    )

                report.append({
                    "Pista": f"A{track_idx}",
                    "Clip": media_item.GetName(),
                    "LUFS": lufs,
                    "Estado": status,
                })
                evaluated += 1

        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=["Pista", "Clip", "LUFS", "Estado"]
            )
            writer.writeheader()
            writer.writerows(report)

        self.logger(f" Auditoría LUFS completada. Guardado en: {csv_path}")
        messagebox.showinfo(
            "Completado",
            f"Se evaluaron {evaluated} clips. Informe guardado.",
        )