from __future__ import annotations


BUTTON_CLASSES = {
    "Button",
    "TButton",
    "Checkbutton",
    "TCheckbutton",
    "Radiobutton",
    "TRadiobutton",
    "Menubutton",
    "TMenubutton",
}


def _choose_cursor(widget) -> str | None:
    widget_class = widget.winfo_class()
    if widget_class in BUTTON_CLASSES:
        return "hand2"
    return None


def _apply_widget_cursor(widget) -> None:
    try:
        current_cursor = str(widget.cget("cursor") or "").strip()
    except Exception:
        current_cursor = ""

    if current_cursor:
        return

    cursor = _choose_cursor(widget)
    if not cursor:
        return

    try:
        widget.configure(cursor=cursor)
    except Exception:
        pass


def apply_cursor_profile(root) -> None:
    _apply_widget_cursor(root)
    for child in root.winfo_children():
        apply_cursor_profile(child)


def install_cursor_profile(root) -> None:
    if getattr(root, "_cursor_profile_installed", False):
        apply_cursor_profile(root)
        return

    root._cursor_profile_installed = True

    def _handle_map(event):
        widget = getattr(event, "widget", None)
        if widget is not None:
            _apply_widget_cursor(widget)

    root.bind_all("<Map>", _handle_map, add="+")
    apply_cursor_profile(root)
