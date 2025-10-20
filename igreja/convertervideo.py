import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import os
import subprocess
import sys
import queue

# --- Drag and Drop (opcional) ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    HAS_DND = False

# --- Dependências opcionais para imagens ---
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import rawpy  # para CR2/RAW
    HAS_RAWPY = True
except Exception:
    HAS_RAWPY = False


def create_no_window_flags():
    """Evita abrir o console no Windows."""
    if sys.platform.startswith("win"):
        return subprocess.CREATE_NO_WINDOW
    return 0


def seconds_to_hms(s):
    try:
        s = float(s)
    except Exception:
        return "00:00:00"
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _ext(path):
    return os.path.splitext(path)[1][1:].lower()


VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}
AUDIO_EXTS = {"wav", "mp3"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "cr2"}

ALL_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS


def is_video_file(path):
    e = _ext(path)
    return e in VIDEO_EXTS or e in AUDIO_EXTS

def is_image_file(path):
    return _ext(path) in IMAGE_EXTS


class VideoConverterApp(ttk.Window if not HAS_DND else TkinterDnD.Tk):
    def __init__(self):
        if HAS_DND:
            super().__init__()
            self.title("Conversor de Vídeo / Imagem")
            self.style = ttk.Style(theme="darkly")
            self.geometry("600x480")
        else:
            super().__init__(title="Conversor de Vídeo / Imagem", themename="darkly", size=(600, 480))

        self.minsize(600, 420)
        self.center_window(600, 480)

        # Estados
        self.input_files = []  # lista de arquivos selecionados
        self.ultimo_arquivo_convertido = ""
        self.formato_destino = tk.StringVar(value="mp4")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_converting = False
        self.proc = None
        self.cancel_requested = False
        self._current_output_path = None
        self.ui_queue = queue.Queue()

        # formatos (vídeo/áudio)
        self.video_formats = ["mp3", "mp4", "avi", "mkv", "mov"]
        # formatos (imagem)
        self.image_formats = ["jpg", "png", "webp", "tiff", "bmp"]

        # modo atual: "video" ou "image"
        self.current_mode = "video"

        self.init_ui()
        self.after(100, self._drain_ui_queue)

        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def center_window(self, width, height):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def init_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Conversor de Vídeo / Imagem", font=("Helvetica", 20, "bold")).pack(pady=(0, 10))

        # Linha Selecionar / Remover
        row = ttk.Frame(container)
        row.pack(pady=5, fill="x")

        ttk.Button(row, text="Selecionar Arquivo(s)", command=self.selecionar_arquivos, bootstyle=WARNING).pack(side="left")
        ttk.Button(row, text="🗑 Remover arquivo(s)", command=self.remover_arquivos, bootstyle=DANGER).pack(side="left", padx=(10, 0))

        # Info do arquivo
        self.label_video = ttk.Label(container, text="Nenhum arquivo selecionado", font=("Helvetica", 12))
        self.label_video.pack(anchor="w", pady=(8, 0))
        self.label_formato = ttk.Label(container, text="", font=("Helvetica", 12))
        self.label_formato.pack(anchor="w")

        if HAS_DND:
            ttk.Label(
                container,
                text="Dica: arraste e solte um ou vários arquivos de vídeo (mp4, avi, mkv...) ou imagem (jpg, png, cr2...), ou até pastas.",
                font=("Helvetica", 10, "italic"),
                foreground="#9aa0a6",
            ).pack(anchor="w", pady=(0, 6))

        # --- Linha do Combobox (inicialmente OCULTA) ---
        self.fmt_row = ttk.Frame(container)
        self.fmt_row_visible = False  # controle de visibilidade

        self.fmt_label = ttk.Label(self.fmt_row, text="Converter para:", font=("Helvetica", 14, "bold"))
        self.fmt_label.pack(side="left")

        self.format_menu = ttk.Combobox(
            self.fmt_row,
            textvariable=self.formato_destino,
            values=[],  # vazio enquanto não houver seleção
            state="readonly"
        )
        self.format_menu.pack(side="left", padx=(10, 0))

        # Botões Converter / Cancelar
        btn_row = ttk.Frame(container)
        btn_row.pack(pady=(10, 6), fill="x")
        self.convert_btn = ttk.Button(btn_row, text="Converter", command=self.start_conversion, bootstyle=SUCCESS)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btn_row, text="Cancelar", command=self.cancel_conversion, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))

        # Progresso + status
        self.progress = ttk.Progressbar(
            container, orient=tk.HORIZONTAL, length=400, mode="determinate",
            variable=self.progress_var, maximum=100
        )
        self.progress.pack(fill="x", pady=(6, 2))
        self.status_label = ttk.Label(container, textvariable=self.status_var, font=("Helvetica", 11))
        self.status_var.set("")
        self.status_label.pack(anchor="w")

        # Abrir pasta
        self.open_btn = ttk.Button(
            container, text="Abrir pasta do arquivo convertido",
            command=self.abrir_pasta, bootstyle=INFO, state=DISABLED
        )
        self.open_btn.pack(pady=10)

    # ---------- Controles de visibilidade do Combobox ----------
    def _show_format_row(self):
        if not self.fmt_row_visible:
            self.fmt_row.pack(pady=(8, 5), fill="x")
            self.fmt_row_visible = True

    def _hide_format_row(self):
        if self.fmt_row_visible:
            self.fmt_row.pack_forget()
            self.fmt_row_visible = False

    # ---------- Atualiza o combobox conforme tipo e seleção ----------
    def _update_format_menu(self):
        if not self.input_files:
            self._hide_format_row()
            self.format_menu.config(values=[])
            return

        # Garante homogeneidade de tipo
        all_video = all(is_video_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)

        if not (all_video or all_image):
            messagebox.showerror("Seleção inválida", "Selecione apenas arquivos de VÍDEO/ÁUDIO ou apenas arquivos de IMAGEM.")
            self._hide_format_row()
            self.format_menu.config(values=[])
            return

        self.current_mode = "image" if all_image else "video"
        values = self.image_formats if self.current_mode == "image" else self.video_formats

        if len(self.input_files) == 1:
            original_ext = _ext(self.input_files[0])
            if original_ext in values:
                values = [v for v in values if v != original_ext]

        self.format_menu.config(values=values)
        if self.formato_destino.get() not in values and values:
            self.formato_destino.set(values[0])

        if values:
            self._show_format_row()
        else:
            self._hide_format_row()

    # ---------- Helpers: coletar arquivos válidos ----------
    def _collect_supported_files(self, paths_or_dirs):
        collected = []
        for item in paths_or_dirs:
            if os.path.isfile(item):
                if _ext(item) in ALL_EXTS:
                    collected.append(os.path.abspath(item))
            elif os.path.isdir(item):
                # sem recursão: apenas arquivos do nível da pasta
                try:
                    for name in os.listdir(item):
                        p = os.path.join(item, name)
                        if os.path.isfile(p) and _ext(p) in ALL_EXTS:
                            collected.append(os.path.abspath(p))
                except Exception:
                    pass
        # remove duplicatas preservando ordem
        seen = set()
        unique = []
        for p in collected:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique.append(p)
        return unique

    # ---------- Drag & Drop ----------
    def _on_drop_files(self, event):
        # Parser nativo do Tk (robusto para chaves, espaços e quebras de linha)
        raw_items = self.tk.splitlist(event.data)
        if not raw_items:
            return
        paths = self._collect_supported_files(raw_items)
        if paths:
            self._set_selected_files(paths)

    # ---------- Seleção / Remoção ----------
    def selecionar_arquivos(self):
        tipos = [
            ("Vídeo/Áudio/Imagem", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v *.wav *.mp3 *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.cr2"),
            ("Vídeos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Áudio", "*.wav *.mp3"),
            ("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.cr2"),
            ("Todos", "*.*"),
        ]
        caminhos = filedialog.askopenfilenames(title="Selecione arquivo(s)", filetypes=tipos)
        if caminhos:
            self._set_selected_files(list(caminhos))

    def _set_selected_files(self, caminhos):
        self.input_files = list(caminhos)
        if not self.input_files:
            self.label_video.config(text="Nenhum arquivo selecionado")
            self.label_formato.config(text="")
            self._update_format_menu()
            return

        if len(self.input_files) == 1:
            f = self.input_files[0]
            self.label_video.config(text=f"Arquivo: {os.path.basename(f)}")
            self.label_formato.config(text=f"Formato original: {_ext(f)}")
        else:
            first = os.path.basename(self.input_files[0])
            self.label_video.config(text=f"{len(self.input_files)} arquivos selecionados (ex.: {first})")
            self.label_formato.config(text="Formatos originais variados")

        self._update_format_menu()

    def remover_arquivos(self):
        self.input_files = []
        self.label_video.config(text="Nenhum arquivo selecionado")
        self.label_formato.config(text="")
        self.progress_var.set(0)
        self.status_var.set("")
        self.open_btn.config(state=DISABLED)
        self.current_mode = "video"
        self.formato_destino.set("mp4")
        self._hide_format_row()
        self.format_menu.config(values=[])

    # ---------- Conversão ----------
    def start_conversion(self):
        if self.is_converting:
            return
        if not self.input_files:
            messagebox.showerror("Erro", "Selecione arquivo(s) primeiro.")
            return

        # Valida homogeneidade novamente
        all_video = all(is_video_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)
        if not (all_video or all_image):
            messagebox.showerror("Seleção inválida", "Selecione apenas arquivos de VÍDEO/ÁUDIO ou apenas arquivos de IMAGEM.")
            return

        formato_destino = self.formato_destino.get()
        if not formato_destino:
            messagebox.showerror("Erro", "Selecione um formato de saída.")
            return

        self.is_converting = True
        self.cancel_requested = False
        self._current_output_path = None
        self.convert_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Preparando...")

        # dispara worker em lote
        t = threading.Thread(target=self._batch_convert_worker, args=(self.input_files[:], formato_destino), daemon=True)
        t.start()

    def cancel_conversion(self):
        if self.is_converting:
            self.cancel_requested = True
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass

    # ---------- Worker de LOTE ----------
    def _batch_convert_worker(self, files, out_ext):
        try:
            total = len(files)
            last_out = None

            for idx, in_path in enumerate(files, start=1):
                if self.cancel_requested:
                    break

                mode = "image" if is_image_file(in_path) and not is_video_file(in_path) else "video"
                pasta_saida = os.path.dirname(in_path)
                base = os.path.splitext(os.path.basename(in_path))[0]
                out_path = os.path.join(pasta_saida, base + f".{out_ext}")
                self._current_output_path = out_path

                self.ui_queue.put(("status", f"[{idx}/{total}] Preparando..."))

                if mode == "image":
                    ok = self._convert_single_image(in_path, out_path, idx, total)
                else:
                    ok = self._convert_single_video(in_path, out_path, idx, total)

                if not ok:
                    if self.cancel_requested:
                        break
                    continue

                last_out = out_path

            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Conversão cancelada."))
            else:
                if last_out:
                    self.ultimo_arquivo_convertido = last_out
                self.ui_queue.put(("done", f"Conversão concluída de {total} arquivo(s)."))

        except Exception as e:
            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Conversão cancelada."))
            else:
                self.ui_queue.put(("error", f"Erro no processamento em lote: {e}"))
        finally:
            self.proc = None
            self.is_converting = False  # <<< garante liberação do estado ao final

    # ---------- Conversão unitária de VÍDEO/ÁUDIO ----------
    def _convert_single_video(self, in_path, out_path, idx, total):
        try:
            duration = self._probe_duration(in_path)
            total_seconds = float(duration) if duration else None

            if out_path.lower().endswith(".mp3"):
                cmd = ["ffmpeg", "-y", "-i", in_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out_path]
            else:
                cmd = ["ffmpeg", "-y", "-i", in_path, out_path]

            creationflags = create_no_window_flags()
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=creationflags
            )

            for line in self.proc.stderr:
                if self.cancel_requested:
                    break
                line = line.strip()
                if "time=" in line:
                    try:
                        t_str = line.split("time=")[1].split(" ")[0]
                        h, m, s = t_str.split(":")
                        sec = float(h) * 3600 + float(m) * 60 + float(s)
                        if total_seconds and total_seconds > 0:
                            pct = max(0.0, min(100.0, (sec / total_seconds) * 100.0))
                            self.ui_queue.put(("progress", pct))
                            self.ui_queue.put(("status", f"[{idx}/{total}] Convertendo... {pct:.1f}% ({seconds_to_hms(sec)} de {seconds_to_hms(total_seconds)})"))
                        else:
                            self.ui_queue.put(("status", f"[{idx}/{total}] Convertendo... {seconds_to_hms(sec)}"))
                    except Exception:
                        pass

            ret = self.proc.wait()

            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False

            if ret == 0:
                self.ui_queue.put(("status", f"[{idx}/{total}] Arquivo convertido: {os.path.basename(out_path)}"))
                return True
            else:
                self.ui_queue.put(("error", f"Falha na conversão do arquivo: {os.path.basename(in_path)}"))
                return False

        except FileNotFoundError:
            self.ui_queue.put(("error", "Não encontrei o ffmpeg/ffprobe. Instale-os e adicione ao PATH."))
            return False
        except Exception as e:
            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            else:
                self.ui_queue.put(("error", f"Erro: {e}"))
                return False
        finally:
            self.proc = None

    # ---------- Conversão unitária de IMAGEM ----------
    def _convert_single_image(self, in_path, out_path, idx, total):
        try:
            if not HAS_PIL:
                self.ui_queue.put(("error", "Conversão de imagens requer Pillow. Instale com: pip install pillow"))
                return False

            self.ui_queue.put(("status", f"[{idx}/{total}] Convertendo imagem..."))

            src_ext = _ext(in_path)
            dst_ext = _ext(out_path)

            if src_ext == "cr2":
                if not HAS_RAWPY:
                    self.ui_queue.put(("error", "Para converter CR2 é necessário instalar o rawpy: pip install rawpy"))
                    return False
                with rawpy.imread(in_path) as raw:
                    rgb = raw.postprocess()
                im = Image.fromarray(rgb)
            else:
                im = Image.open(in_path)

            save_kwargs = {}
            fmt = dst_ext.upper()
            if dst_ext in ("jpg", "jpeg"):
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGB")
                save_kwargs["quality"] = 92
                fmt = "JPEG"
            elif dst_ext == "webp":
                fmt = "WEBP"
                save_kwargs["quality"] = 92
            elif dst_ext in ("tif", "tiff"):
                fmt = "TIFF"
            elif dst_ext == "bmp":
                fmt = "BMP"

            im.save(out_path, fmt, **save_kwargs)

            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False

            self.ui_queue.put(("progress", 100))
            self.ui_queue.put(("status", f"[{idx}/{total}] Arquivo convertido: {os.path.basename(out_path)}"))
            return True

        except Exception as e:
            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            else:
                self.ui_queue.put(("error", f"Erro na conversão de imagem ({os.path.basename(in_path)}): {e}"))
                return False

    def _probe_duration(self, path):
        try:
            creationflags = create_no_window_flags()
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path]
            out = subprocess.check_output(cmd, text=True, creationflags=creationflags, stderr=subprocess.DEVNULL)
            return out.strip()
        except Exception:
            return None

    # ---------- Atualização de UI ----------
    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "progress":
                    self.progress_var.set(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    self.is_converting = False  # <<< importante
                    self.progress_var.set(100)
                    self.status_var.set(payload)
                    self.convert_btn.config(state=NORMAL)
                    self.cancel_btn.config(state=DISABLED)
                    self.open_btn.config(state=NORMAL)
                    messagebox.showinfo("Sucesso", "Conversão concluída!")
                elif kind == "canceled":
                    self.is_converting = False  # <<< importante
                    self.status_var.set(payload)
                    self.progress_var.set(0)
                    self.convert_btn.config(state=NORMAL)
                    self.cancel_btn.config(state=DISABLED)
                    self.open_btn.config(state=DISABLED)
                    self._current_output_path = None
                elif kind == "error":
                    # Mostra erro mas não encerra o lote por padrão
                    messagebox.showerror("Erro", str(payload))
        except queue.Empty:
            pass
        finally:
            if not self.is_converting and self.cancel_btn["state"] == NORMAL:
                self.convert_btn.config(state=NORMAL)
                self.cancel_btn.config(state=DISABLED)
            self.after(100, self._drain_ui_queue)

    # ---------- Abrir pasta ----------
    def abrir_pasta(self):
        if self.ultimo_arquivo_convertido and os.path.exists(self.ultimo_arquivo_convertido):
            pasta = os.path.dirname(self.ultimo_arquivo_convertido)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(pasta)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", pasta])
                else:
                    subprocess.Popen(["xdg-open", pasta])
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo convertido encontrado.")


if __name__ == "__main__":
    app = VideoConverterApp()
    app.mainloop()
