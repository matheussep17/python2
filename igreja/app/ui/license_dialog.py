import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.licensing import (
    LicenseConnectionError,
    LicenseValidationError,
    activate_with_server,
    describe_license_state,
    device_fingerprint,
    device_has_bypass,
    license_is_enforced,
    load_license_settings,
    load_local_license_state,
    local_license_is_usable_offline,
    machine_name,
    validate_with_server,
)
from app.ui.theme import apply_design_system, resolve_ttk_theme


class LicenseActivationWindow(ttk.Window):
    def __init__(self, settings: dict, initial_message: str = ""):
        super().__init__(title="Ativação do aplicativo", themename=resolve_ttk_theme("Escuro"), size=(700, 500))
        style = ttk.Style()
        apply_design_system(self, style, "Escuro")
        self.settings = settings
        self.result = False

        local_state = load_local_license_state()
        self.username_var = tk.StringVar(value=local_state.get("username", ""))
        self.password_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value=initial_message.strip() or "Informe o login e a senha enviados para este computador."
        )
        self.summary_var = tk.StringVar(value=describe_license_state(local_state))
        self.device_var = tk.StringVar(value=f"Computador: {machine_name()}\nFingerprint: {device_fingerprint()}")

        self.minsize(640, 440)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self.after(0, self._enter_fullscreen)

    def _build_ui(self):
        shell = ttk.Frame(self, padding=24, style="AppBody.TFrame")
        shell.pack(fill="both", expand=True)

        card = ttk.Frame(shell, padding=24, style="Card.TFrame")
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="ATIVAÇÃO", style="AppKicker.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Controle de acesso por computador", style="WorkspaceTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            card,
            text=(
                "Este aplicativo agora depende de uma licença vinculada a um único equipamento. "
                "Após a ativação, as funcionalidades continuam iguais."
            ),
            style="WorkspaceSubtitle.TLabel",
            justify="left",
            wraplength=620,
        ).grid(row=2, column=0, sticky="w", pady=(6, 18))

        summary = ttk.Labelframe(card, text="Situação local", style="Hero.TLabelframe")
        summary.grid(row=3, column=0, sticky="ew")
        ttk.Label(
            summary,
            textvariable=self.summary_var,
            style="SurfaceAlt.TLabel",
            justify="left",
            anchor="w",
            padding=12,
        ).pack(fill="x")

        device_info = ttk.Labelframe(card, text="IdentificaÃ§Ã£o deste computador", style="Hero.TLabelframe")
        device_info.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        device_shell = ttk.Frame(device_info, padding=12, style="SurfaceAlt.TFrame")
        device_shell.pack(fill="x")
        ttk.Label(
            device_shell,
            textvariable=self.device_var,
            style="SurfaceAlt.TLabel",
            justify="left",
            anchor="w",
        ).pack(fill="x")
        ttk.Button(
            device_shell,
            text="Copiar identificaÃ§Ã£o",
            command=self._copy_device_info,
            style="Action.TButton",
        ).pack(anchor="w", pady=(10, 0))

        form = ttk.Labelframe(card, text="Credenciais", style="Hero.TLabelframe")
        form.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        inner = ttk.Frame(form, padding=12, style="SurfaceAlt.TFrame")
        inner.pack(fill="x")
        inner.columnconfigure(1, weight=1)

        ttk.Label(inner, text="Login", style="SurfaceAlt.TLabel").grid(row=0, column=0, sticky="w")
        username_entry = ttk.Entry(inner, textvariable=self.username_var, width=36)
        username_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        ttk.Label(inner, text="Senha", style="SurfaceAlt.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))
        password_entry = ttk.Entry(inner, textvariable=self.password_var, show="*", width=36)
        password_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(12, 0))
        password_entry.bind("<Return>", lambda _event: self._activate())

        ttk.Label(
            inner,
            text=(
                "A licença pode ser permanente ou ter validade definida no servidor. "
                "Se a internet cair, o app continua pelo período offline permitido."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
            wraplength=560,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        status_frame = ttk.Frame(card, style="Card.TFrame")
        status_frame.grid(row=6, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", justify="left", wraplength=620).pack(
            fill="x"
        )

        actions = ttk.Frame(card, style="Card.TFrame")
        actions.grid(row=7, column=0, sticky="ew", pady=(18, 0))
        ttk.Button(actions, text="Ativar agora", command=self._activate, style="PrimaryAction.TButton").pack(side="left")
        ttk.Button(actions, text="Validar licença salva", command=self._validate_existing, style="Action.TButton").pack(
            side="left", padx=(10, 0)
        )
        ttk.Button(actions, text="Fechar", command=self._on_close, style="DangerAction.TButton").pack(side="right")

        username_entry.focus_set()

    def _refresh_summary(self, state=None):
        self.summary_var.set(describe_license_state(state or load_local_license_state()))

    def _copy_device_info(self):
        self.clipboard_clear()
        self.clipboard_append(self.device_var.get())
        self.status_var.set("IdentificaÃ§Ã£o deste computador copiada para a Ã¡rea de transferÃªncia.")

    def _enter_fullscreen(self):
        try:
            self.state("zoomed")
            return
        except Exception:
            pass

        try:
            width = max(self.winfo_screenwidth(), 640)
            height = max(self.winfo_screenheight(), 440)
            self.geometry(f"{width}x{height}+0+0")
        except Exception:
            pass

    def _activate(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self.status_var.set("Preencha login e senha antes de ativar.")
            return

        self.status_var.set("Validando licença no servidor...")
        self.update_idletasks()
        try:
            state = activate_with_server(username, password, self.settings)
        except (LicenseConnectionError, LicenseValidationError) as exc:
            self.status_var.set(str(exc))
            return

        self._refresh_summary(state)
        self.status_var.set("Licença ativada com sucesso neste computador.")
        self.result = True
        self.after(250, self.destroy)

    def _validate_existing(self):
        self.status_var.set("Revalidando licença salva...")
        self.update_idletasks()
        try:
            state = validate_with_server(self.settings)
        except (LicenseConnectionError, LicenseValidationError) as exc:
            self.status_var.set(str(exc))
            return

        self._refresh_summary(state)
        self.status_var.set("Licença local revalidada com sucesso.")
        self.result = True
        self.after(250, self.destroy)

    def _on_close(self):
        self.destroy()


def ensure_application_license() -> bool:
    settings = load_license_settings()
    if not license_is_enforced(settings):
        return True
    if device_has_bypass(settings):
        return True

    if not settings.get("api_url"):
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Licenciamento",
                "O licenciamento está ativado, mas 'license_api_url' não foi configurado no config.json.",
                parent=root,
            )
            root.destroy()
        except Exception:
            pass
        return False

    local_state = load_local_license_state()
    if local_state:
        try:
            validate_with_server(settings, local_state)
            return True
        except LicenseConnectionError:
            if local_license_is_usable_offline(local_state):
                return True
            initial_message = (
                "Não foi possível falar com o servidor e o prazo offline desta licença já acabou. "
                "Conecte a internet e valide novamente."
            )
        except LicenseValidationError as exc:
            initial_message = str(exc)
        else:
            initial_message = ""
    else:
        initial_message = "Nenhuma licença ativa foi encontrada neste computador."

    window = LicenseActivationWindow(settings, initial_message=initial_message)
    window.mainloop()
    return bool(window.result)
