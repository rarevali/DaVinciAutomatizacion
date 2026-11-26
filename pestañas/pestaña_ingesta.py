# -*- coding: utf-8 -*-
"""Módulo para la gestión de ingesta de archivos en DaVinci Resolve.

Este módulo provee la interfaz gráfica y la lógica interna para examinar
directorios, clasificar archivos multimedia por extensión y reconstruir
la estructura de carpetas como Bins dentro del Media Pool de DaVinci Resolve.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class ToolTip:
    """Crea ventanas emergentes con texto explicativo (tooltips).

    Se activa al pasar el cursor sobre un widget de Tkinter y se destruye
    cuando el ratón sale de dicho componente.
    """

    def __init__(self, widget: tk.Widget, text: str) -> None:
        """Inicializa la instancia del ToolTip.

        Args:
            widget (tk.Widget): El control de Tkinter al que se vinculará
                el globo de ayuda.
            text (str): Mensaje explicativo que se mostrará en pantalla.
        """
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None

        # Vinculación de eventos de ratón
        self.widget.bind("<Enter>", self.mostrar)
        self.widget.bind("<Leave>", self.ocultar)

    def mostrar(self, event: tk.Event = None) -> None:
        """Programa la aparición del globo explicativo con un breve retraso.

        El retraso evita que aparezcan múltiples ventanas al mover el ratón
        rápidamente por la interfaz.

        Args:
            event (tk.Event, optional): Evento desencadenante de entrada de ratón.
        """
        def mostrar_luego():
            if self.tipwindow or not self.text:
                return

            # Cálculo de la posición justo debajo del elemento
            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            # Creación de la ventana flotante sin bordes
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#ffffe0",
                foreground="#000000",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9, "normal"),
                padx=5,
                pady=3
            )
            label.pack(ipadx=1)

        if self.id is None:
            # Espera 350 ms antes de renderizar la ventana
            self.id = self.widget.after(350, mostrar_luego)

    def ocultar(self, event: tk.Event = None) -> None:
        """Cancela el temporizador pendiente y destruye la ventana emergente.

        Args:
            event (tk.Event, optional): Evento desencadenante de salida de ratón.
        """
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class PestañaIngesta(ttk.Frame):
    """Pestaña de interfaz de usuario para la ingesta clasificada de archivos.

    Gestiona la lectura de discos locales o de red, clasifica archivos según
    su extensión y crea la estructura jerárquica dentro de DaVinci Resolve.
    """

    # Extensiones de archivo permitidas y clasificadas por tipo de contenedor
    EXTENSIONS = {
        "01_VIDEO": {
            ".mov", ".mp4", ".mxf", ".braw", ".r3d", ".crm", ".avi", ".mkv"
        },
        "02_AUDIO": {
            ".wav", ".aif", ".aiff", ".mp3", ".aac", ".flac", ".m4a", ".wma",
            ".ogg", ".ac3"
        },
        "03_STILLS": {
            ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dpx", ".exr", ".dng",
            ".cr2", ".arw"
        },
        "04_GRAPHICS": {
            ".psd", ".ai", ".svg"
        }
    }

    def __init__(self, parent: tk.Widget, callback_logger: callable,
                 ejecutor_hilos: callable, resolve_instance: object) -> None:
        """Inicializa la pestaña de ingesta y sus dependencias.

        Args:
            parent (tk.Widget): Contenedor padre donde se alojará la pestaña.
            callback_logger (callable): Función para enviar mensajes al log
                consola principal.
            ejecutor_hilos (callable): Función para ejecutar tareas pesadas
                en segundo plano sin congelar la GUI.
            resolve_instance (object): Referencia directa a la API de
                DaVinci Resolve.
        """
        super().__init__(parent)
        self.logger = callback_logger
        self.ejecutar_hilo = ejecutor_hilos
        self.resolve = resolve_instance

        # Construcción de componentes de la interfaz
        self.construir_interfaz()

    def construir_interfaz(self) -> None:
        """Crea y organiza los controles visuales dentro del frame."""
        frame = ttk.LabelFrame(
            self, text=" Importación clasificada y subcarpetas ", padding=12
        )
        frame.pack(fill="x", padx=10, pady=10)

        # Etiqueta informativa
        lbl_path = ttk.Label(frame, text="Ruta de la carpeta raíz:")
        lbl_path.grid(row=0, column=0, sticky="w", pady=5)
        ToolTip(
            lbl_path,
            "Directorio principal que contiene los materiales a importar."
        )

        # Entrada de texto para la ruta
        self.entry_path = ttk.Entry(frame, width=42)
        self.entry_path.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(
            self.entry_path,
            "Ruta absoluta de la carpeta seleccionada en el disco."
        )

        # Botón para buscar directorios
        btn_browse = ttk.Button(
            frame, text="Examinar...", command=self.explorar_carpeta
        )
        btn_browse.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(
            btn_browse,
            "Abre el explorador del sistema para seleccionar una carpeta."
        )

        # Botón de ejecución del proceso
        self.btn_run = ttk.Button(
            self,
            text="📂 Importar respetando estructura de carpetas",
            command=lambda: self.ejecutar_hilo(self.proceso_importar)
        )
        self.btn_run.pack(fill="x", padx=15, pady=15)
        ToolTip(
            self.btn_run,
            "Inicia el escaneo e importación automática hacia DaVinci Resolve."
        )

    def explorar_carpeta(self) -> None:
        """Abre la ventana emergente para elegir la carpeta de origen."""
        carpeta = filedialog.askdirectory()
        if carpeta:
            # Reemplaza cualquier ruta previa por la seleccionada
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, carpeta)

    def _obtener_o_crear_subbin(self, media_pool: object, bin_padre: object,
                                nombre_bin: str) -> object:
        """Obtiene un bin existente o crea uno nuevo si no existe.

        Revisa la lista de subcarpetas dentro del bin padre para evitar
        duplicados durante el proceso de importación.

        Args:
            media_pool (object): Objeto MediaPool de la API de Resolve.
            bin_padre (object): Bin contenedor donde buscar o crear el subbin.
            nombre_bin (str): Nombre del subbin deseado.

        Returns:
            object: Referencia al objeto Folder (Bin) encontrado o creado.
        """
        # Obtiene la lista actual de carpetas contenidas en el padre
        sub_folders = bin_padre.GetSubFolderList() or []

        # Si el bin ya existe, se reutiliza
        for folder in sub_folders:
            if folder.GetName() == nombre_bin:
                return folder

        # Si no existe, se crea un nuevo subbin dentro del padre
        return media_pool.AddSubFolder(bin_padre, nombre_bin)

    def proceso_importar(self) -> None:
        """Ejecuta el flujo completo de escaneo, clasificación e importación.

        Recorre la carpeta seleccionada de forma recursiva, determina la categoría
        de cada archivo por su extensión, genera la jerarquía de bins necesaria
        en DaVinci Resolve e importa los archivos a su ubicación correspondiente.

        Raises:
            RuntimeError: Si la ruta es inválida o no se detecta DaVinci Resolve.
        """
        ruta = self.entry_path.get().strip()
        if not ruta:
            messagebox.showerror(
                "Error", "Selecciona una ruta de carpeta válida."
            )
            return

        # Validación de la API de DaVinci Resolve
        resolve = self.resolve
        if not resolve:
            raise RuntimeError(
                "No se detectó la instancia activa de DaVinci Resolve."
            )

        # Obtención del proyecto actual y gestores de Media
        current_project = resolve.GetProjectManager().GetCurrentProject()
        if not current_project:
            raise RuntimeError(
                "No hay ningún proyecto abierto en DaVinci Resolve."
            )

        media_pool = current_project.GetMediaPool()
        media_storage = resolve.GetMediaStorage()
        target_dir = Path(ruta)

        # Comprobación de existencia del directorio
        if not target_dir.exists() or not target_dir.is_dir():
            raise RuntimeError(
                "La ruta especificada no existe o no es un directorio válido."
            )

        self.logger(f"--- Iniciando importación clasificada desde: {ruta} ---")
        root_bin = media_pool.GetRootFolder()

        # 1. Escaneo recursivo de todos los elementos del directorio de origen
        for file_path in target_dir.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                matched_category = None

                # 2. Comprobación de extensión con las categorías permitidas
                for category, ext_set in self.EXTENSIONS.items():
                    if ext in ext_set:
                        matched_category = category
                        break

                # 3. Si el archivo coincide con una categoría, procesamos su ruta
                if matched_category:
                    # Calcula la ruta relativa excluyendo el directorio raíz
                    relative_path = file_path.relative_to(target_dir)

                    # Separa la jerarquía de subcarpetas omitiendo el nombre del archivo
                    parts = relative_path.parts[:-1]

                    # Genera el bin de nivel superior (ej. "01_VIDEO")
                    current_bin = self._obtener_o_crear_subbin(
                        media_pool, root_bin, matched_category
                    )

                    # Genera secuencialmente los bins hijos según las subcarpetas del disco
                    for subfolder_name in parts:
                        current_bin = self._obtener_o_crear_subbin(
                            media_pool, current_bin, subfolder_name
                        )

                    # 4. Establece el bin de destino activo e importa el archivo físico
                    media_pool.SetCurrentFolder(current_bin)
                    media_storage.AddItemListToMediaPool(
                        [str(file_path.resolve())]
                    )

        # Restablece la navegación del Media Pool a la raíz del proyecto
        media_pool.SetCurrentFolder(root_bin)

        self.logger("Importación y estructura de subcarpetas finalizada.")
        messagebox.showinfo(
            "Completado", "Importación de archivos finalizada con éxito."
        )