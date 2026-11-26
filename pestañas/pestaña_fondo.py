# -*- coding: utf-8 -*-
"""Módulo para la eliminación automatizada de fondos en imágenes mediante IA.

Gestiona la selección de directorios de origen, la detección de intérpretes 
de Python compatibles en el sistema (incluyendo entornos Conda y rutas locales)
y la ejecución por lotes de subprocesos mediante la librería 'rembg' para aislar
sujetos u objetos de manera limpia.
"""

from pathlib import Path
import subprocess
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class PestañaFondo(ttk.Frame):
    """Pestaña de interfaz de usuario para el procesamiento por lotes

    y la eliminación inteligente de fondos en recursos gráficos.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callback_logger: callable,
        ejecutor_hilos: callable,
    ) -> None:
        """Inicializa la pestaña de procesamiento de imágenes y sus dependencias."""
        super().__init__(parent)
        self.logger = callback_logger
        self.ejecutar_hilo = ejecutor_hilos
        self.construir_interfaz()

    def construir_interfaz(self) -> None:
        """Crea el contenedor principal y los elementos visuales de control."""
        frame = ttk.LabelFrame(
            self,
            text=" Eliminación automática de fondo en imágenes (IA) ",
            padding=12,
        )
        frame.pack(fill="x", padx=10, pady=10)

        # Configuración del campo de ruta de imágenes
        ttk.Label(frame, text="Carpeta de imágenes:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.entry_img_path = ttk.Entry(frame, width=32)
        self.entry_img_path.grid(row=0, column=1, padx=5, pady=5)

        # Botón para explorar carpetas del sistema
        btn_browse_img = ttk.Button(
            frame, text="Examinar...", command=self.explorar_carpeta
        )
        btn_browse_img.grid(row=0, column=2, padx=5, pady=5)

        # Botón principal de ejecución para la tarea de IA
        self.btn_run_bg = ttk.Button(
            self,
            text="🖼️ Quitar fondo a todas las imágenes",
            command=lambda: self.ejecutar_hilo(self.proceso_quitar_fondo),
        )
        self.btn_run_bg.pack(fill="x", padx=15, pady=15)

    def explorar_carpeta(self) -> None:
        """Abre un cuadro de diálogo del sistema para seleccionar

        la carpeta contenedora de los ficheros gráficos de origen.
        """
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.entry_img_path.delete(0, tk.END)
            self.entry_img_path.insert(0, carpeta)

    def _encontrar_interprete_python(self) -> str:
        """Busca y valida un intérprete de Python compatible en el sistema

        explorando rutas estándar de Anaconda, Miniconda o instalaciones locales.
        """
        posibles = [
            r"C:\ProgramData\anaconda3\python.exe",
            r"C:\ProgramData\Miniconda3\python.exe",
            os.path.expanduser(r"~\anaconda3\python.exe"),
            os.path.expanduser(r"~\miniconda3\python.exe"),
            os.path.expanduser(
                r"~\AppData\Local\Programs\Python\Python313\python.exe"
            ),
        ]
        for ruta in posibles:
            if Path(ruta).exists():
                return ruta
        try:
            res = subprocess.run(
                ["where", "python"], capture_output=True, text=True, check=True
            )
            rutas = res.stdout.strip().splitlines()
            if rutas:
                return rutas[0]
        except Exception:
            pass
        raise RuntimeError("No se encontró ningún intérprete de Python.")

    def proceso_quitar_fondo(self) -> None:
        """Ejecuta el procesamiento concurrente por lotes para eliminar

        el fondo de las imágenes compatibles utilizando la librería 'rembg'.
        """
        path = self.entry_img_path.get().strip()
        if not path:
            messagebox.showerror(
                "Error", "Selecciona una carpeta con imágenes."
            )
            return

        input_dir = Path(path)
        if not input_dir.exists() or not input_dir.is_dir():
            raise RuntimeError("La ruta especificada no es válida.")

        output_dir = input_dir / "Sin_Fondo"
        output_dir.mkdir(exist_ok=True)

        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
        image_files = [
            p
            for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in image_extensions
        ]

        if not image_files:
            self.logger("No se encontraron imágenes compatibles.")
            return

        python_executable = self._encontrar_interprete_python()
        processed_count = 0
        user_site = os.path.expanduser(
            r"~\AppData\Roaming\Python\Python313\site-packages"
        )

        self.logger(
            f"--- Iniciando eliminación de fondos en: {input_dir} ---"
        )
        for img_path in image_files:
            try:
                output_path = output_dir / f"{img_path.stem}_sin_fondo.png"
                cmd = [
                    python_executable,
                    "-c",
                    f"import sys; sys.path.append(r'{user_site}'); from rembg import remove; from PIL import Image; remove(Image.open(r'{img_path}')).save(r'{output_path}')",
                ]
                if (
                    subprocess.run(cmd, capture_output=True, text=True).returncode
                    == 0
                ):
                    processed_count += 1
            except Exception:
                pass

        self.logger(f"Proceso finalizado. Guardadas en: {output_dir}")
        messagebox.showinfo(
            "Completado",
            f"Se procesaron {processed_count} imágenes correctamente.",
        )