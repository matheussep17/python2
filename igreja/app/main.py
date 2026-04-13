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
    has_update,
    schedule_windows_self_replace,
)
from app.ui.alerts import install_messagebox_hooks, show_info
from app.ui.cursors import install_cursor_profile
from app.ui.theme import apply_design_system, resolve_ttk_theme
from app.utils import (
    HAS_DND,
    TkinterDnD,
    configure_runtime_environment,
    download_and_install_ffmpeg,
    ffmpeg_vendor_bin_dir,
    get_ffmpeg_download_url,
    missing_runtime_requirements,
    runtime_requirement_message,
)
from app.version import APP_VERSION


DEFAULT_WINDOW_WIDTH = 1480
DEFAULT_WINDOW_HEIGHT = 760
MIN_WINDOW_WIDTH = 1120
MIN_WINDOW_HEIGHT = 600
SMALL_SCREEN_WIDTH = 1366
SMALL_SCREEN_HEIGHT = 768


class SuperApp(ttk.Window if not HAS_DND else TkinterDnD.Tk):
    def __init__(self):
        import traceback

        def report_callback_exception(_root, exc, val, tb):
            if exc is tk.TclError and val and "application has been destroyed" in str(val).lower():
                return
            traceback.print_exception(exc, val, tb)

        tk.Tk.report_callback_exception = report_callback_exception

        initial_mode = "Escuro"
        initial_theme = resolve_ttk_theme(initial_mode)

        if HAS_DND:
            super().__init__()
            self.style = ttk.Style(theme=initial_theme)
        else:
            super().__init__(
                title="Media Suite - Conversor",
                themename=initial_theme,
                size=(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT),
            )
            self.style = ttk.Style()

        self.theme_mode = tk.StringVar(value=initial_mode)
        self.nav_buttons = {}
        self.update_check_in_progress = False
        self._is_closing = False
        self._sidebar_width = 320

        self._apply_window_icon()
        install_messagebox_hooks(self)
        apply_design_system(self, self.style, self.theme_mode.get())
        install_cursor_profile(self)

        self.title("Media Suite - Conversor")
        self._configure_initial_window()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.screen_meta = {
            "converter": {
                "window": "Conversor",
                "nav": "01  Conversor",
                "title": "Conversor Multiformato",
                "subtitle": "Transforme vídeo, áudio e imagem com uma estação limpa, previsível e pronta para produção.",
            },
            "compressor": {
                "window": "Comprimir",
                "nav": "02  Comprimir",
                "title": "Compressão Inteligente",
                "subtitle": "Reduza tamanho de arquivos preservando qualidade e clareza para entregas reais.",
            },
            "editor": {
                "window": "Editar mídia",
                "nav": "03  Editar mídia",
                "title": "Montagem de Trechos",
                "subtitle": "Organize segmentos, combine mídias e produza saídas com ritmo e precisão.",
            },
            "pdf": {
                "window": "Editar PDF",
                "nav": "04  Editar PDF",
                "title": "Anotação e Revisão de PDF",
                "subtitle": "Abra, revise, marque e exporte documentos com uma interface mais segura e focada.",
            },
            "baixar": {
                "window": "Baixar",
                "nav": "05  Baixar",
                "title": "Coleta de Mídia",
                "subtitle": "Baixe conteúdo externo com contexto claro de origem, formato e destino final.",
            },
            "lyrics": {
                "window": "Letras",
                "nav": "06  Letras",
                "title": "Pesquisa de Letras",
                "subtitle": "Busque referências musicais com leitura confortável e status de operação sempre visível.",
            },
            "transcribe": {
                "window": "Transcrição",
                "nav": "07  Transcrição",
                "title": "Transcrição Assistida",
                "subtitle": "Converta áudio em documentos com uma experiência mais séria, técnica e pronta para uso.",
            },
        }

        top = ttk.Frame(self, padding=(24, 18, 24, 14), style="TopBar.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        brand = ttk.Frame(top, style="TopBarInner.TFrame")
        brand.grid(row=0, column=0, sticky="w")
        ttk.Label(brand, text="CENTRAL DE MIDIA", style="AppKicker.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Media Suite", style="AppHeader.TLabel").pack(anchor="w", pady=(2, 0))
        self.title_label = ttk.Label(
            brand,
            text="Ambiente central para conversão, edição, busca e entrega de mídia",
            style="AppSubHeader.TLabel",
        )
        self.title_label.pack(anchor="w", pady=(2, 0))

        top_right = ttk.Frame(top, padding=8, style="ToolbarGroup.TFrame")
        top_right.grid(row=0, column=1, sticky="e")
        ttk.Label(top_right, text="Tema", style="HeaderMeta.TLabel").pack(side="left", padx=(0, 8))
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
            style="Chrome.TButton",
            command=lambda: self.check_for_updates(user_initiated=True),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            top_right,
            text="Sobre",
            style="Chrome.TButton",
            command=self._open_about,
        ).pack(side="left", padx=(8, 0))

        main = ttk.Frame(self, padding=(18, 0, 18, 14), style="AppBody.TFrame")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        side = ttk.Frame(main, padding=(0, 0, 16, 0), style="SideBar.TFrame")
        side.grid(row=0, column=0, sticky="ns")

        side_panel = ttk.Frame(side, padding=18, width=self._sidebar_width, style="SidebarPanel.TFrame")
        side_panel.pack(fill="y", expand=True)
        side_panel.pack_propagate(False)
        self.side_panel = side_panel
        ttk.Label(side_panel, text="NAVEGAÇÃO", style="SidebarSection.TLabel").pack(anchor="w")
        ttk.Label(side_panel, text="Áreas do Sistema", style="SidebarTitle.TLabel").pack(anchor="w", pady=(4, 2))
        self.sidebar_intro = ttk.Label(
            side_panel,
            text="Acesso rápido aos fluxos principais do aplicativo.",
            style="SidebarHint.TLabel",
            justify="left",
            wraplength=260,
        )
        self.sidebar_intro.pack(anchor="w", pady=(0, 14), fill="x")

        for key in ["converter", "compressor", "editor", "pdf", "baixar", "lyrics", "transcribe"]:
            btn = ttk.Button(
                side_panel,
                text=self.screen_meta[key]["nav"],
                style="Nav.TButton",
                command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        ttk.Separator(side_panel).pack(fill="x", pady=14)
        self.sidebar_footer = ttk.Label(
            side_panel,
            text="Use a navegação lateral ou os atalhos do rodapé.",
            style="SidebarHint.TLabel",
            justify="left",
            wraplength=260,
        )
        self.sidebar_footer.pack(anchor="w", pady=(4, 0), fill="x")

        workspace = ttk.Frame(main, style="ContentArea.TFrame")
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(1, weight=1)

        hero = ttk.Frame(workspace, padding=(22, 18), style="HeroPanel.TFrame")
        hero.grid(row=0, column=0, sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        ttk.Label(hero, text="ÁREA ATIVA", style="WorkspaceEyebrow.TLabel").grid(row=0, column=0, sticky="w")
        self.workspace_title = ttk.Label(hero, text="", style="WorkspaceTitle.TLabel")
        self.workspace_title.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.workspace_subtitle = ttk.Label(hero, text="", style="WorkspaceSubtitle.TLabel", justify="left", wraplength=860)
        self.workspace_subtitle.grid(row=2, column=0, sticky="w", pady=(4, 0))

        stage = ttk.Frame(workspace, padding=12, style="ContentShell.TFrame")
        stage.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        stage.grid_columnconfigure(0, weight=1)
        stage.grid_rowconfigure(0, weight=1)

        self.content = ttk.Frame(stage, style="ContentShell.TFrame")
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        sb = ttk.Frame(self, padding=(20, 10), style="StatusBar.TFrame")
        sb.grid(row=2, column=0, sticky="ew")
        self.statusbar_var = tk.StringVar(value="Pronto.")
        ttk.Label(sb, textvariable=self.statusbar_var, style="Status.TLabel", anchor="w").pack(side="left")
        self.status_meta = ttk.Label(sb, text=f"Versão {APP_VERSION} • Atalhos Ctrl+1 a Ctrl+7", style="Status.TLabel")
        self.status_meta.pack(side="right")

        self.frames = {
            "converter": ConverterFrame(self.content, self._set_status),
            "editor": EditorFrame(self.content, self._set_status),
            "lyrics": LyricsSearchFrame(self.content, self._set_status),
            "pdf": PdfEditorFrame(self.content, self._set_status),
            "compressor": CompressorFrame(self.content, self._set_status),
            "baixar": BaixarFrame(self.content, self._set_status),
            "transcribe": TranscriberFrame(self.content, self._set_status),
        }
        for key, frame in self.frames.items():
            frame.screen_key = key
            frame.grid(row=0, column=0, sticky="nsew")

        self._show("converter")

        self.bind("<Control-Key-1>", lambda _e: self._show("converter"))
        self.bind("<Control-Key-2>", lambda _e: self._show("compressor"))
        self.bind("<Control-Key-3>", lambda _e: self._show("editor"))
        self.bind("<Control-Key-4>", lambda _e: self._show("pdf"))
        self.bind("<Control-Key-5>", lambda _e: self._show("baixar"))
        self.bind("<Control-Key-6>", lambda _e: self._show("lyrics"))
        self.bind("<Control-Key-7>", lambda _e: self._show("transcribe"))
        self.bind("<Configure>", self._on_window_resize, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(500, self._schedule_startup_update_check)
        self.after_idle(self._update_responsive_shell)

    def _configure_initial_window(self):
        screen_width = max(1, int(self.winfo_screenwidth()))
        screen_height = max(1, int(self.winfo_screenheight()))

        min_width = min(DEFAULT_WINDOW_WIDTH, max(MIN_WINDOW_WIDTH, screen_width - 80))
        min_height = min(DEFAULT_WINDOW_HEIGHT, max(MIN_WINDOW_HEIGHT, screen_height - 120))
        self.minsize(min_width, min_height)

        should_zoom = screen_width <= SMALL_SCREEN_WIDTH or screen_height <= SMALL_SCREEN_HEIGHT
        target_width = min(DEFAULT_WINDOW_WIDTH, max(min_width, int(screen_width * 0.92)))
        target_height = min(DEFAULT_WINDOW_HEIGHT, max(min_height, int(screen_height * 0.9)))

        if should_zoom:
            self.geometry(f"{target_width}x{target_height}+0+0")
            try:
                self.state("zoomed")
                return
            except tk.TclError:
                pass

        x = max(0, (screen_width - target_width) // 2)
        y = max(0, (screen_height - target_height) // 2)
        self.geometry(f"{target_width}x{target_height}+{x}+{y}")

    def _on_theme_changed(self, _event=None):
        mode = self.theme_mode.get()
        self.style.theme_use(resolve_ttk_theme(mode))
        apply_design_system(self, self.style, mode)
        current = getattr(self, "current_screen", "converter")
        self._update_nav_appearance(current)
        self._show(current)
        self._update_responsive_shell()

    def _on_window_resize(self, event=None):
        if event is not None and event.widget is not self:
            return
        self._update_responsive_shell()

    def _update_responsive_shell(self):
        width = max(1, self.winfo_width())

        if width >= 1700:
            sidebar_width = 320
        elif width >= 1450:
            sidebar_width = 280
        else:
            sidebar_width = 240

        self._sidebar_width = sidebar_width
        if getattr(self, "side_panel", None):
            self.side_panel.configure(width=sidebar_width)

        sidebar_wrap = max(180, sidebar_width - 36)
        if getattr(self, "sidebar_intro", None):
            self.sidebar_intro.configure(wraplength=sidebar_wrap)
        if getattr(self, "sidebar_footer", None):
            self.sidebar_footer.configure(wraplength=sidebar_wrap)

        subtitle_wrap = max(420, width - sidebar_width - 220)
        if getattr(self, "workspace_subtitle", None):
            self.workspace_subtitle.configure(wraplength=subtitle_wrap)

        if getattr(self, "status_meta", None):
            compact = width < 1180
            self.status_meta.configure(
                text=(f"Versão {APP_VERSION} • Ctrl+1..7" if compact else f"Versão {APP_VERSION} • Atalhos Ctrl+1 a Ctrl+7")
            )

    def _show(self, key):
        frame = self.frames.get(key)
        if not frame:
            return

        frame.lift()
        self.current_screen = key
        self._update_nav_appearance(key)

        meta = self.screen_meta.get(key, self.screen_meta["converter"])
        self.workspace_title.config(text=meta["title"])
        self.workspace_subtitle.config(text=meta["subtitle"])
        self.title_label.config(text=f"Área atual: {meta['window']}")

        if key == "baixar":
            try:
                service = self.frames["baixar"].service.get()
            except Exception:
                service = "YouTube"
            self.workspace_subtitle.config(
                text=f"{meta['subtitle']} Serviço atual configurado: {service}."
            )
            self.title(f"Media Suite - Baixar - {service}")
        else:
            self.title(f"Media Suite - {meta['window']}")

        self._set_status("Pronto.")

    def _update_nav_appearance(self, active_key):
        for key, btn in self.nav_buttons.items():
            style_name = f"{key}.Active.Nav.TButton" if key == active_key else f"{key}.Nav.TButton"
            btn.configure(style=style_name)

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

    def _schedule_startup_update_check(self):
        if self._is_closing:
            return
        if can_self_update():
            self.check_for_updates(user_initiated=False)

    def _safe_after(self, delay_ms: int, callback):
        if self._is_closing:
            return
        try:
            self.after(delay_ms, callback)
        except tk.TclError:
            pass

    def check_for_updates(self, user_initiated: bool):
        if self._is_closing:
            return
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
            self._safe_after(0, lambda error=exc, initiated=user_initiated: self._finish_update_check_error(error, initiated))
            return

        self._safe_after(
            0,
            lambda update_manifest=manifest, initiated=user_initiated: self._handle_update_manifest(
                update_manifest, initiated
            ),
        )

    def _finish_update_check_error(self, exc: Exception, user_initiated: bool):
        if self._is_closing:
            return
        self.update_check_in_progress = False
        self._set_status("Pronto.")
        if user_initiated:
            if isinstance(exc, UpdateError):
                messagebox.showwarning("Atualizacao", str(exc))
            else:
                messagebox.showerror("Atualizacao", f"Falha ao verificar atualizacoes:\n{exc}")

    def _handle_update_manifest(self, manifest: dict, user_initiated: bool):
        if self._is_closing:
            return
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
            "A atualizacao sera baixada agora e aplicada quando o aplicativo for fechado.\n"
            "Depois disso, basta abrir o app novamente normalmente.\n\n"
            "Deseja continuar?"
        )
        if notes:
            prompt += f"\n\nO que há de novo nesta versão:\n{notes}"

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
                progress_callback=lambda downloaded, total: self._safe_after(
                    0,
                    lambda version=manifest["version"], current=downloaded, total_bytes=total: (
                        self._report_update_download_progress(version, current, total_bytes)
                    ),
                ),
            )
            self._safe_after(
                0,
                lambda downloaded_package=package_path, update_manifest=manifest: self._finish_update_download(
                    downloaded_package, update_manifest
                ),
            )
        except Exception as exc:
            self._safe_after(0, lambda error=exc: self._finish_update_download_error(error))

    def _report_update_download_progress(self, version: str, downloaded: int, total: int):
        if self._is_closing:
            return
        if total > 0:
            percent = int((downloaded / total) * 100)
            self._set_status(f"Baixando atualizacao {version}... {percent}%")
        else:
            self._set_status(f"Baixando atualizacao {version}...")

    def _finish_update_download(self, package_path: Path, manifest: dict):
        if self._is_closing:
            return
        self.update_check_in_progress = False
        self._set_status("Atualizacao pronta para instalar.")

        confirm = messagebox.askyesno(
            "Instalar atualizacao",
            (
                f"A versao {manifest['version']} foi baixada.\n\n"
                "O aplicativo sera fechado para substituir o arquivo atual pela nova versao.\n"
                "Depois disso, abra o aplicativo novamente normalmente.\n\n"
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

        self._set_status("Fechando para concluir a atualizacao...")
        self.destroy()

    def _finish_update_download_error(self, exc: Exception):
        if self._is_closing:
            return
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

    def _on_close(self):
        if self._is_closing:
            return
        self._is_closing = True
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


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


def _try_recover_missing_ffmpeg(root, missing: list[str]) -> bool:
    missing_set = set(missing)
    ffmpeg_missing = {"ffmpeg", "ffprobe"}
    if not missing_set.intersection(ffmpeg_missing):
        return False

    remaining = [item for item in missing if item not in ffmpeg_missing]
    if remaining:
        return False

    download_url = get_ffmpeg_download_url()
    if not download_url:
        return False

    install_dir = ffmpeg_vendor_bin_dir()
    should_install = messagebox.askyesno(
        "FFmpeg ausente",
        (
            "O aplicativo precisa do FFmpeg para iniciar.\n\n"
            "Deseja baixar e instalar automaticamente agora?\n\n"
            f"Destino: {install_dir}"
        ),
        parent=root,
    )
    if not should_install:
        return False

    try:
        messagebox.showinfo(
            "Baixando FFmpeg",
            "O download do FFmpeg vai iniciar agora. Isso pode levar alguns segundos.",
            parent=root,
        )
        download_and_install_ffmpeg(download_url)
        configure_runtime_environment()
    except Exception as exc:
        messagebox.showerror(
            "Falha ao instalar FFmpeg",
            f"Nao foi possivel instalar o FFmpeg automaticamente.\n\n{exc}",
            parent=root,
        )
        return False

    messagebox.showinfo(
        "FFmpeg instalado",
        "O FFmpeg foi instalado com sucesso. O aplicativo vai continuar a abertura.",
        parent=root,
    )
    return True


def main():
    configure_runtime_environment()
    missing, runtime = missing_runtime_requirements()
    if missing:
        try:
            root = tk.Tk()
            root.withdraw()
            if _try_recover_missing_ffmpeg(root, missing):
                missing, runtime = missing_runtime_requirements()

            if missing:
                messagebox.showerror("Dependencias ausentes", runtime_requirement_message(missing, runtime))
            root.destroy()
        except Exception:
            pass

        if missing:
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
