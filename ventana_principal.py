# -*- coding: utf-8 -*-
"""Módulo principal de la aplicación de automatización para DaVinci Resolve.

Gestiona la interfaz gráfica principal, el sistema de pestañas modulares,
la consola de logs compartida y la ejecución asíncrona de hilos.
"""

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Detección segura de la instancia de DaVinci Resolve en el script principal
try:
    RESOLVE_INSTANCE = resolve
except NameError:
    import DaVinciResolveScript as dvr
    RESOLVE_INSTANCE = dvr.scriptapp("Resolve")

from pestañas.pestaña_audio import PestañaAudio
from pestañas.pestaña_colores import PestañaColores
from pestañas.pestaña_fondo import PestañaFondo
from pestañas.pestaña_ingesta import PestañaIngesta
from pestañas.pestaña_timelines import PestañaTimelines


class ToolTip:
    """Crea globos de texto flotantes al pasar el ratón sobre un componente."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        """Inicializa la clase ToolTip.

        Args:
            widget (tk.Widget): Componente de Tkinter al que se vincula la ayuda.
            text (str): Mensaje explicativo que se mostrará en pantalla.
        """
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.mostrar)
        self.widget.bind("<Leave>", self.ocultar)

    def mostrar(self, event: tk.Event = None) -> None:
        """Programa la aparición de la ventana flotante tras un breve retraso."""
        def mostrar_luego():
            if self.tipwindow or not self.text:
                return

            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

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
            self.id = self.widget.after(350, mostrar_luego)

    def ocultar(self, event: tk.Event = None) -> None:
        """Oculta y destruye la ventana flotante de ayuda."""
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class VentanaPrincipal(tk.Tk):
    """Ventana principal de la aplicación con estructura modular y consola."""

    def __init__(self) -> None:
        """Inicializa la ventana principal y sus componentes visuales."""
        super().__init__()
        self.title("DaVinci Resolve - Automatizaciones API")
        self.geometry("860x780")
        self.resizable(True, True)
        self.attributes("-topmost", True)

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.construir_layout()

    def registrar_log(self, mensaje: str) -> None:
        """Registra mensajes en la consola inferior de manera segura (thread-safe).

        Args:
            mensaje (str): Texto informativo o de error a registrar.
        """
        def actualizar():
            self.log_area.configure(state="normal")
            self.log_area.insert(tk.END, mensaje + "\n")
            self.log_area.see(tk.END)
            self.log_area.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            actualizar()
        else:
            self.after(0, actualizar)

    def iniciar_en_hilo(self, funcion_objetivo: callable) -> None:
        """Ejecuta tareas pesadas en segundo plano mediante hilos independientes.

        Args:
            funcion_objetivo (callable): Método que se ejecutará en paralelo.
        """
        def envoltorio():
            try:
                funcion_objetivo()
            except Exception as e:
                messagebox.showerror("Error de Ejecución", str(e))
                self.registrar_log(f"Error: {str(e)}")

        hilo = threading.Thread(target=envoltorio, daemon=True)
        hilo.start()

    def mostrar_ayuda(self) -> None:
        """Muestra una ventana emergente con el manual de uso rápido."""
        texto = (
            "MANUAL DE USO RÁPIDO\n"
            "--------------------------------------------------\n\n"
            "[1] INGESTA & BINS:\n"
            " - Selecciona la carpeta raíz y vuelca la estructura al Media Pool.\n\n"
            "[2] COLORACIÓN:\n"
            " - Escanea y asigna colores dinámicamente según la ruta de las carpetas.\n\n"
            "[3] TIMELINES, AUDIO Y QUITAR FONDO:\n"
            " - Automatizaciones secundarias del sistema.\n"
        )

        ventana_ayuda = tk.Toplevel(self)
        ventana_ayuda.title("Ayuda y Documentación")
        ventana_ayuda.geometry("580x520")
        ventana_ayuda.resizable(False, False)
        ventana_ayuda.attributes("-topmost", True)

        frame_ayuda = ttk.Frame(ventana_ayuda, padding=15)
        frame_ayuda.pack(fill="both", expand=True)

        txt_ayuda = scrolledtext.ScrolledText(
            frame_ayuda, wrap="word", width=68, height=20,
            font=("Consolas", 9), bg="#fcfcfc", fg="#222222"
        )
        txt_ayuda.pack(fill="both", expand=True, pady=(0, 10))
        txt_ayuda.insert(tk.END, texto)
        txt_ayuda.configure(state="disabled")

        btn_cerrar = ttk.Button(
            frame_ayuda, text="Aceptar", command=ventana_ayuda.destroy
        )
        btn_cerrar.pack(anchor="e")

    def construir_layout(self) -> None:
        """Construye la estructura visual superior, central y de logs."""
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=10, pady=(6, 0))

        btn_help = ttk.Button(
            header_frame, text="❓ Manual de ayuda", width=20,
            command=self.mostrar_ayuda
        )
        btn_help.pack(side="right")
        ToolTip(btn_help, "Abre la ventana con el manual de uso detallado.")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self.tab_ingesta = PestañaIngesta(
            self.notebook, self.registrar_log, self.iniciar_en_hilo, RESOLVE_INSTANCE
        )
        self.tab_colores = PestañaColores(
            self.notebook, self.registrar_log, self.iniciar_en_hilo, RESOLVE_INSTANCE
        )
        self.tab_timelines = PestañaTimelines(
            self.notebook, self.registrar_log, self.iniciar_en_hilo, RESOLVE_INSTANCE
        )
        self.tab_audio = PestañaAudio(
            self.notebook, self.registrar_log, self.iniciar_en_hilo, RESOLVE_INSTANCE
        )
        self.tab_fondo = PestañaFondo(
            self.notebook, self.registrar_log, self.iniciar_en_hilo
        )

        self.notebook.add(self.tab_ingesta, text=" 📂 1. Ingesta ")
        self.notebook.add(self.tab_colores, text=" 🎨 2. Coloración ")
        self.notebook.add(self.tab_timelines, text=" 🎬 3. Timelines ")
        self.notebook.add(self.tab_audio, text=" 🔊 4. Audio y loudness ")
        self.notebook.add(self.tab_fondo, text=" 🖼️ 5. Quitar fondo ")

        log_frame = ttk.LabelFrame(self, text=" Consola de logs ", padding=8)
        log_frame.pack(fill="both", side="bottom", padx=10, pady=8, expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_frame, wrap="word", height=7, state="disabled",
            bg="#1e1e1e", fg="#00ff66", font=("Consolas", 9)
        )
        self.log_area.pack(fill="both", expand=True)
        ToolTip(self.log_area, "Muestra el registro de eventos en tiempo real.")


if __name__ == "__main__":
    app = VentanaPrincipal()
    app.mainloop()