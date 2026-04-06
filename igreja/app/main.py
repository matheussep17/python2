import os
import socket
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# Permite executar este arquivo diretamente: `python app/main.py`
# sem quebrar os imports absolutos `from app...`.
if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.frames.baixar_videos import BaixarFrame
from app.frames.compressor import CompressorFrame
from app.frames.converter import ConverterFrame
from app.frames.editor import EditorFrame
from app.frames.lyrics_search import LyricsSearchFrame
from app.frames.pdf_editor import PdfEditorFrame
from app.frames.transcriber import TranscriberFrame
from app.updater import (
    UpdateError,
    can_self_update,
    download_update_package,
    fetch_update_manifest,
    get_current_version,
    get_update_settings,
    has_update,
    schedule_windows_self_replace,
)
from app.ui.alerts import install_messagebox_hooks, show_info
from app.ui.theme import apply_design_system, resolve_ttk_theme
from app.utils import (
    HAS_DND,
    TkinterDnD,
    configure_runtime_environment,
    missing_runtime_requirements,
    runtime_requirement_message,
)
from app.version import APP_VERSION


class SuperApp(ttk.Window if not HAS_DND else TkinterDnD.Tk):
    def __init__(self):
        import traceback

        def report_callback_exception(exc, val, tb):
            traceback.print_exception(exc, val, tb)

        tk.Tk.report_callback_exception = report_callback_exception

        initial_mode = "Escuro"
        initial_theme = resolve_ttk_theme(initial_mode)

        if HAS_DND:
            super().__init__()
            self.style = ttk.Style(theme=initial_theme)
            self.geometry("1280x760")
        else:
            super().__init__(
                title="Media Suite - Conversor",
                themename=initial_theme,
                size=(1280, 760),
            )
            self.style = ttk.Style()

        self.theme_mode = tk.StringVar(value=initial_mode)
        self.nav_bootstyles = {
            "converter": "primary",
            "editor": "danger",
            "lyrics": "secondary",
            "pdf": "info",
            "compressor": "warning",
            "baixar": "info",
            "transcribe": "success",
        }
        self.nav_buttons = {}
        self.update_check_in_progress = False

        self._apply_window_icon()
        install_messagebox_hooks(self)
        apply_design_system(self, self.style, self.theme_mode.get())

        self.title("Media Suite - Conversor")
        # Some frames (like the video editor) can grow tall/wide when generating output,
        # so keep the window from being resized too small.
        self.minsize(1280, 760)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(18, 12), style="TopBar.TFrame")
        top.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(top, text="Media Suite", style="AppHeader.TLabel").pack(side="left")
        self.title_label = ttk.Label(top, text="• Conversor", style="AppSubHeader.TLabel")
        self.title_label.pack(side="left", padx=(8, 0))

        top_right = ttk.Frame(top, style="TopBar.TFrame")
        top_right.pack(side="right")
        ttk.Label(top_right, text="Tema", style="SidebarHint.TLabel").pack(side="left", padx=(0, 6))
        self.theme_box = ttk.Combobox(
            top_right,
            textvariable=self.theme_mode,
            values=["Escuro", "Claro"],
            state="readonly",
            width=9,
        )
        self.theme_box.pack(side="left")
        self.theme_box.bind("<<ComboboxSelected>>", self._on_theme_changed)
        ttk.Button(
            top_right,
            text="Atualizar",
            bootstyle="info-outline",
            command=lambda: self.check_for_updates(user_initiated=True),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            top_right,
            text="Sobre",
            bootstyle="secondary-outline",
            command=self._open_about,
        ).pack(side="left", padx=(8, 0))

        side = ttk.Frame(self, padding=14, style="SideBar.TFrame")
        side.grid(row=1, column=0, sticky="ns")
        ttk.Label(side, text="Navegacao", style="SidebarHint.TLabel").pack(anchor="w", pady=(0, 8))

        # Side navigation tabs are ordered alphabetically (by label) for consistency.
        for key, label, emoji in [
            ("baixar", "Baixar", "⬇️"),
            ("compressor", "Comprimir", "🗜️"),
            ("converter", "Conversor", "⚙️"),
            ("editor", "Editar mídia", "✂️"),
            ("lyrics", "Letras", "🎵"),
            ("pdf", "Editar PDF", "📄"),
            ("transcribe", "Transcrição", "📝"),
        ]:
            btn = ttk.Button(
                side,
                # Standardize spacing between icon and label.
                text=f"{emoji} {label}",
                style="Nav.TButton",
                command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", pady=5)
            self.nav_buttons[key] = btn

        self.content = ttk.Frame(self, padding=(8, 16, 16, 16), style="ContentArea.TFrame")
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        sb = ttk.Frame(self, padding=(16, 8), style="StatusBar.TFrame")
        sb.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.statusbar_var = tk.StringVar(value="Pronto.")
        ttk.Label(sb, textvariable=self.statusbar_var, style="Status.TLabel", anchor="w").pack(side="left")

        self.frames = {
            "converter": ConverterFrame(self.content, self._set_status),
            "editor": EditorFrame(self.content, self._set_status),
            "lyrics": LyricsSearchFrame(self.content, self._set_status),
            "pdf": PdfEditorFrame(self.content, self._set_status),
            "compressor": CompressorFrame(self.content, self._set_status),
            "baixar": BaixarFrame(self.content, self._set_status),
            "transcribe": TranscriberFrame(self.content, self._set_status),
        }
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self._show("converter")

        self.bind("<Control-Key-1>", lambda _e: self._show("converter"))
        self.bind("<Control-Key-2>", lambda _e: self._show("editor"))
        self.bind("<Control-Key-3>", lambda _e: self._show("baixar"))
        self.bind("<Control-Key-4>", lambda _e: self._show("compressor"))
        self.bind("<Control-Key-5>", lambda _e: self._show("pdf"))
        self.bind("<Control-Key-6>", lambda _e: self._show("transcribe"))
        self.after(2000, self._schedule_auto_update_check)

    def _on_theme_changed(self, _event=None):
        mode = self.theme_mode.get()
        self.style.theme_use(resolve_ttk_theme(mode))
        apply_design_system(self, self.style, mode)
        current = getattr(self, "current_screen", "converter")
        self._update_nav_appearance(current)

    def _show(self, key):
        frame = self.frames.get(key)
        if not frame:
            return

        frame.lift()
        self.current_screen = key
        self._update_nav_appearance(key)

        mapping = {
            "converter": "• Conversor",
            "editor": "• Editar video",
            "pdf": "• Editar PDF",
            "compressor": "• Comprimir",
            "baixar": "• Baixar",
            "transcribe": "• Transcricao",
        }
        self.title_label.config(text=mapping.get(key, ""))

        if key == "baixar":
            try:
                service = self.frames["baixar"].service.get()
            except Exception:
                service = "YouTube"
            self.title(f"Media Suite - Baixar - {service}")
        else:
            window_title = mapping.get(key, "• Conversor").replace("• ", "")
            self.title(f"Media Suite - {window_title}")

        self._set_status("Pronto.")

    def _update_nav_appearance(self, active_key):
        for key, btn in self.nav_buttons.items():
            color = self.nav_bootstyles.get(key, "secondary")
            bootstyle = color if key == active_key else f"{color}-outline"
            btn.configure(bootstyle=bootstyle)

    def _open_about(self):
        show_info(
            self,
            (
                f"Versao: {APP_VERSION}\n\n"
                "Desenvolvido por Matheus Torres para utilizacao na igreja.\n"
                "Projeto sem fins lucrativos, criado para facilitar o trabalho diario."
            ),
            "Sobre o app",
        )

    def _set_status(self, text):
        self.statusbar_var.set(text)

    def _schedule_auto_update_check(self):
        settings = get_update_settings()
        if settings.get("auto_check"):
            self.check_for_updates(user_initiated=False)

    def check_for_updates(self, user_initiated: bool):
        if self.update_check_in_progress:
            if user_initiated:
                messagebox.showinfo("Atualizacao", "Ja existe uma verificacao de atualizacao em andamento.")
            return

        if not can_self_update():
            if user_initiated:
                messagebox.showinfo(
                    "Atualizacao",
                    "A atualizacao automatica funciona no executavel Windows gerado pelo build.",
                )
            return

        self.update_check_in_progress = True
        self._set_status("Verificando atualizacoes...")
        threading.Thread(
            target=self._check_for_updates_worker,
            args=(user_initiated,),
            daemon=True,
        ).start()

    def _check_for_updates_worker(self, user_initiated: bool):
        try:
            manifest = fetch_update_manifest()
        except Exception as exc:
            self.after(0, lambda: self._finish_update_check_error(exc, user_initiated))
            return

        self.after(0, lambda: self._handle_update_manifest(manifest, user_initiated))

    def _finish_update_check_error(self, exc: Exception, user_initiated: bool):
        self.update_check_in_progress = False
        self._set_status("Pronto.")
        if user_initiated:
            if isinstance(exc, UpdateError):
                messagebox.showwarning("Atualizacao", str(exc))
            else:
                messagebox.showerror("Atualizacao", f"Falha ao verificar atualizacoes:\n{exc}")

    def _handle_update_manifest(self, manifest: dict, user_initiated: bool):
        self.update_check_in_progress = False
        if not has_update(manifest):
            self._set_status("Pronto.")
            if user_initiated:
                messagebox.showinfo(
                    "Atualizacao",
                    f"Voce ja esta na versao mais recente ({get_current_version()}).",
                )
            return

        notes = manifest.get("notes", "").strip()
        prompt = (
            f"Versao atual: {get_current_version()}\n"
            f"Nova versao: {manifest['version']}\n\n"
            "Deseja baixar e instalar agora?"
        )
        if notes:
            prompt += f"\n\nNovidades:\n{notes}"

        should_install = messagebox.askyesno("Atualizacao disponivel", prompt)
        if not should_install:
            self._set_status("Atualizacao adiada.")
            return

        self.update_check_in_progress = True
        self._set_status(f"Baixando atualizacao {manifest['version']}...")
        threading.Thread(
            target=self._download_and_apply_update_worker,
            args=(manifest,),
            daemon=True,
        ).start()

    def _download_and_apply_update_worker(self, manifest: dict):
        try:
            package_path = download_update_package(
                manifest,
                progress_callback=lambda downloaded, total: self.after(
                    0, lambda: self._report_update_download_progress(manifest["version"], downloaded, total)
                ),
            )
            self.after(0, lambda: self._finish_update_download(package_path, manifest))
        except Exception as exc:
            self.after(0, lambda: self._finish_update_download_error(exc))

    def _report_update_download_progress(self, version: str, downloaded: int, total: int):
        if total > 0:
            percent = int((downloaded / total) * 100)
            self._set_status(f"Baixando atualizacao {version}... {percent}%")
        else:
            self._set_status(f"Baixando atualizacao {version}...")

    def _finish_update_download(self, package_path: Path, manifest: dict):
        self.update_check_in_progress = False
        self._set_status("Atualizacao pronta para instalar.")

        confirm = messagebox.askyesno(
            "Instalar atualizacao",
            (
                f"A versao {manifest['version']} foi baixada.\n\n"
                "O aplicativo sera fechado para concluir a atualizacao.\n"
                "Deseja continuar agora?"
            ),
        )
        if not confirm:
            self._set_status("Atualizacao baixada, mas nao instalada.")
            return

        try:
            schedule_windows_self_replace(package_path)
        except Exception as exc:
            messagebox.showerror("Atualizacao", f"Nao foi possivel iniciar a instalacao:\n{exc}")
            self._set_status("Falha ao iniciar a atualizacao.")
            return

        self.destroy()

    def _finish_update_download_error(self, exc: Exception):
        self.update_check_in_progress = False
        self._set_status("Falha ao baixar atualizacao.")
        messagebox.showerror("Atualizacao", f"Falha ao baixar a atualizacao:\n{exc}")

    def _apply_window_icon(self):
        if not sys.platform.startswith("win"):
            return

        candidates = [Path(sys.executable)] if getattr(sys, "frozen", False) else []
        candidates.extend(
            [
                Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico",
                Path.cwd() / "app" / "assets" / "app_icon.ico",
            ]
        )

        for icon_path in candidates:
            try:
                if icon_path.exists():
                    self.iconbitmap(default=str(icon_path))
                    return
            except Exception:
                continue


def single_instance_or_exit(port=54321):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        try:
            messagebox.showinfo("Ja esta aberto", "O aplicativo ja esta em execucao.")
        except Exception:
            pass
        sys.exit(0)
    return sock


def main():
    configure_runtime_environment()
    missing, runtime = missing_runtime_requirements()
    if missing:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Dependencias ausentes", runtime_requirement_message(missing, runtime))
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    _lock = single_instance_or_exit()
    app = SuperApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("Aplicativo interrompido pelo usuário.")
        sys.exit(0)


if __name__ == "__main__":
    main()
