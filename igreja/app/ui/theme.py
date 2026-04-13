from __future__ import annotations

import tkinter as tk


THEME_PROFILES = {
    "Escuro": {
        "ttk_theme": "darkly",
        "window_bg": "#040A14",
        "top_bg": "#07111F",
        "top_border": "#15314F",
        "side_bg": "#09101B",
        "side_panel_bg": "#0C1625",
        "content_bg": "#060E1A",
        "hero_bg": "#0A1728",
        "hero_alt_bg": "#10213A",
        "status_bg": "#07111F",
        "panel_bg": "#0F1C2E",
        "panel_alt_bg": "#13253E",
        "panel_border": "#223858",
        "panel_border_soft": "#162941",
        "panel_highlight": "#7DB8FF",
        "panel_shadow": "#050B14",
        "input_bg": "#081321",
        "input_border": "#35547A",
        "input_focus": "#8FC5FF",
        "title_fg": "#F4F8FF",
        "subtitle_fg": "#B4C3D9",
        "muted_fg": "#7E91AE",
        "field_fg": "#F7FBFF",
        "inverse_fg": "#07111F",
        "nav_accents": {
            "baixar": "#5ED4FF",
            "compressor": "#FFBE5C",
            "converter": "#7DB8FF",
            "editor": "#FF7B9D",
            "lyrics": "#C187FF",
            "pdf": "#19E28F",
            "transcribe": "#7EE081",
        },
    },
    "Claro": {
        "ttk_theme": "litera",
        "window_bg": "#EEF3FA",
        "top_bg": "#F8FBFF",
        "top_border": "#D4E1F1",
        "side_bg": "#E8EFF8",
        "side_panel_bg": "#F6F9FD",
        "content_bg": "#EEF3FA",
        "hero_bg": "#F9FBFE",
        "hero_alt_bg": "#EAF1FB",
        "status_bg": "#F8FBFF",
        "panel_bg": "#FDFEFF",
        "panel_alt_bg": "#F2F6FC",
        "panel_border": "#C8D5E5",
        "panel_border_soft": "#DDE6F2",
        "panel_highlight": "#1F5FAF",
        "panel_shadow": "#E4EBF5",
        "input_bg": "#FFFFFF",
        "input_border": "#B9C8DB",
        "input_focus": "#2A6BC0",
        "title_fg": "#0E1A2B",
        "subtitle_fg": "#41546D",
        "muted_fg": "#697C97",
        "field_fg": "#0E1A2B",
        "inverse_fg": "#FFFFFF",
        "nav_accents": {
            "baixar": "#0F84D8",
            "compressor": "#D78317",
            "converter": "#1F5FAF",
            "editor": "#D64578",
            "lyrics": "#8A49D8",
            "pdf": "#0FAF68",
            "transcribe": "#4F8F2F",
        },
    },
}


NAV_STYLE_KEYS = (
    "baixar",
    "compressor",
    "converter",
    "editor",
    "lyrics",
    "pdf",
    "transcribe",
)


def _normalize_mode(mode: str | tk.Variable | None) -> str | None:
    if hasattr(mode, "get"):
        try:
            mode = mode.get()
        except Exception:
            mode = None
    if mode == "Claro":
        return "Claro"
    return "Escuro"


def resolve_mode(mode: str | tk.Variable | None) -> str:
    return _normalize_mode(mode) or "Escuro"


def resolve_ttk_theme(mode: str | tk.Variable | None) -> str:
    normalized = resolve_mode(mode)
    return THEME_PROFILES[normalized]["ttk_theme"]


def get_theme_profile(mode: str | tk.Variable | None) -> dict:
    normalized = resolve_mode(mode)
    return THEME_PROFILES[normalized]


