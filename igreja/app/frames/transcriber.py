# app/frames/transcriber.py
import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import HAS_DND, HAS_FW, HAS_DOCX, DND_FILES, _ext

# ---------- Transcrição ----------
AUDIO_VIDEO_EXTS = {"mp3", "wav", "m4a", "mp4", "mkv", "mov", "webm"}
SUPPORTED_EXTS = AUDIO_VIDEO_EXTS

# Modelo atual (você pode trocar para "medium" se quiser mais qualidade)
WHISPER_MODEL = "large-v2"

# Ajustes para transcrição mais completa
PRIMARY_BEAM_SIZE = 10          # mais completo (mais lento)
FALLBACK_BEAM_SIZE = 16         # fallback ainda mais completo (mais lento)
MIN_TEXT_CHARS_FOR_OK = 120     # se sair menos que isso, considera fraco e tenta fallback


class TranscriberFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.input_files = []
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")

        self.is_running = False
        self.cancel_requested = False
        self.ui_queue = queue.Queue()

        self.last_output = None
        self.model = None

        self._build_ui()
        self.after(100, self._drain_ui_queue)

        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def _build_ui(self):
        card = ttk.Frame(self, padding=18, bootstyle="dark")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text="Transcritor de Áudio (Word)", font=("Helvetica", 18, "bold")).pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        row = ttk.Frame(card)
        row.pack(fill="x")
        ttk.Button(row, text="Selecionar Arquivo(s)", command=self.selecionar_arquivos, bootstyle=WARNING).pack(side="left")
        ttk.Button(row, text="🗑 Remover", command=self.remover_arquivos, bootstyle=DANGER).pack(side="left", padx=(10, 0))

        self.label_sel = ttk.Label(card, text="Nenhum arquivo selecionado", font=("Helvetica", 12))
        self.label_sel.pack(anchor="w", pady=(10, 0))

        ctl = ttk.Frame(card)
        ctl.pack(fill="x", pady=(10, 6))
        self.btn_run = ttk.Button(ctl, text="▶️ Transcrever (mais completo)", command=self.start_transcription, bootstyle=SUCCESS)
        self.btn_run.pack(side="left")
        self.btn_cancel = ttk.Button(ctl, text="Cancelar", command=self.cancel_transcription, bootstyle=SECONDARY, state=DISABLED)
        self.btn_cancel.pack(side="left", padx=(10, 0))

        prog = ttk.Frame(card, padding=10, bootstyle="secondary")
        prog.pack(fill="x", pady=(8, 4))
        self.progress = ttk.Progressbar(prog, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        self.status_lbl = ttk.Label(prog, textvariable=self.status_var, font=("Helvetica", 11))
        self.status_lbl.pack(anchor="w", pady=(6, 0))

        self.btn_open = ttk.Button(card, text="Abrir pasta do último .docx", command=self.abrir_pasta, bootstyle=INFO, state=DISABLED)
        self.btn_open.pack(pady=8)

    def selecionar_arquivos(self):
        tipos = [
            ("Áudio/Vídeo", "*.mp3 *.wav *.m4a *.mp4 *.mkv *.mov *.webm"),
            ("Áudio", "*.mp3 *.wav *.m4a"),
            ("Vídeo", "*.mp4 *.mkv *.mov *.webm"),
            ("Todos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Selecione arquivo(s)", filetypes=tipos)
        if paths:
            self._set_files(list(paths))

    def _on_drop_files(self, event):
        items = self.tk.splitlist(event.data)
        paths = []

        for p in items:
            if os.path.isdir(p):
                try:
                    for nm in os.listdir(p):
                        f = os.path.join(p, nm)
                        if os.path.isfile(f) and _ext(f) in SUPPORTED_EXTS:
                            paths.append(os.path.abspath(f))
                except Exception:
                    pass
            elif os.path.isfile(p) and _ext(p) in SUPPORTED_EXTS:
                paths.append(os.path.abspath(p))

        seen = set()
        uniq = []
        for p in paths:
            low = p.lower()
            if low not in seen:
                seen.add(low)
                uniq.append(p)

        if uniq:
            self._set_files(uniq)

    def _set_files(self, paths):
        paths = [p for p in paths if os.path.isfile(p) and _ext(p) in SUPPORTED_EXTS]
        self.input_files = paths

        if not self.input_files:
            self.label_sel.config(text="Nenhum arquivo selecionado")
            return

        self.label_sel.config(
            text=f"Arquivo: {os.path.basename(paths[0])}"
            if len(paths) == 1 else f"{len(paths)} arquivos (ex.: {os.path.basename(paths[0])})"
        )

    def remover_arquivos(self):
        self.input_files = []
        self.label_sel.config(text="Nenhum arquivo selecionado")
        self.progress_var.set(0)
        self.status_var.set("")
        self.btn_open.config(state=DISABLED)

    def start_transcription(self):
        if self.is_running:
            return

        if not HAS_FW or not HAS_DOCX:
            messagebox.showerror("Dependências", "Para transcrever instale: pip install faster-whisper python-docx")
            return

        if not self.input_files:
            messagebox.showerror("Erro", "Selecione pelo menos um arquivo.")
            return

        self.is_running = True
        self.cancel_requested = False

        self.btn_run.config(state=DISABLED)
        self.btn_cancel.config(state=NORMAL)
        self.btn_open.config(state=DISABLED)

        self.progress_var.set(0)
        self.status_var.set("Preparando...")
        self.on_status("Transcrição iniciada…")

        threading.Thread(target=self._batch_transcribe_worker, args=(self.input_files[:],), daemon=True).start()

    def cancel_transcription(self):
        if self.is_running:
            self.cancel_requested = True

    def _ensure_model(self):
        if self.model is not None:
            return
        self.ui_queue.put(("status", f"Carregando modelo '{WHISPER_MODEL}'..."))
        from faster_whisper import WhisperModel
        # CPU int8: bom pra uso geral em PC comum
        self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        self.ui_queue.put(("status", "Modelo carregado."))

    def _batch_transcribe_worker(self, files):
        try:
            self._ensure_model()
            total = len(files)
            last_out = None

            for idx, path in enumerate(files, start=1):
                if self.cancel_requested:
                    break

                out_path = os.path.join(
                    os.path.dirname(path),
                    os.path.splitext(os.path.basename(path))[0] + ".docx"
                )

                self.ui_queue.put(("status", f"[{idx}/{total}] Transcrevendo: {os.path.basename(path)}"))
                ok = self._transcribe_one(path, out_path, idx, total)

                if ok:
                    last_out = out_path

            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Transcrição cancelada."))
            else:
                if last_out:
                    self.last_output = last_out
                self.ui_queue.put(("done", f"Transcrição concluída de {total} arquivo(s)."))

        except Exception as e:
            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Transcrição cancelada."))
            else:
                self.ui_queue.put(("error", f"Erro no processamento: {e}"))
        finally:
            self.is_running = False

    def _save_docx(self, text, out_docx, info):
        try:
            from docx import Document
        except Exception:
            messagebox.showerror("Dependências", "Instale: pip install python-docx")
            return False

        doc = Document()
        doc.add_heading("Transcrição", level=1)

        # Idioma detectado
        lang = getattr(info, "language", None)
        if lang:
            doc.add_paragraph(f"Idioma detectado: {lang}")
            doc.add_paragraph("")

        doc.add_paragraph(text)
        doc.save(out_docx)
        return True

    def _run_transcribe(self, in_path: str, beam_size: int):
        """
        Executa transcribe com foco em completude:
        - language=None (multi-idioma)
        - vad_filter=False (não cortar fala)
        - beam_size configurável (mais completo)
        """
        return self.model.transcribe(
            in_path,
            language=None,
            vad_filter=False,
            beam_size=beam_size,
            condition_on_previous_text=True
        )

    def _transcribe_one(self, in_path, out_docx, idx, total):
        try:
            # 1) Primeira tentativa (mais completa que o padrão)
            segments, info = self._run_transcribe(in_path, beam_size=PRIMARY_BEAM_SIZE)

            pieces = []
            for seg in segments:
                if self.cancel_requested:
                    break
                t = (seg.text or "").strip()
                if t:
                    pieces.append(t)

            if self.cancel_requested:
                return False

            full = " ".join(pieces).strip()

            # 2) Fallback automático: se veio pouco texto, tentar ainda mais completo
            if len(full) < MIN_TEXT_CHARS_FOR_OK:
                self.ui_queue.put(("status", f"[{idx}/{total}] Resultado curto — tentando modo mais completo..."))
                segments2, info2 = self._run_transcribe(in_path, beam_size=FALLBACK_BEAM_SIZE)

                pieces2 = []
                for seg in segments2:
                    if self.cancel_requested:
                        break
                    t = (seg.text or "").strip()
                    if t:
                        pieces2.append(t)

                if self.cancel_requested:
                    return False

                full2 = " ".join(pieces2).strip()

                # usa o melhor (mais longo)
                if len(full2) > len(full):
                    full = full2
                    info = info2

            if not full:
                self.ui_queue.put(("error", f"Nenhum texto reconhecido em: {os.path.basename(in_path)}"))
                return False

            if not self._save_docx(full, out_docx, info):
                return False

            self.ui_queue.put(("progress", 100))
            self.ui_queue.put(("status", f"[{idx}/{total}] Salvo: {os.path.basename(out_docx)}"))
            return True

        except Exception as e:
            self.ui_queue.put(("error", f"Erro ao transcrever {os.path.basename(in_path)}: {e}"))
            return False

    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "progress":
                    self.progress_var.set(payload)

                elif kind == "status":
                    self.status_var.set(payload)
                    self.on_status(payload)

                elif kind == "done":
                    self.progress_var.set(100)
                    self.status_var.set(payload)
                    self.on_status("Transcrição finalizada")

                    self.btn_run.config(state=NORMAL)
                    self.btn_cancel.config(state=DISABLED)
                    self.btn_open.config(state=NORMAL if self.last_output else DISABLED)
                    messagebox.showinfo("Sucesso", "Transcrição concluída!")

                elif kind == "canceled":
                    self.status_var.set(payload)
                    self.on_status(payload)
                    self.progress_var.set(0)

                    self.btn_run.config(state=NORMAL)
                    self.btn_cancel.config(state=DISABLED)
                    self.btn_open.config(state=DISABLED)

                elif kind == "error":
                    self.on_status("Erro na transcrição")
                    messagebox.showerror("Erro", str(payload))

        except queue.Empty:
            pass
        finally:
            if not self.is_running and self.btn_cancel["state"] == NORMAL:
                self.btn_run.config(state=NORMAL)
                self.btn_cancel.config(state=DISABLED)
            self.after(100, self._drain_ui_queue)

    def abrir_pasta(self):
        if self.last_output and os.path.exists(self.last_output):
            pasta = os.path.dirname(self.last_output)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(pasta)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", pasta])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", pasta])
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo transcrito encontrado.")
