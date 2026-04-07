from __future__ import annotations

import tkinter as tk


THEME_PROFILES = {
    "Escuro": {
        "ttk_theme": "darkly",
        "window_bg": "#111827",
        "top_bg": "#0F172A",
        "side_bg": "#0B1220",
        "content_bg": "#111827",
        "status_bg": "#0F172A",
        "title_fg": "#E2E8F0",
        "subtitle_fg": "#94A3B8",
        "muted_fg": "#9CA3AF",
        "lyrics_accent": "#E879F9",
    },
    "Claro": {
        "ttk_theme": "litera",
        "window_bg": "#F5F7FB",
        "top_bg": "#FFFFFF",
        "side_bg": "#EEF3FA",
        "content_bg": "#F5F7FB",
        "status_bg": "#FFFFFF",
        "title_fg": "#0F172A",
        "subtitle_fg": "#334155",
        "muted_fg": "#64748B",
        "lyrics_accent": "#BE185D",
    },
}


def resolve_mode(mode: str | None) -> str:
    if mode == "Claro":
        return "Claro"
    return "Escuro"


def resolve_ttk_theme(mode: str | None) -> str:
    normalized = resolve_mode(mode)
    return THEME_PROFILES[normalized]["ttk_theme"]


def apply_design_system(window, style, mode: str | None) -> None:
    normalized = resolve_mode(mode)
    profile = THEME_PROFILES[normalized]

    window.app_theme_mode = normalized.lower()
    # Fonte base do aplicativo mais legível e com aparência profissional
    window.option_add("*Font", "{Segoe UI} 11")

    style.configure("TopBar.TFrame", background=profile["top_bg"])
    style.configure("SideBar.TFrame", background=profile["side_bg"])
    style.configure("ContentArea.TFrame", background=profile["content_bg"])
    style.configure("StatusBar.TFrame", background=profile["status_bg"])

    style.configure(
        "AppHeader.TLabel",
        font=("Segoe UI", 24, "bold"),
        foreground=profile["title_fg"],
        background=profile["top_bg"],
    )
    style.configure(
        "AppSubHeader.TLabel",
        font=("Segoe UI", 16),
        foreground=profile["subtitle_fg"],
        background=profile["top_bg"],
    )
    style.configure(
        "SectionTitle.TLabel",
        font=("Segoe UI", 18, "bold"),
    )
    style.configure(
        "Muted.TLabel",
        foreground=profile["muted_fg"],
    )
    style.configure(
        "SidebarHint.TLabel",
        foreground=profile["muted_fg"],
        background=profile["side_bg"],
    )
    style.configure(
        "Status.TLabel",
        foreground=profile["muted_fg"],
        background=profile["status_bg"],
    )

    style.configure("TButton", font=("Segoe UI", 11, "bold"), padding=(12, 8))
    # Keep navigation buttons compact and consistently spaced.
    style.configure("Nav.TButton", font=("Segoe UI", 11, "bold"), padding=(10, 8), anchor="w")
    style.configure(
        "Lyrics.Nav.TButton",
        font=("Segoe UI", 11, "bold"),
        padding=(10, 8),
        anchor="w",
        foreground=profile["lyrics_accent"],
        background=profile["side_bg"],
        bordercolor=profile["lyrics_accent"],
        darkcolor=profile["side_bg"],
        lightcolor=profile["side_bg"],
    )
    style.map(
        "Lyrics.Nav.TButton",
        foreground=[("pressed", profile["lyrics_accent"]), ("active", profile["lyrics_accent"])],
        background=[("pressed", profile["side_bg"]), ("active", profile["side_bg"])],
        bordercolor=[("pressed", profile["lyrics_accent"]), ("active", profile["lyrics_accent"])],
    )
    style.configure(
        "Lyrics.Active.Nav.TButton",
        font=("Segoe UI", 11, "bold"),
        padding=(10, 8),
        anchor="w",
        foreground="#FFFFFF",
        background=profile["lyrics_accent"],
        bordercolor=profile["lyrics_accent"],
        darkcolor=profile["lyrics_accent"],
        lightcolor=profile["lyrics_accent"],
    )
    style.map(
        "Lyrics.Active.Nav.TButton",
        foreground=[("pressed", "#FFFFFF"), ("active", "#FFFFFF")],
        background=[("pressed", profile["lyrics_accent"]), ("active", profile["lyrics_accent"])],
        bordercolor=[("pressed", profile["lyrics_accent"]), ("active", profile["lyrics_accent"])],
    )
    style.configure("TEntry", font=("Segoe UI", 11), padding=8)
    style.configure("TCombobox", font=("Segoe UI", 11), padding=6)
    style.configure("Horizontal.TProgressbar", thickness=10)

    try:
        window.configure(background=profile["window_bg"])
    except tk.TclError:
        pass

