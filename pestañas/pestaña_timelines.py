# -*- coding: utf-8 -*-
"""Módulo para la generación automática y exportación de secuencias (Timelines).

Gestiona la creación de líneas de tiempo basadas en la agrupación temporal
de los clips, soporta modos de organización secuencial o apilada (con 
distribución escalonada de vídeo y audio), y automatiza su envío masivo 
a la cola de renderizado en DaVinci Resolve.
"""

from datetime import datetime
import re
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk


class PestañaTimelines(ttk.Frame):
    """Pestaña de interfaz de usuario para la configuración, generación

    y exportación automatizada de secuencias cronológicas.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callback_logger: callable,
        ejecutor_hilos: callable,
        resolve_instance: object,
    ) -> None:
        """Inicializa la pestaña de generación de timelines y sus dependencias."""
        super().__init__(parent)
        self.logger = callback_logger
        self.ejecutar_hilo = ejecutor_hilos
        self.resolve = resolve_instance
        self.construir_interfaz()

    def construir_interfaz(self) -> None:
        """Crea el contenedor principal y los elementos visuales de control."""
        frame = ttk.LabelFrame(
            self,
            text=" Configuración de secuencias y exportación ",
            padding=12,
        )
        frame.pack(fill="x", padx=10, pady=10)

        # Configuración del prefijo o código identificativo
        ttk.Label(frame, text="Código / Prefijo (ej. ESP):").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.country_entry = ttk.Entry(frame, width=15)
        self.country_entry.insert(0, "ESP")
        self.country_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Selector de resolución de salida
        ttk.Label(frame, text="Resolución:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.combo_res = ttk.Combobox(
            frame,
            values=[
                "UHD (3840x2160)",
                "FHD (1920x1080)",
                "Vertical (1080x1920)",
            ],
            state="readonly",
            width=25,
        )
        self.combo_res.current(0)
        self.combo_res.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Selector del modo de distribución de pistas
        ttk.Label(frame, text="Modo de pistas:").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.mode_options = [
            "Secuencial (pista única V1/A1) - Recomendado",
            "Apilado vertical (una pista por clip V1/A1, V2/A2...)",
        ]
        self.combo_mode = ttk.Combobox(
            frame, values=self.mode_options, state="readonly", width=42
        )
        self.combo_mode.current(1)
        self.combo_mode.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Botón para la generación automática de timelines
        self.btn_run_timelines = ttk.Button(
            self,
            text="Generar timelines automáticas",
            command=lambda: self.ejecutar_hilo(self.proceso_generar_timelines),
        )
        self.btn_run_timelines.pack(fill="x", padx=15, pady=(10, 5))

        # Botón para exportar y renderizar el contenido
        self.btn_export_timelines = ttk.Button(
            self,
            text="Exportar y renderizar todas las timelines",
            command=lambda: self.ejecutar_hilo(self.proceso_exportar_timelines),
        )
        self.btn_export_timelines.pack(fill="x", padx=15, pady=(5, 10))

    def _obtener_clips_recursivamente(self, folder: object) -> list:
        """Explora de manera recursiva un Bin para extraer todos los clips

        descartando aquellas referencias que correspondan a timelines previas.
        """
        clips_found = []
        clip_list = folder.GetClipList() or []
        for clip in clip_list:
            properties = clip.GetClipProperty() or {}
            if properties.get("Type", "") != "Timeline":
                clips_found.append(clip)

        sub_folders = folder.GetSubFolderList() or []
        for sub_folder in sub_folders:
            clips_found.extend(
                self._obtener_clips_recursivamente(sub_folder)
            )

        return clips_found

    def _extraer_fecha_clip(self, clip: object) -> tuple:
        """Extrae la fecha de un clip evaluando su nombre mediante expresiones

        regulares o consultando los metadatos internos de creación.
        """
        filename = clip.GetName()
        match = re.search(r"(\d{2})(\d{2})(20\d{2})", filename)
        if match:
            day, month, year = match.groups()
            try:
                return datetime(
                    int(year), int(month), int(day)
                ), "Fecha en nombre"
            except ValueError:
                pass

        properties = clip.GetClipProperty() or {}
        metadata = clip.GetMetadata() or {}
        raw_date = properties.get("Date Created", "") or metadata.get(
            "Date Created", ""
        )

        if raw_date:
            for fmt in [
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return (
                        datetime.strptime(str(raw_date).strip(), fmt),
                        "Metadato",
                    )
                except ValueError:
                    continue

        return datetime(2021, 9, 1), "Por defecto"

    def _es_clip_solo_audio(self, clip: object) -> bool:
        """Determina si un elemento multimedia pertenece exclusivamente a

        una pista sonora analizando su extensión de archivo o tipo.
        """
        properties = clip.GetClipProperty() or {}
        clip_type = str(properties.get("Type", "")).lower()
        file_path = str(properties.get("File Path", "")).lower()
        audio_extensions = {
            ".wav",
            ".mp3",
            ".aac",
            ".m4a",
            ".aiff",
            ".flac",
            ".wma",
            ".ogg",
            ".ac3",
        }

        if any(file_path.endswith(ext) for ext in audio_extensions):
            return True
        if "audio" in clip_type and "video" not in clip_type:
            return True

        return False

    def _obtener_duracion_frames(self, clip: object, fps: float) -> int:
        """Calcula la duración exacta de un clip en fotogramas

        utilizando las propiedades de duración o código de tiempo.
        """
        prop = clip.GetClipProperty() or {}
        frames_str = prop.get("Frames", "")
        if frames_str and str(frames_str).isdigit() and int(frames_str) > 0:
            return int(frames_str)

        duration_str = prop.get("Duration", "")
        if duration_str:
            parts = str(duration_str).split(":")
            if len(parts) == 4:
                h, m, s, f = map(int, parts)
                return int(((h * 3600) + (m * 60) + s) * fps + f)

        return int(5 * fps)

    def _adjuntar_clips_apilados(
        self, media_pool: object, timeline: object, clips: list
    ) -> None:
        """Inserta los clips de vídeo y de audio en la secuencia de forma vertical

        (escalonados), colocando los audios independientes a continuación de los vídeos.
        """
        fps = float(timeline.GetSetting("timelineFrameRate") or "24")
        start_frame_offset = int(3600 * fps)
        
        # Separamos los recursos de vídeo y audio independiente
        video_clips = [c for c in clips if not self._es_clip_solo_audio(c)]
        audio_clips = [c for c in clips if self._es_clip_solo_audio(c)]

        # Aseguramos pistas suficientes de vídeo y audio en la línea de tiempo
        while timeline.GetTrackCount("video") < len(video_clips):
            timeline.AddTrack("video")
        total_audio_tracks_needed = len(video_clips) + len(audio_clips)
        while timeline.GetTrackCount("audio") < total_audio_tracks_needed:
            timeline.AddTrack("audio")

        # 1. Inserción escalonada de los clips de vídeo
        current_frame = start_frame_offset
        for idx, clip in enumerate(video_clips, start=1):
            duration = self._obtener_duracion_frames(clip, fps)
            media_pool.AppendToTimeline(
                [{
                    "mediaPoolItem": clip,
                    "trackIndex": idx,
                    "recordFrame": current_frame,
                    "mediaType": 0,
                }]
            )
            current_frame += duration  # El siguiente vídeo arranca al finalizar el anterior

        # 2. Inserción escalonada de los clips de audio independientes
        # Comienzan en el fotograma exacto donde concluyeron los vídeos para evitar solapamientos
        audio_current_frame = current_frame
        base_audio_track = len(video_clips) + 1

        for idx, clip in enumerate(audio_clips):
            duration = self._obtener_duracion_frames(clip, fps)
            media_pool.AppendToTimeline(
                [{
                    "mediaPoolItem": clip,
                    "trackIndex": base_audio_track + idx,
                    "recordFrame": audio_current_frame,
                    "mediaType": 2,
                }]
            )
            audio_current_frame += duration  # Cada audio independiente se coloca secuencialmente

    def proceso_generar_timelines(self) -> None:
        """Ejecuta la lógica de agrupación temporal de clips y la posterior

        creación automatizada de las líneas de tiempo en el proyecto.
        """
        resolve = self.resolve
        if not resolve:
            raise RuntimeError(
                "No se detectó la instancia activa de DaVinci Resolve."
            )
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("No hay ningún proyecto abierto.")

        media_pool = project.GetMediaPool()
        country_code = self.country_entry.get().strip() or "ESP"
        res_selection = self.combo_res.get()
        mode = self.combo_mode.get()

        if "3840x2160" in res_selection:
            w, h = "3840", "2160"
        elif "1920x1080" in res_selection:
            w, h = "1920", "1080"
        else:
            w, h = "1080", "1920"

        self.logger(
            f"--- Iniciando proceso de timelines para: [{country_code}] ---"
        )
        root_folder = media_pool.GetRootFolder()
        sub_folders = root_folder.GetSubFolderList() or []

        video_bin = next(
            (sf for sf in sub_folders if sf.GetName() == "01_VIDEO"),
            root_folder,
        )
        audio_bin = next(
            (sf for sf in sub_folders if sf.GetName() == "02_AUDIO"), None
        )

        clips = self._obtener_clips_recursivamente(video_bin)
        independent_audio = (
            self._obtener_clips_recursivamente(audio_bin)
            if audio_bin
            else []
        )

        if not clips:
            self.logger("No se encontraron clips de video válidos.")
            return

        grouped_clips = {}
        for clip in clips:
            clip_date, _ = self._extraer_fecha_clip(clip)
            day_key = datetime(clip_date.year, clip_date.month, clip_date.day)
            grouped_clips.setdefault(day_key, []).append(clip)

        created_timelines = []
        for date_obj in sorted(grouped_clips.keys()):
            timeline_name = f"{country_code}_{date_obj.strftime('%d-%m-%Y')}"
            combined = grouped_clips[date_obj] + independent_audio
            timeline = media_pool.CreateEmptyTimeline(timeline_name)
            if timeline:
                timeline.SetSetting("timelineResolutionWidth", w)
                timeline.SetSetting("timelineResolutionHeight", h)
                if "Apilado" in mode:
                    self._adjuntar_clips_apilados(
                        media_pool, timeline, combined
                    )
                else:
                    media_pool.AppendToTimeline(combined)
                created_timelines.append(timeline)

        if created_timelines:
            master_clips = [
                t.GetMediaPoolItem()
                for t in created_timelines
                if t.GetMediaPoolItem()
            ]
            if master_clips:
                master = media_pool.CreateTimelineFromClips(
                    f"{country_code}_MASTER_SEQUENCE", master_clips
                )
                if master:
                    master.SetSetting("timelineResolutionWidth", w)
                    master.SetSetting("timelineResolutionHeight", h)

        self.logger("Timelines generadas con éxito.")
        messagebox.showinfo(
            "Completado", "Generación de timelines finalizada."
        )

    def proceso_exportar_timelines(self) -> None:
        """Configura los parámetros de renderizado y añade de forma masiva

        todas las timelines activas a la cola de exportación del software.
        """
        output_dir = filedialog.askdirectory(
            title="Seleccionar carpeta de destino"
        )
        if not output_dir:
            return

        resolve = self.resolve
        if not resolve:
            raise RuntimeError("No se detectó DaVinci Resolve.")
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("No hay proyecto abierto.")

        try:
            project.DeleteAllRenderJobs()
        except Exception:
            pass

        try:
            project.SetCurrentRenderFormatAndCodec("mp4", "H.264")
        except Exception:
            pass

        res_selection = self.combo_res.get()
        if "3840x2160" in res_selection:
            w, h = "3840", "2160"
        elif "1920x1080" in res_selection:
            w, h = "1920", "1080"
        else:
            w, h = "1080", "1920"

        project.SetRenderSettings({
            "TargetDir": output_dir,
            "FormatWidth": w,
            "FormatHeight": h,
            "ExportVideo": True,
            "ExportAudio": True,
            "SelectAllFrames": True,
        })

        timeline_count = project.GetTimelineCount()
        added = 0
        job_ids = []

        for i in range(1, timeline_count + 1):
            timeline = project.GetTimelineByIndex(i)
            if timeline:
                project.SetCurrentTimeline(timeline)
                project.SetRenderSettings({"CustomName": timeline.GetName()})
                job_id = project.AddRenderJob()
                if job_id:
                    added += 1
                    job_ids.append(job_id)

        if added > 0:
            self.logger(
                f"Se añadieron {added} timelines a la cola de render."
            )
            try:
                project.StartRendering(job_ids)
            except Exception:
                pass
            messagebox.showinfo(
                "Completado", f"Se han añadido {added} timelines a la cola."
            )