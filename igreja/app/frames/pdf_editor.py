import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import *

from app.ui.output_folder import OutputFolderMixin
from app.utils import DND_FILES, HAS_DND, HAS_PIL, HAS_PYMUPDF, fitz


PDF_EXTS = {"pdf"}
COLOR_CHOICES = [
    ("Vermelho", "#ff4d4f"),
    ("Laranja", "#ff8c42"),
    ("Amarelo", "#ffd166"),
    ("Verde", "#06d6a0"),
    ("Azul", "#118ab2"),
    ("Roxo", "#9b5de5"),
    ("Branco", "#ffffff"),
    ("Preto", "#111111"),
]
MIN_TEXT_WIDTH = 60.0
DEFAULT_TEXT_WIDTH = 220.0


def is_pdf_file(path: str) -> bool:
    return os.path.splitext(path)[1][1:].lower() in PDF_EXTS


def hex_to_rgb(color: str):
    value = (color or "").strip().lstrip("#")
    if len(value) != 6:
        return (1.0, 1.0, 1.0)
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


class PdfEditorFrame(OutputFolderMixin, ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.pdf_path = ""
        self.pdf_doc = None
        self.page_count = 0
        self.current_page_index = 0
        self.page_annotations = {}
        self.last_output = ""
        self.init_output_folder("Mesma pasta do PDF aberto")

        self.render_scale = 1.0
        self.current_page_size = (0.0, 0.0)
        self.current_render_size = (0, 0)
        self.current_image = None
        self.current_canvas_items = []
        self.canvas_item_roles = {}
        self.thumbnail_images = []
        self.thumbnail_buttons = []
        self.annotation_seq = 0

        self.current_pen_annotation = None
        self.drag_mode = None
        self.drag_annotation_id = None
        self.drag_last_pdf = None
        self.text_drag_start = None
        self.text_preview_item = None
        self.text_drag_origin_annotation_id = None
        self.selected_annotation_id = None
        self.active_text_editor = None
        self.active_text_window = None
        self.active_text_annotation_id = None

        self.output_name_var = tk.StringVar()
        self.page_var = tk.StringVar(value="0 / 0")
        self.status_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)
        self.tool_var = tk.StringVar(value="select")
        self.color_name_var = tk.StringVar(value=COLOR_CHOICES[0][0])
        self.brush_size_var = tk.IntVar(value=4)
        self.font_size_var = tk.IntVar(value=18)
        self.zoom_var = tk.StringVar(value="100%")

        self.is_running = False
        self.ui_queue = queue.Queue()
        self.auto_fit = True
        self._last_action_key_ts = 0.0

        self.color_map = {name: value for name, value in COLOR_CHOICES}
        self.tool_var.trace_add("write", self._on_tool_changed)

        self._build_ui()
        self.bind_all("<Return>", self._handle_return_key, add="+")
        self.bind_all("<Escape>", self._handle_escape_key, add="+")
        self.after(100, self._drain_ui_queue)

        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def _build_ui(self):
        # Create a canvas with scrollbar for scrolling content
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(self.canvas_frame, highlightthickness=0)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)

        self.card = ttk.Frame(self.scroll_canvas, padding=18)
        self.card_window = self.scroll_canvas.create_window((0, 0), window=self.card, anchor="nw")
        self.card.bind("<Configure>", self._on_card_configure)

        header = ttk.Frame(self.card)
        header.pack(fill="x")
        ttk.Label(header, text="Editor de PDF", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(self.card).pack(fill="x", pady=12)

        intro = ttk.LabelFrame(self.card, text="Arquivo")
        intro.pack(fill="x")
        intro_inner = ttk.Frame(intro, padding=12)
        intro_inner.pack(fill="x")
        intro_inner.columnconfigure(2, weight=1)

        self.select_btn = ttk.Button(intro_inner, text="Abrir PDF", command=self.select_file, bootstyle=WARNING)
        self.select_btn.grid(row=0, column=0, sticky="w")
        self.clear_btn = ttk.Button(intro_inner, text="Limpar", command=self.clear_file, bootstyle=DANGER)
        self.clear_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.selection_label = ttk.Label(intro_inner, text="Nenhum PDF aberto", font=("Helvetica", 12))
        self.selection_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 4))
        ttk.Label(
            intro_inner,
            text="Abra um PDF para visualizar as paginas, desenhar, criar caixas de texto e ajustar as anotacoes.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        if HAS_DND:
            ttk.Label(
                intro_inner,
                text="Arraste e solte um PDF aqui para abrir rapidamente.",
                style="Muted.TLabel",
            ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        if not HAS_PYMUPDF or not HAS_PIL:
            missing = []
            if not HAS_PYMUPDF:
                missing.append("PyMuPDF")
            if not HAS_PIL:
                missing.append("Pillow")
            ttk.Label(
                intro_inner,
                text=f"Dependencias ausentes para o editor visual: {', '.join(missing)}.",
                bootstyle="warning",
            ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
            self.select_btn.config(state=DISABLED)
            self.clear_btn.config(state=DISABLED)

        self.tools_frame = ttk.LabelFrame(self.card, text="Ferramentas")
        self.tools_frame.pack(fill="x", pady=(10, 6))
        tools_inner = ttk.Frame(self.tools_frame, padding=12)
        tools_inner.pack(fill="x")

        ttk.Radiobutton(tools_inner, text="Selecionar", value="select", variable=self.tool_var, bootstyle="toolbutton").pack(
            side="left"
        )
        ttk.Radiobutton(tools_inner, text="Desenhar", value="pen", variable=self.tool_var, bootstyle="toolbutton").pack(
            side="left", padx=(8, 0)
        )
        ttk.Radiobutton(tools_inner, text="Texto", value="text", variable=self.tool_var, bootstyle="toolbutton").pack(
            side="left", padx=(8, 0)
        )
        ttk.Radiobutton(tools_inner, text="Borracha", value="erase", variable=self.tool_var, bootstyle="toolbutton").pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(tools_inner, text="Cor").pack(side="left", padx=(18, 6))
        self.color_box = ttk.Combobox(
            tools_inner,
            textvariable=self.color_name_var,
            values=[name for name, _value in COLOR_CHOICES],
            state="readonly",
            width=12,
        )
        self.color_box.pack(side="left")
        self.color_box.bind("<<ComboboxSelected>>", self._on_text_style_control_changed)
        ttk.Label(tools_inner, text="Traco").pack(side="left", padx=(18, 6))
        self.brush_spin = ttk.Spinbox(tools_inner, from_=1, to=24, textvariable=self.brush_size_var, width=6)
        self.brush_spin.pack(side="left")
        ttk.Label(tools_inner, text="Fonte").pack(side="left", padx=(18, 6))
        self.font_spin = ttk.Spinbox(tools_inner, from_=8, to=72, textvariable=self.font_size_var, width=6)
        self.font_spin.pack(side="left")
        self.font_spin.bind("<KeyRelease>", self._on_text_style_control_changed)
        self.font_spin.bind("<FocusOut>", self._on_text_style_control_changed)

        self.text_row = ttk.Frame(self.card)
        self.text_row.pack(fill="x", pady=(0, 6))
        ttk.Label(
            self.text_row,
            text="No modo texto, clique na pagina para criar a caixa e digitar direto no documento.",
            style="Muted.TLabel",
        ).pack(side="left", fill="x", expand=True)
        self.delete_btn = ttk.Button(
            self.text_row, text="Apagar selecionado", command=self.delete_selected_annotation, bootstyle="danger-outline"
        )
        self.delete_btn.pack(side="left")

        self.adjust_row = ttk.Frame(self.card)
        self.adjust_row.pack(fill="x", pady=(0, 6))
        self.font_minus_btn = ttk.Button(
            self.adjust_row, text="Fonte -", command=lambda: self._adjust_selected_text_font(-2), bootstyle="info-outline"
        )
        self.font_minus_btn.pack(side="left")
        self.font_plus_btn = ttk.Button(
            self.adjust_row, text="Fonte +", command=lambda: self._adjust_selected_text_font(2), bootstyle="info-outline"
        )
        self.font_plus_btn.pack(side="left", padx=(8, 0))
        self.width_minus_btn = ttk.Button(
            self.adjust_row, text="Mais estreito", command=lambda: self._adjust_selected_text_width(-20), bootstyle="info-outline"
        )
        self.width_minus_btn.pack(side="left", padx=(18, 0))
        self.width_plus_btn = ttk.Button(
            self.adjust_row, text="Mais largo", command=lambda: self._adjust_selected_text_width(20), bootstyle="info-outline"
        )
        self.width_plus_btn.pack(side="left", padx=(8, 0))
        ttk.Label(
            self.adjust_row,
            text="No modo texto, clique para digitar. No modo selecionar, arraste para mover e use o puxador lateral para largura.",
            style="Muted.TLabel",
        ).pack(side="left", padx=(18, 0))

        self.nav_frame = ttk.Frame(self.card)
        self.nav_frame.pack(fill="x", pady=(0, 8))
        self.prev_btn = ttk.Button(self.nav_frame, text="Pagina anterior", command=lambda: self._change_page(-1), bootstyle=SECONDARY)
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(self.nav_frame, text="Proxima pagina", command=lambda: self._change_page(1), bootstyle=SECONDARY)
        self.next_btn.pack(side="left", padx=(10, 0))
        ttk.Label(self.nav_frame, textvariable=self.page_var, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(14, 0))
        ttk.Button(self.nav_frame, text="Zoom -", command=lambda: self._change_zoom(-0.15), bootstyle="secondary-outline").pack(
            side="left", padx=(18, 0)
        )
        ttk.Label(self.nav_frame, textvariable=self.zoom_var).pack(side="left", padx=(8, 0))
        ttk.Button(self.nav_frame, text="Zoom +", command=lambda: self._change_zoom(0.15), bootstyle="secondary-outline").pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(self.nav_frame, text="Limpar pagina", command=self.clear_current_page_annotations, bootstyle="danger-outline").pack(
            side="right"
        )
        ttk.Button(self.nav_frame, text="Limpar tudo", command=self.clear_all_annotations, bootstyle="danger-outline").pack(
            side="right", padx=(0, 8)
        )

        self.viewer_frame = ttk.Frame(self.card)
        self.viewer_frame.pack(fill="both", expand=True)
        self.viewer_frame.columnconfigure(0, weight=0, minsize=160)
        self.viewer_frame.columnconfigure(1, weight=1)
        self.viewer_frame.rowconfigure(0, weight=1)

        thumbs_wrap = ttk.LabelFrame(self.viewer_frame, text="Paginas")
        thumbs_wrap.grid(row=0, column=0, sticky="nsw", padx=(0, 8), pady=(0, 0))
        thumbs_inner = ttk.Frame(thumbs_wrap, padding=8)
        thumbs_inner.pack(fill="both", expand=True)
        self.thumbs_canvas = tk.Canvas(thumbs_inner, width=170, highlightthickness=0, bg="#162033")
        self.thumbs_canvas.pack(side="left", fill="both", expand=True)
        self.thumbs_scroll = ttk.Scrollbar(thumbs_inner, orient="vertical", command=self.thumbs_canvas.yview)
        self.thumbs_scroll.pack(side="left", fill="y")
        self.thumbs_canvas.configure(yscrollcommand=self.thumbs_scroll.set)
        self.thumbs_frame = ttk.Frame(self.thumbs_canvas)
        self.thumbs_window = self.thumbs_canvas.create_window((0, 0), window=self.thumbs_frame, anchor="nw")
        self.thumbs_frame.bind("<Configure>", self._on_thumbs_configure)
        self.thumbs_canvas.bind("<Configure>", self._on_thumbs_canvas_configure)

        canvas_wrap = ttk.LabelFrame(self.viewer_frame, text="Pagina")
        canvas_wrap.grid(row=0, column=1, sticky="nsew")
        canvas_wrap.columnconfigure(0, weight=1)
        canvas_wrap.rowconfigure(0, weight=1)
        canvas_inner = ttk.Frame(canvas_wrap, padding=10)
        canvas_inner.pack(fill="both", expand=True)
        canvas_inner.rowconfigure(0, weight=1)
        canvas_inner.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_inner, bg="#20242c", highlightthickness=0, cursor="cross")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.v_scroll = ttk.Scrollbar(canvas_inner, orient="vertical", command=self.canvas.yview)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll = ttk.Scrollbar(canvas_inner, orient="horizontal", command=self.canvas.xview)
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)

        self.output_frame = ttk.LabelFrame(self.card, text="Saida")
        self.output_frame.pack(fill="x", pady=(10, 0))
        output_inner = ttk.Frame(self.output_frame, padding=12)
        output_inner.pack(fill="x")
        output_inner.columnconfigure(1, weight=1)

        ttk.Label(output_inner, text="Nome do arquivo", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.output_entry = ttk.Entry(output_inner, textvariable=self.output_name_var, width=32)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ttk.Button(output_inner, text="Escolher pasta de destino", command=self.choose_dest_folder, bootstyle=SUCCESS).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.dest_label = ttk.Label(
            output_inner,
            text=self.get_destination_label_text(),
            style="Muted.TLabel",
        )
        self.dest_label.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(8, 0))

        self.actions_frame = ttk.Frame(self.card)
        self.actions_frame.pack(fill="x", pady=(8, 4))
        self.save_btn = ttk.Button(self.actions_frame, text="Salvar PDF anotado", command=self.start_export, bootstyle=SUCCESS)
        self.save_btn.pack(side="left")
        self.open_btn = ttk.Button(
            self.actions_frame, text="Abrir pasta do PDF", command=self.open_folder, bootstyle=INFO, state=DISABLED
        )
        self.open_btn.pack(side="left", padx=(10, 0))

        self.progress_frame = ttk.Frame(self.card, padding=(10, 6))
        self.progress = ttk.Progressbar(
            self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100
        )
        self.progress.pack(fill="x")
        ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11)).pack(anchor="w", pady=(6, 0))

        self._hide_progress()
        self._draw_empty_state()
        self._update_editor_visibility()
        self._update_action_state()

    def _selected_color(self):
        return self.color_map.get(self.color_name_var.get(), COLOR_CHOICES[0][1])

    def _on_tool_changed(self, *_args):
        self._update_action_state()

    def _update_editor_visibility(self):
        has_document = bool(self.pdf_doc and self.page_count > 0)
        if has_document:
            if not self.tools_frame.winfo_ismapped():
                self.tools_frame.pack(fill="x", pady=(10, 6))
            if not self.text_row.winfo_ismapped():
                self.text_row.pack(fill="x", pady=(0, 6))
            if not self.adjust_row.winfo_ismapped():
                self.adjust_row.pack(fill="x", pady=(0, 6))
            if not self.nav_frame.winfo_ismapped():
                self.nav_frame.pack(fill="x", pady=(0, 8))
            if not self.viewer_frame.winfo_ismapped():
                self.viewer_frame.pack(fill="both", expand=True)
            if not self.output_frame.winfo_ismapped():
                self.output_frame.pack(fill="x", pady=(10, 0))
            if not self.actions_frame.winfo_ismapped():
                self.actions_frame.pack(fill="x", pady=(8, 4))
            return

        self.tools_frame.pack_forget()
        self.text_row.pack_forget()
        self.adjust_row.pack_forget()
        self.nav_frame.pack_forget()
        self.viewer_frame.pack_forget()
        self.output_frame.pack_forget()
        self.actions_frame.pack_forget()

    def _next_annotation_id(self):
        self.annotation_seq += 1
        return self.annotation_seq

    def _is_active_screen(self):
        top = self.winfo_toplevel()
        return getattr(top, "current_screen", None) == getattr(self, "screen_key", None)

    def _handle_return_key(self, event=None):
        if not self._is_active_screen() or self.is_running:
            return
        if event is not None and event.widget is self.active_text_editor:
            return
        if self.active_text_editor:
            return
        if str(self.save_btn["state"]) != str(NORMAL):
            return
        now = time.monotonic()
        if now - self._last_action_key_ts < 0.35:
            return "break"
        self._last_action_key_ts = now
        self.start_export()
        return "break"

    def _handle_escape_key(self, _event=None):
        if not self._is_active_screen():
            return
        if self.active_text_editor:
            self._cancel_inline_edit()
            return "break"

    def select_file(self):
        if not HAS_PYMUPDF or not HAS_PIL:
            messagebox.showerror("Dependencia ausente", "Instale PyMuPDF e Pillow para usar o editor visual de PDF.")
            return
        path = filedialog.askopenfilename(
            title="Selecione um PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
        )
        if path:
            self._load_pdf(path)

    def _on_drop_files(self, event):
        if not HAS_PYMUPDF or not HAS_PIL:
            return
        items = self.tk.splitlist(event.data)
        for item in items:
            if os.path.isfile(item) and is_pdf_file(item):
                self._load_pdf(os.path.abspath(item))
                return

    def _load_pdf(self, path):
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path) or not is_pdf_file(abs_path):
            messagebox.showerror("Erro", "Selecione um arquivo PDF valido.")
            return

        try:
            doc = fitz.open(abs_path)
            if doc.page_count <= 0:
                raise ValueError("O PDF nao possui paginas.")
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel abrir o PDF: {exc}")
            return

        self._close_document()
        self.pdf_doc = doc
        self.pdf_path = abs_path
        self.page_count = doc.page_count
        self.current_page_index = 0
        self.page_annotations = {}
        self.selected_annotation_id = None
        self.last_output = ""
        self.open_btn.config(state=DISABLED)
        self.selection_label.config(text=f"{os.path.basename(abs_path)} ({self.page_count} pagina(s))")
        self._refresh_output_name()
        self._build_thumbnails()
        self._update_editor_visibility()
        self._render_current_page()
        self._update_action_state()
        self.on_status("PDF carregado para edicao.")

    def clear_file(self):
        self._close_inline_text_editor(save=True)
        self._close_document()
        self.pdf_path = ""
        self.page_count = 0
        self.current_page_index = 0
        self.page_annotations = {}
        self.selected_annotation_id = None
        self.output_name_var.set("")
        self.page_var.set("0 / 0")
        self.selection_label.config(text="Nenhum PDF aberto")
        self.last_output = ""
        self.open_btn.config(state=DISABLED)
        self.progress_var.set(0)
        self.status_var.set("")
        self._clear_thumbnails()
        self._update_editor_visibility()
        self._draw_empty_state()
        self._update_action_state()
        self.on_status("Pronto.")

    def _close_document(self):
        self._close_inline_text_editor(save=True)
        if self.pdf_doc is not None:
            try:
                self.pdf_doc.close()
            except Exception:
                pass
        self.pdf_doc = None
        self.current_image = None
        self.current_canvas_items = []
        self.canvas_item_roles = {}
        self.current_pen_annotation = None
        self.drag_mode = None
        self.drag_annotation_id = None
        self.drag_last_pdf = None
        self.text_drag_start = None
        self.text_preview_item = None
        self.text_drag_origin_annotation_id = None

    def _refresh_output_name(self):
        if not self.pdf_path:
            self.output_name_var.set("")
            return
        base = os.path.splitext(os.path.basename(self.pdf_path))[0]
        self.output_name_var.set(f"{base}_anotado.pdf")

    def _draw_empty_state(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            520,
            240,
            text="Abra um PDF para visualizar e anotar as paginas.",
            fill="#cbd5e1",
            font=("Segoe UI", 16, "bold"),
        )
        self.canvas.create_text(
            520,
            280,
            text="Ferramentas: selecionar, desenhar, texto com caixa ajustavel e borracha.",
            fill="#94a3b8",
            font=("Segoe UI", 11),
        )
        self.canvas.configure(scrollregion=(0, 0, 1040, 560))

    def _build_thumbnails(self):
        self._clear_thumbnails()
        if not self.pdf_doc:
            return

        for page_index in range(self.page_count):
            try:
                page = self.pdf_doc.load_page(page_index)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.22, 0.22), alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                photo = ImageTk.PhotoImage(image)
            except Exception:
                photo = None

            self.thumbnail_images.append(photo)
            btn = ttk.Button(
                self.thumbs_frame,
                text=f"Pagina {page_index + 1}",
                image=photo,
                compound="top",
                style="Nav.TButton",
                command=lambda idx=page_index: self._go_to_page(idx),
                width=16,
            )
            btn.pack(fill="x", pady=(0, 8))
            self.thumbnail_buttons.append(btn)

        self._update_thumbnail_selection()

    def _clear_thumbnails(self):
        for btn in self.thumbnail_buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        self.thumbnail_buttons = []
        self.thumbnail_images = []
        self.thumbs_canvas.configure(scrollregion=(0, 0, 0, 0))

    def _update_thumbnail_selection(self):
        for idx, btn in enumerate(self.thumbnail_buttons):
            btn.configure(bootstyle="warning" if idx == self.current_page_index else "primary-outline")

    def _on_thumbs_configure(self, _event=None):
        self.thumbs_canvas.configure(scrollregion=self.thumbs_canvas.bbox("all"))

    def _on_thumbs_canvas_configure(self, event):
        self.thumbs_canvas.itemconfigure(self.thumbs_window, width=event.width)

    def _render_current_page(self):
        if not self.pdf_doc or self.page_count <= 0:
            self._draw_empty_state()
            return

        try:
            page = self.pdf_doc.load_page(self.current_page_index)
            rect = page.rect
            self.current_page_size = (float(rect.width), float(rect.height))

            # Ajusta automaticamente a escala para preencher a largura disponível
            if self.auto_fit and self.current_page_size[0] > 0:
                canvas_width = max(1, self.canvas.winfo_width())
                fit_scale = canvas_width / self.current_page_size[0]
                fit_scale = min(max(0.55, fit_scale), 2.5)
                if abs(fit_scale - self.render_scale) > 0.01:
                    self.render_scale = fit_scale

            matrix = fitz.Matrix(self.render_scale, self.render_scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.current_image = ImageTk.PhotoImage(image)
            self.current_render_size = (pix.width, pix.height)
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel renderizar a pagina: {exc}")
            return

        self.canvas.delete("all")
        self.canvas_item_roles = {}
        self.canvas.create_image(0, 0, image=self.current_image, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, self.current_render_size[0], self.current_render_size[1]))
        self.page_var.set(f"{self.current_page_index + 1} / {self.page_count}")
        self.zoom_var.set(f"{int(self.render_scale * 100)}%")
        self._update_thumbnail_selection()
        self._redraw_annotations()

    def _on_canvas_configure(self, event):
        if not self.auto_fit or not self.pdf_doc or self.page_count <= 0 or self.current_page_size[0] <= 0:
            return
        fit_scale = max(0.55, min(2.5, event.width / self.current_page_size[0]))
        if abs(fit_scale - self.render_scale) > 0.01:
            self.render_scale = fit_scale
            self._render_current_page()

    def _redraw_annotations(self):
        for item_id in self.current_canvas_items:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass

        self.current_canvas_items = []
        self.canvas_item_roles = {}
        annotations = self.page_annotations.get(self.current_page_index, [])
        for annotation in annotations:
            item_ids = self._draw_annotation(annotation)
            if item_ids:
                self.current_canvas_items.extend(item_ids)

    def _draw_annotation(self, annotation):
        item_ids = []
        ann_id = annotation["id"]

        if annotation["type"] == "pen":
            coords = []
            for x_pos, y_pos in annotation["points"]:
                display_x, display_y = self._pdf_to_canvas(x_pos, y_pos)
                coords.extend([display_x, display_y])
            if len(coords) >= 4:
                item_id = self.canvas.create_line(
                    *coords,
                    fill=annotation["color"],
                    width=max(1, annotation["width"]),
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND,
                    smooth=True,
                )
            elif len(coords) == 2:
                radius = max(2, annotation["width"])
                item_id = self.canvas.create_oval(
                    coords[0] - radius,
                    coords[1] - radius,
                    coords[0] + radius,
                    coords[1] + radius,
                    fill=annotation["color"],
                    outline=annotation["color"],
                )
            else:
                return item_ids

            self.canvas_item_roles[item_id] = (ann_id, "body")
            item_ids.append(item_id)

        elif annotation["type"] == "text":
            display_x, display_y = self._pdf_to_canvas(annotation["x"], annotation["y"])
            display_width = max(MIN_TEXT_WIDTH * self.render_scale, annotation["width"] * self.render_scale)
            font_size = max(8, int(annotation["font_size"] * self.render_scale))
            text_item = self.canvas.create_text(
                display_x,
                display_y,
                text=annotation["text"],
                anchor="nw",
                fill=annotation["color"],
                width=display_width,
                font=("Segoe UI", font_size, "bold"),
            )
            self.canvas_item_roles[text_item] = (ann_id, "body")
            item_ids.append(text_item)

            bbox = self.canvas.bbox(text_item)
            if bbox:
                pad = 6
                if ann_id == self.selected_annotation_id:
                    border = self.canvas.create_rectangle(
                        bbox[0] - pad,
                        bbox[1] - pad,
                        bbox[2] + pad,
                        bbox[3] + pad,
                        outline="#f59e0b",
                        width=2,
                        dash=(6, 4),
                    )
                    self.canvas.tag_lower(border, text_item)
                    self.canvas_item_roles[border] = (ann_id, "body")
                    item_ids.append(border)

                    handle = self.canvas.create_rectangle(
                        bbox[2] + 2,
                        (bbox[1] + bbox[3]) / 2 - 7,
                        bbox[2] + 16,
                        (bbox[1] + bbox[3]) / 2 + 7,
                        fill="#f59e0b",
                        outline="#ffffff",
                    )
                    self.canvas_item_roles[handle] = (ann_id, "resize_width")
                    item_ids.append(handle)

        if ann_id == self.selected_annotation_id and annotation["type"] == "pen":
            bbox = self._annotation_canvas_bbox(annotation)
            if bbox:
                selection = self.canvas.create_rectangle(
                    bbox[0] - 8,
                    bbox[1] - 8,
                    bbox[2] + 8,
                    bbox[3] + 8,
                    outline="#f59e0b",
                    width=2,
                    dash=(6, 4),
                )
                self.canvas_item_roles[selection] = (ann_id, "body")
                item_ids.append(selection)

        return item_ids

    def _annotation_canvas_bbox(self, annotation):
        if annotation["type"] == "pen":
            points = [self._pdf_to_canvas(x_pos, y_pos) for x_pos, y_pos in annotation["points"]]
            if not points:
                return None
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return (min(xs), min(ys), max(xs), max(ys))

        if annotation["type"] == "text":
            display_x, display_y = self._pdf_to_canvas(annotation["x"], annotation["y"])
            display_width = max(MIN_TEXT_WIDTH * self.render_scale, annotation["width"] * self.render_scale)
            temp_item = self.canvas.create_text(
                display_x,
                display_y,
                text=annotation["text"],
                anchor="nw",
                width=display_width,
                font=("Segoe UI", max(8, int(annotation["font_size"] * self.render_scale)), "bold"),
            )
            bbox = self.canvas.bbox(temp_item)
            self.canvas.delete(temp_item)
            return bbox

        return None

    def _go_to_page(self, page_index):
        if not self.pdf_doc or page_index < 0 or page_index >= self.page_count:
            return
        self._close_inline_text_editor(save=True)
        self.current_page_index = page_index
        self.selected_annotation_id = None
        self._render_current_page()
        self.on_status(f"Pagina {page_index + 1} carregada.")

    def _change_page(self, delta):
        self._go_to_page(self.current_page_index + delta)

    def _change_zoom(self, delta):
        self.auto_fit = False
        new_scale = min(2.5, max(0.55, self.render_scale + delta))
        if abs(new_scale - self.render_scale) < 0.001:
            return
        self._close_inline_text_editor(save=True)
        self.render_scale = new_scale
        if self.pdf_doc:
            self._render_current_page()

    def _canvas_to_pdf(self, x_pos, y_pos):
        render_w, render_h = self.current_render_size
        page_w, page_h = self.current_page_size
        if render_w <= 0 or render_h <= 0 or page_w <= 0 or page_h <= 0:
            return (0.0, 0.0)
        return (
            max(0.0, min(page_w, (x_pos / render_w) * page_w)),
            max(0.0, min(page_h, (y_pos / render_h) * page_h)),
        )

    def _pdf_to_canvas(self, x_pos, y_pos):
        render_w, render_h = self.current_render_size
        page_w, page_h = self.current_page_size
        if render_w <= 0 or render_h <= 0 or page_w <= 0 or page_h <= 0:
            return (0.0, 0.0)
        return ((x_pos / page_w) * render_w, (y_pos / page_h) * render_h)

    def _event_to_canvas_coords(self, event):
        x_pos = self.canvas.canvasx(event.x)
        y_pos = self.canvas.canvasy(event.y)
        render_w, render_h = self.current_render_size
        if x_pos < 0 or y_pos < 0 or x_pos > render_w or y_pos > render_h:
            return None
        return (x_pos, y_pos)

    def _current_page_annotations(self):
        return self.page_annotations.setdefault(self.current_page_index, [])

    def _find_annotation(self, annotation_id):
        if annotation_id is None:
            return None
        for annotation in self.page_annotations.get(self.current_page_index, []):
            if annotation["id"] == annotation_id:
                return annotation
        return None

    def _find_annotation_hit(self, canvas_x, canvas_y):
        overlapping = self.canvas.find_overlapping(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3)
        for item_id in reversed(overlapping):
            info = self.canvas_item_roles.get(item_id)
            if info:
                return info
        return (None, None)

    def _set_selected_annotation(self, annotation_id):
        if self.active_text_annotation_id is not None and self.active_text_annotation_id != annotation_id:
            self._close_inline_text_editor(save=True)
        self.selected_annotation_id = annotation_id
        annotation = self._find_annotation(annotation_id)
        if annotation and annotation["type"] == "text":
            for color_name, color_value in COLOR_CHOICES:
                if color_value.lower() == annotation["color"].lower():
                    self.color_name_var.set(color_name)
                    break
            self.font_size_var.set(int(annotation["font_size"]))
        self._redraw_annotations()
        self._update_action_state()

    def _refresh_inline_text_editor_style(self):
        if not self.active_text_editor:
            return
        annotation = self._find_annotation(self.active_text_annotation_id)
        if not annotation:
            return
        self.active_text_editor.configure(
            fg=annotation["color"],
            font=("Segoe UI", max(8, int(annotation["font_size"] * self.render_scale)), "bold"),
        )
        self._resize_inline_text_editor()

    def _resize_inline_text_editor(self, _event=None):
        if not self.active_text_editor or self.active_text_window is None:
            return
        annotation = self._find_annotation(self.active_text_annotation_id)
        if not annotation:
            return
        display_x, display_y = self._pdf_to_canvas(annotation["x"], annotation["y"])
        display_width = max(MIN_TEXT_WIDTH * self.render_scale, annotation["width"] * self.render_scale)
        text_value = self.active_text_editor.get("1.0", "end-1c")
        line_count = max(3, min(14, int(self.active_text_editor.index("end-1c").split(".")[0]) + 1))
        self.active_text_editor.configure(height=line_count)
        self.canvas.coords(self.active_text_window, display_x, display_y)
        self.canvas.itemconfigure(self.active_text_window, width=display_width)

    def _apply_selected_text_style_from_controls(self):
        annotation = self._find_annotation(self.selected_annotation_id)
        if not annotation or annotation["type"] != "text":
            return
        annotation["color"] = self._selected_color()
        try:
            annotation["font_size"] = max(8, min(96, int(self.font_size_var.get() or annotation["font_size"])))
        except Exception:
            pass
        self._redraw_annotations()
        self._refresh_inline_text_editor_style()

    def _on_text_style_control_changed(self, _event=None):
        self._apply_selected_text_style_from_controls()

    def _close_inline_text_editor(self, save=True):
        if not self.active_text_editor:
            return

        annotation = self._find_annotation(self.active_text_annotation_id)
        if annotation and save:
            text_value = self.active_text_editor.get("1.0", "end-1c").strip()
            if text_value:
                annotation["text"] = text_value
            else:
                annotations = self.page_annotations.get(self.current_page_index, [])
                self.page_annotations[self.current_page_index] = [
                    item for item in annotations if item["id"] != self.active_text_annotation_id
                ]
                if self.selected_annotation_id == self.active_text_annotation_id:
                    self.selected_annotation_id = None

        try:
            self.active_text_editor.destroy()
        except Exception:
            pass
        try:
            if self.active_text_window is not None:
                self.canvas.delete(self.active_text_window)
        except Exception:
            pass

        self.active_text_editor = None
        self.active_text_window = None
        self.active_text_annotation_id = None
        self._redraw_annotations()
        self._update_action_state()

    def _open_inline_text_editor(self, annotation_id, focus_end=True):
        annotation = self._find_annotation(annotation_id)
        if not annotation or annotation["type"] != "text":
            return

        self._close_inline_text_editor(save=True)
        self.selected_annotation_id = annotation_id

        display_x, display_y = self._pdf_to_canvas(annotation["x"], annotation["y"])
        display_width = max(MIN_TEXT_WIDTH * self.render_scale, annotation["width"] * self.render_scale)
        editor = tk.Text(
            self.canvas,
            wrap="word",
            undo=True,
            bd=0,
            relief="flat",
            insertwidth=2,
            highlightthickness=1,
            highlightbackground="#d97706",
            highlightcolor="#f59e0b",
            padx=4,
            pady=2,
            bg="#fffdf8",
            fg=annotation["color"],
            font=("Segoe UI", max(8, int(annotation["font_size"] * self.render_scale)), "bold"),
        )
        editor.insert("1.0", annotation.get("text", ""))
        line_count = max(3, min(14, int(editor.index("end-1c").split(".")[0]) + 1))
        editor.configure(height=line_count)
        window_id = self.canvas.create_window(display_x, display_y, anchor="nw", width=display_width, window=editor)

        editor.bind("<KeyRelease>", self._resize_inline_text_editor)
        editor.bind("<Control-Return>", lambda _e: self._finish_inline_edit())
        editor.bind("<Escape>", lambda _e: self._cancel_inline_edit())

        self.active_text_editor = editor
        self.active_text_window = window_id
        self.active_text_annotation_id = annotation_id
        self._redraw_annotations()
        self._update_action_state()
        editor.focus_set()
        if focus_end:
            editor.mark_set("insert", "end-1c")

    def _finish_inline_edit(self):
        self._close_inline_text_editor(save=True)
        self.tool_var.set("select")
        self.on_status("Texto atualizado.")

    def _cancel_inline_edit(self):
        self._close_inline_text_editor(save=False)
        self.tool_var.set("select")

    def _create_text_annotation(self, start_canvas, end_canvas):
        start_pdf = self._canvas_to_pdf(*start_canvas)
        if end_canvas is None:
            x_pos = start_pdf[0]
            y_pos = start_pdf[1]
            width = DEFAULT_TEXT_WIDTH
        else:
            end_pdf = self._canvas_to_pdf(*end_canvas)
            x_pos = min(start_pdf[0], end_pdf[0])
            y_pos = min(start_pdf[1], end_pdf[1])
            width = abs(end_pdf[0] - start_pdf[0])
            width = max(MIN_TEXT_WIDTH, width or DEFAULT_TEXT_WIDTH)

        annotation = {
            "id": self._next_annotation_id(),
            "type": "text",
            "x": x_pos,
            "y": y_pos,
            "width": width,
            "font_size": max(8, int(self.font_size_var.get() or 18)),
            "color": self._selected_color(),
            "text": "",
        }
        self._current_page_annotations().append(annotation)
        self._set_selected_annotation(annotation["id"])
        self._open_inline_text_editor(annotation["id"], focus_end=False)
        self.on_status("Digite o texto direto na caixa criada.")
        return annotation["id"]

    def _erase_annotation_at(self, canvas_x, canvas_y):
        ann_id, _role = self._find_annotation_hit(canvas_x, canvas_y)
        if ann_id is None:
            return
        annotations = self.page_annotations.get(self.current_page_index, [])
        self.page_annotations[self.current_page_index] = [ann for ann in annotations if ann["id"] != ann_id]
        if self.selected_annotation_id == ann_id:
            self.selected_annotation_id = None
        self._redraw_annotations()
        self._update_action_state()
        self.on_status("Anotacao removida.")

    def _on_canvas_press(self, event):
        if self.is_running or not self.pdf_doc:
            return

        if self.active_text_editor:
            self._close_inline_text_editor(save=True)

        canvas_pos = self._event_to_canvas_coords(event)
        if not canvas_pos:
            return

        tool = self.tool_var.get()
        self.drag_mode = None
        self.drag_annotation_id = None
        self.drag_last_pdf = None

        if tool == "erase":
            self._erase_annotation_at(*canvas_pos)
            return

        ann_id, role = self._find_annotation_hit(*canvas_pos)
        if tool == "select":
            self._set_selected_annotation(ann_id)
            if ann_id is None:
                return
            self.drag_annotation_id = ann_id
            self.drag_last_pdf = self._canvas_to_pdf(*canvas_pos)
            self.drag_mode = "resize_width" if role == "resize_width" else "move"
            return

        if tool == "text":
            annotation = self._find_annotation(ann_id)
            if annotation and annotation["type"] == "text":
                self._set_selected_annotation(ann_id)
                self._open_inline_text_editor(ann_id)
                self.on_status("Edite o texto direto na pagina.")
                return

            self._set_selected_annotation(None)
            self._create_text_annotation(canvas_pos, None)
            return

        if tool == "pen":
            self._set_selected_annotation(None)
            pdf_x, pdf_y = self._canvas_to_pdf(*canvas_pos)
            annotation = {
                "id": self._next_annotation_id(),
                "type": "pen",
                "points": [(pdf_x, pdf_y)],
                "width": max(1, int(self.brush_size_var.get() or 4)),
                "color": self._selected_color(),
            }
            self._current_page_annotations().append(annotation)
            self.current_pen_annotation = annotation
            self._redraw_annotations()

    def _on_canvas_drag(self, event):
        if self.is_running or not self.pdf_doc:
            return

        canvas_pos = self._event_to_canvas_coords(event)
        if not canvas_pos:
            return

        if self.current_pen_annotation:
            pdf_x, pdf_y = self._canvas_to_pdf(*canvas_pos)
            points = self.current_pen_annotation["points"]
            if not points or (abs(points[-1][0] - pdf_x) >= 0.5 or abs(points[-1][1] - pdf_y) >= 0.5):
                points.append((pdf_x, pdf_y))
                self._redraw_annotations()
            return

        if self.drag_mode and self.drag_annotation_id:
            annotation = self._find_annotation(self.drag_annotation_id)
            if not annotation:
                return

            pdf_x, pdf_y = self._canvas_to_pdf(*canvas_pos)
            last_x, last_y = self.drag_last_pdf or (pdf_x, pdf_y)
            dx = pdf_x - last_x
            dy = pdf_y - last_y
            self.drag_last_pdf = (pdf_x, pdf_y)

            if self.drag_mode == "move":
                if annotation["type"] == "text":
                    annotation["x"] = max(0.0, annotation["x"] + dx)
                    annotation["y"] = max(0.0, annotation["y"] + dy)
                elif annotation["type"] == "pen":
                    annotation["points"] = [(max(0.0, x_pos + dx), max(0.0, y_pos + dy)) for x_pos, y_pos in annotation["points"]]
                self._redraw_annotations()
                return

            if self.drag_mode == "resize_width" and annotation["type"] == "text":
                annotation["width"] = max(MIN_TEXT_WIDTH, annotation["width"] + dx)
                self._redraw_annotations()

    def _on_canvas_release(self, event):
        if self.current_pen_annotation:
            self.on_status("Desenho adicionado na pagina.")
        self.current_pen_annotation = None
        self.drag_mode = None
        self.drag_annotation_id = None
        self.drag_last_pdf = None

        self.text_drag_start = None
        self.text_drag_origin_annotation_id = None
        if self.text_preview_item:
            self.canvas.delete(self.text_preview_item)
            self.text_preview_item = None

    def _on_canvas_double_click(self, event):
        if self.is_running or not self.pdf_doc:
            return

        canvas_pos = self._event_to_canvas_coords(event)
        if not canvas_pos:
            return

        ann_id, _role = self._find_annotation_hit(*canvas_pos)
        annotation = self._find_annotation(ann_id)
        if annotation and annotation["type"] == "text":
            self._set_selected_annotation(ann_id)
            self._open_inline_text_editor(ann_id)

    def clear_current_page_annotations(self):
        if self.current_page_index in self.page_annotations:
            self.page_annotations.pop(self.current_page_index, None)
            self.selected_annotation_id = None
            self._redraw_annotations()
            self._update_action_state()
            self.on_status("Anotacoes da pagina removidas.")

    def clear_all_annotations(self):
        if not self.page_annotations:
            return
        self.page_annotations = {}
        self.selected_annotation_id = None
        self._redraw_annotations()
        self._update_action_state()
        self.on_status("Todas as anotacoes foram removidas.")

    def delete_selected_annotation(self):
        annotation = self._find_annotation(self.selected_annotation_id)
        if not annotation:
            return
        annotations = self.page_annotations.get(self.current_page_index, [])
        self.page_annotations[self.current_page_index] = [ann for ann in annotations if ann["id"] != self.selected_annotation_id]
        self.selected_annotation_id = None
        self._redraw_annotations()
        self._update_action_state()
        self.on_status("Anotacao selecionada removida.")

    def _adjust_selected_text_font(self, delta):
        annotation = self._find_annotation(self.selected_annotation_id)
        if not annotation or annotation["type"] != "text":
            return
        annotation["font_size"] = max(8, min(96, int(annotation["font_size"]) + delta))
        self.font_size_var.set(annotation["font_size"])
        self._redraw_annotations()
        self._refresh_inline_text_editor_style()
        self.on_status("Tamanho da fonte ajustado.")

    def _adjust_selected_text_width(self, delta):
        annotation = self._find_annotation(self.selected_annotation_id)
        if not annotation or annotation["type"] != "text":
            return
        annotation["width"] = max(MIN_TEXT_WIDTH, annotation["width"] + delta)
        self._redraw_annotations()
        self._refresh_inline_text_editor_style()
        self.on_status("Largura da caixa de texto ajustada.")

    def _update_action_state(self):
        has_document = bool(self.pdf_doc and self.page_count > 0)
        normal_state = NORMAL if has_document and not self.is_running and HAS_PYMUPDF and HAS_PIL else DISABLED
        nav_state = NORMAL if has_document and not self.is_running else DISABLED
        selected = self._find_annotation(self.selected_annotation_id)
        selected_text = bool(selected and selected["type"] == "text")
        text_mode = self.tool_var.get() == "text"

        self.save_btn.config(state=normal_state)
        self.prev_btn.config(state=nav_state)
        self.next_btn.config(state=nav_state)
        self.color_box.config(state="readonly" if normal_state == NORMAL else DISABLED)
        self.brush_spin.config(state=NORMAL if normal_state == NORMAL else DISABLED)
        self.font_spin.config(state=NORMAL if normal_state == NORMAL else DISABLED)
        self.output_entry.config(state=NORMAL if normal_state == NORMAL else DISABLED)
        self.delete_btn.config(state=NORMAL if selected and not self.is_running else DISABLED)
        active_text_controls = NORMAL if text_mode and has_document and not self.is_running else DISABLED
        self.font_minus_btn.config(state=active_text_controls)
        self.font_plus_btn.config(state=active_text_controls)
        self.width_minus_btn.config(state=active_text_controls)
        self.width_plus_btn.config(state=active_text_controls)

        for btn in self.thumbnail_buttons:
            btn.configure(state=nav_state)

        if has_document and text_mode:
            if not self.adjust_row.winfo_ismapped():
                self.adjust_row.pack(fill="x", pady=(0, 6), before=self.nav_frame)
        else:
            self.adjust_row.pack_forget()

    def start_export(self):
        if self.is_running:
            return
        if not self.pdf_path or not self.pdf_doc:
            messagebox.showerror("Erro", "Abra um PDF antes de salvar.")
            return

        self._close_inline_text_editor(save=True)

        output_name = (self.output_name_var.get() or "").strip()
        if not output_name:
            messagebox.showerror("Erro", "Informe um nome para o arquivo de saida.")
            return
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"

        output_dir = self.resolve_output_dir(self.pdf_path)
        output_path = os.path.join(output_dir, output_name)
        try:
            self.ensure_output_dir(self.pdf_path)
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel preparar a pasta de destino:\n{exc}")
            return
        if os.path.abspath(output_path).lower() == os.path.abspath(self.pdf_path).lower():
            messagebox.showerror("Erro", "Escolha um nome diferente do PDF original.")
            return

        annotations = {
            page_index: [self._clone_annotation(item) for item in items]
            for page_index, items in self.page_annotations.items()
        }

        self.is_running = True
        self.last_output = ""
        self.open_btn.config(state=DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Preparando exportacao...")
        self._show_progress()
        self._update_action_state()
        self.on_status("Salvando PDF anotado...")

        threading.Thread(target=self._export_worker, args=(self.pdf_path, output_path, annotations), daemon=True).start()

    def _clone_annotation(self, annotation):
        cloned = dict(annotation)
        if annotation["type"] == "pen":
            cloned["points"] = list(annotation["points"])
        return cloned

    def _export_worker(self, input_path, output_path, annotations):
        try:
            doc = fitz.open(input_path)
            total_pages = max(1, doc.page_count)

            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                page_annotations = annotations.get(page_index, [])

                for annotation in page_annotations:
                    if annotation["type"] == "pen":
                        self._apply_pen_annotation(page, annotation)
                    elif annotation["type"] == "text":
                        rect = fitz.Rect(
                            annotation["x"],
                            annotation["y"],
                            annotation["x"] + max(MIN_TEXT_WIDTH, annotation["width"]),
                            max(annotation["y"] + 24, page.rect.height - 8),
                        )
                        page.insert_textbox(
                            rect,
                            annotation["text"],
                            fontsize=max(8, int(annotation["font_size"])),
                            color=hex_to_rgb(annotation["color"]),
                            overlay=True,
                        )

                pct = ((page_index + 1) / total_pages) * 100.0
                self.ui_queue.put(("progress", pct))
                self.ui_queue.put(("status", f"Processando pagina {page_index + 1}/{total_pages}..."))

            doc.save(output_path, garbage=4, deflate=True)
            doc.close()
            self.ui_queue.put(("done", {"message": "PDF anotado salvo com sucesso.", "last_output": output_path}))
        except Exception as exc:
            self.ui_queue.put(("error", f"Erro ao salvar o PDF anotado: {exc}"))
        finally:
            self.is_running = False

    def _apply_pen_annotation(self, page, annotation):
        color = hex_to_rgb(annotation["color"])
        width = max(1, int(annotation["width"]))
        points = annotation["points"]
        if not points:
            return

        shape = page.new_shape()
        if len(points) == 1:
            x_pos, y_pos = points[0]
            radius = max(1, width)
            shape.draw_oval(fitz.Rect(x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius))
            shape.finish(color=color, fill=color, width=1)
            shape.commit(overlay=True)
            return

        shape.draw_polyline([fitz.Point(x_pos, y_pos) for x_pos, y_pos in points])
        shape.finish(color=color, width=width)
        shape.commit(overlay=True)

    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "progress":
                    self.progress_var.set(float(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                    self.on_status(str(payload))
                elif kind == "done":
                    info = payload if isinstance(payload, dict) else {"message": str(payload)}
                    self.last_output = info.get("last_output") or ""
                    self._finish_ok(info.get("message", "PDF anotado salvo com sucesso."))
                elif kind == "error":
                    self._finish_error(str(payload))
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_ui_queue)

    def _show_progress(self):
        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", pady=(4, 2))

    def _hide_progress(self):
        if self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def _finish_ok(self, message):
        self._hide_progress()
        self.progress_var.set(100)
        self.status_var.set(message)
        self.open_btn.config(state=NORMAL if self.last_output else DISABLED)
        self._update_action_state()
        self.on_status(message)
        messagebox.showinfo("Concluido", message)

    def _finish_error(self, message):
        self._hide_progress()
        self.progress_var.set(0)
        self.status_var.set(message)
        self.open_btn.config(state=DISABLED)
        self._update_action_state()
        self.on_status("Erro ao salvar PDF")
        messagebox.showerror("Erro", message)

    def open_folder(self):
        if not self.last_output or not os.path.exists(self.last_output):
            messagebox.showerror("Erro", "Nenhum PDF gerado foi encontrado.")
            return

        folder = os.path.dirname(self.last_output)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", folder])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel abrir a pasta: {exc}")

    def _on_scroll_canvas_configure(self, event):
        # Ajusta a largura do card para preencher o canvas e garantir responsividade.
        self.scroll_canvas.itemconfigure(self.card_window, width=event.width)

        # Se houver mais espaço vertical, expande o card para não deixar gap no bottom.
        if self.card.winfo_reqheight() < event.height:
            self.scroll_canvas.itemconfigure(self.card_window, height=event.height)
        else:
            self.scroll_canvas.itemconfigure(self.card_window, height=self.card.winfo_reqheight())

        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def _on_card_configure(self, event):
        # Atualiza a área total que pode ser rolada quando o conteúdo muda de tamanho.
        canvas_height = self.scroll_canvas.winfo_height()
        if self.card.winfo_reqheight() < canvas_height:
            self.scroll_canvas.itemconfigure(self.card_window, height=canvas_height)
        else:
            self.scroll_canvas.itemconfigure(self.card_window, height=self.card.winfo_reqheight())

        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