def apply_design_system(window, style, mode: str | tk.Variable | None) -> None:
    profile = get_theme_profile(mode)

    window.app_theme_mode = resolve_mode(mode).lower()
    window.option_add("*Font", "{Segoe UI} 11")

    style.configure(".", background=profile["panel_bg"], foreground=profile["field_fg"])

    style.configure("TopBar.TFrame", background=profile["top_bg"])
    style.configure("TopBarInner.TFrame", background=profile["top_bg"])
    style.configure("ToolbarGroup.TFrame", background=profile["hero_bg"])
    style.configure("AppBody.TFrame", background=profile["window_bg"])
    style.configure("SideBar.TFrame", background=profile["side_bg"])
    style.configure("SidebarPanel.TFrame", background=profile["side_panel_bg"])
    style.configure("ContentArea.TFrame", background=profile["content_bg"])
    style.configure("HeroPanel.TFrame", background=profile["hero_bg"])
    style.configure("ContentShell.TFrame", background=profile["panel_shadow"])
    style.configure("StatusBar.TFrame", background=profile["status_bg"])
    style.configure("Card.TFrame", background=profile["panel_bg"])
    style.configure("Surface.TFrame", background=profile["panel_bg"])
    style.configure("SurfaceAlt.TFrame", background=profile["panel_alt_bg"])
    style.configure(
        "Inset.TFrame",
        background=profile["panel_alt_bg"],
        bordercolor=profile["panel_border_soft"],
        borderwidth=1,
        relief="flat",
        lightcolor=profile["panel_border_soft"],
        darkcolor=profile["panel_border_soft"],
    )

    style.configure(
        "AppKicker.TLabel",
        font=("Bahnschrift SemiCondensed", 10, "bold"),
        foreground=profile["panel_highlight"],
        background=profile["top_bg"],
    )
    style.configure(
        "AppHeader.TLabel",
        font=("Bahnschrift SemiBold", 24),
        foreground=profile["title_fg"],
        background=profile["top_bg"],
    )
    style.configure(
        "AppSubHeader.TLabel",
        font=("Segoe UI", 11),
        foreground=profile["subtitle_fg"],
        background=profile["top_bg"],
    )
    style.configure(
        "HeaderMeta.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["hero_bg"],
    )
    style.configure(
        "WorkspaceEyebrow.TLabel",
        font=("Bahnschrift SemiCondensed", 10, "bold"),
        foreground=profile["panel_highlight"],
        background=profile["hero_bg"],
    )
    style.configure(
        "WorkspaceTitle.TLabel",
        font=("Bahnschrift SemiBold", 22),
        foreground=profile["title_fg"],
        background=profile["hero_bg"],
    )
    style.configure(
        "WorkspaceSubtitle.TLabel",
        font=("Segoe UI", 11),
        foreground=profile["subtitle_fg"],
        background=profile["hero_bg"],
    )
    style.configure(
        "SectionTitle.TLabel",
        font=("Bahnschrift SemiBold", 18),
        foreground=profile["title_fg"],
        background=profile["panel_bg"],
    )
    style.configure(
        "Muted.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["panel_bg"],
    )
    style.configure(
        "CardMuted.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["panel_bg"],
    )
    style.configure(
        "InsetMuted.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["panel_alt_bg"],
    )
    style.configure(
        "SidebarHint.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["side_panel_bg"],
    )
    style.configure(
        "SidebarSection.TLabel",
        font=("Bahnschrift SemiCondensed", 10, "bold"),
        foreground=profile["subtitle_fg"],
        background=profile["side_panel_bg"],
    )
    style.configure(
        "SidebarTitle.TLabel",
        font=("Bahnschrift SemiBold", 16),
        foreground=profile["title_fg"],
        background=profile["side_panel_bg"],
    )
    style.configure(
        "Status.TLabel",
        font=("Segoe UI", 10),
        foreground=profile["muted_fg"],
        background=profile["status_bg"],
    )
    style.configure(
        "SectionLabel.TLabel",
        font=("Segoe UI Semibold", 10),
        foreground=profile["subtitle_fg"],
        background=profile["panel_bg"],
    )

    style.configure(
        "TButton",
        font=("Segoe UI Semibold", 10),
        padding=(14, 9),
        borderwidth=1,
    )
    style.map(
        "TButton",
        relief=[("pressed", "flat"), ("active", "flat")],
    )
    style.configure(
        "Chrome.TButton",
        font=("Segoe UI Semibold", 10),
        padding=(14, 9),
        background=profile["hero_bg"],
        foreground=profile["title_fg"],
        bordercolor=profile["panel_border"],
        borderwidth=1,
        relief="flat",
        lightcolor=profile["panel_border"],
        darkcolor=profile["panel_border"],
    )
    style.map(
        "Chrome.TButton",
        background=[("active", profile["hero_alt_bg"]), ("pressed", profile["hero_alt_bg"])],
        foreground=[("active", profile["title_fg"]), ("pressed", profile["title_fg"])],
        bordercolor=[("active", profile["panel_highlight"]), ("pressed", profile["panel_highlight"])],
    )
    style.configure(
        "Nav.TButton",
        font=("Segoe UI Semibold", 10),
        padding=(16, 12),
        anchor="w",
        borderwidth=1,
        relief="flat",
    )

    for key in NAV_STYLE_KEYS:
        accent = profile["nav_accents"][key]
        style.configure(
            f"{key}.Nav.TButton",
            font=("Segoe UI Semibold", 10),
            padding=(16, 12),
            anchor="w",
            foreground=accent,
            background=profile["side_panel_bg"],
            bordercolor=accent,
            borderwidth=1,
            relief="flat",
            lightcolor=accent,
            darkcolor=accent,
        )
        style.map(
            f"{key}.Nav.TButton",
            foreground=[("active", profile["title_fg"]), ("pressed", profile["title_fg"])],
            background=[("active", profile["hero_bg"]), ("pressed", profile["hero_bg"])],
            bordercolor=[("active", accent), ("pressed", accent)],
        )
        style.configure(
            f"{key}.Active.Nav.TButton",
            font=("Segoe UI Semibold", 10),
            padding=(16, 12),
            anchor="w",
            foreground=profile["inverse_fg"],
            background=accent,
            bordercolor=accent,
            borderwidth=1,
            relief="flat",
            lightcolor=accent,
            darkcolor=accent,
        )
        style.map(
            f"{key}.Active.Nav.TButton",
            foreground=[("active", profile["inverse_fg"]), ("pressed", profile["inverse_fg"])],
            background=[("active", accent), ("pressed", accent)],
            bordercolor=[("active", accent), ("pressed", accent)],
        )

    style.configure(
        "TLabelframe",
        background=profile["panel_bg"],
        bordercolor=profile["panel_border_soft"],
        borderwidth=1,
        relief="flat",
        lightcolor=profile["panel_border_soft"],
        darkcolor=profile["panel_border_soft"],
    )
    style.configure(
        "TLabelframe.Label",
        font=("Bahnschrift SemiBold", 11),
        foreground=profile["title_fg"],
        background=profile["panel_bg"],
        padding=(12, 4, 12, 8),
    )
    style.configure(
        "Hero.TLabelframe",
        background=profile["panel_bg"],
        bordercolor=profile["panel_highlight"],
        borderwidth=1,
        relief="flat",
        lightcolor=profile["panel_highlight"],
        darkcolor=profile["panel_highlight"],
    )
    style.configure(
        "Hero.TLabelframe.Label",
        font=("Bahnschrift SemiBold", 12),
        foreground=profile["title_fg"],
        background=profile["panel_bg"],
        padding=(12, 4, 12, 8),
    )

    style.configure(
        "TEntry",
        font=("Segoe UI", 10),
        padding=10,
        fieldbackground=profile["input_bg"],
        foreground=profile["field_fg"],
        bordercolor=profile["input_border"],
        insertcolor=profile["field_fg"],
        lightcolor=profile["input_border"],
        darkcolor=profile["input_border"],
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", profile["input_focus"])],
        lightcolor=[("focus", profile["input_focus"])],
        darkcolor=[("focus", profile["input_focus"])],
        fieldbackground=[("readonly", profile["panel_alt_bg"])],
    )
    style.configure(
        "TCombobox",
        font=("Segoe UI", 10),
        padding=8,
        fieldbackground=profile["input_bg"],
        foreground=profile["field_fg"],
        bordercolor=profile["input_border"],
        lightcolor=profile["input_border"],
        darkcolor=profile["input_border"],
        arrowcolor=profile["field_fg"],
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", profile["input_focus"])],
        lightcolor=[("focus", profile["input_focus"])],
        darkcolor=[("focus", profile["input_focus"])],
        fieldbackground=[("readonly", profile["input_bg"])],
        arrowcolor=[("focus", profile["input_focus"])],
    )
    style.configure(
        "TSeparator",
        background=profile["panel_border_soft"],
    )
    style.configure(
        "Horizontal.TProgressbar",
        thickness=10,
        troughcolor=profile["panel_alt_bg"],
        bordercolor=profile["panel_alt_bg"],
        background=profile["panel_highlight"],
        lightcolor=profile["panel_highlight"],
        darkcolor=profile["panel_highlight"],
    )

    window.option_add("*Text.Font", "{Cascadia Mono} 10")
    window.option_add("*Text.Background", profile["panel_alt_bg"])
    window.option_add("*Text.Foreground", profile["field_fg"])
    window.option_add("*Text.InsertBackground", profile["field_fg"])
    window.option_add("*Text.SelectBackground", profile["panel_highlight"])
    window.option_add("*Text.SelectForeground", profile["inverse_fg"])
    window.option_add("*Text.HighlightThickness", 1)
    window.option_add("*Text.HighlightBackground", profile["panel_border"])
    window.option_add("*Text.HighlightColor", profile["input_focus"])

    try:
        window.configure(background=profile["window_bg"])
    except tk.TclError:
        pass
