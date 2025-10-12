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


class VideoConverterApp(ttk.Window if not HAS_DND else TkinterDnD.Tk):
    def __init__(self):
        if HAS_DND:
            # Com DnD herdamos de TkinterDnD.Tk e aplicamos o tema do ttkbootstrap
            super().__init__()
            self.title("Conversor de Vídeo")
            self.style = ttk.Style(theme="darkly")
            self.geometry("600x480")  # <--- altura maior
        else:
            super().__init__(title="Conversor de Vídeo", themename="darkly", size=(600, 480))  # <--- altura maior

        # Evita ficar menor que o necessário (para o botão aparecer sempre)
        self.minsize(600, 420)

        self.center_window(600, 480)  # <--- centraliza com a nova altura
        self.caminho_video = ""
        self.ultimo_arquivo_convertido = ""
        self.formato_destino = tk.StringVar(value="mp4")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_converting = False
        self.proc = None
        self.cancel_requested = False            # <-- controla cancelamento
        self._current_output_path = None         # <-- arquivo de saída atual
        self.ui_queue = queue.Queue()            # thread -> UI

        # --- FORMATS BASE (inclui mp3) ---
        self.base_formats = ["mp3", "mp4", "avi", "mkv", "mov"]
  # NEW

        self.init_ui()
        self.after(100, self._drain_ui_queue)

        # Registrar DnD se disponível
        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def center_window(self, width, height):
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def init_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Conversor de Vídeo", font=("Helvetica", 20, "bold")).pack(pady=(0, 10))

        # Linha Selecionar / Remover
        row = ttk.Frame(container)
        row.pack(pady=5, fill="x")

        ttk.Button(row, text="Selecionar Vídeo", command=self.selecionar_video, bootstyle=WARNING).pack(side="left")
        ttk.Button(row, text="🗑 Remover vídeo", command=self.remover_video, bootstyle=DANGER).pack(side="left", padx=(10, 0))

        # Info do arquivo
        self.label_video = ttk.Label(container, text="Nenhum arquivo selecionado", font=("Helvetica", 12))
        self.label_video.pack(anchor="w", pady=(8, 0))
        self.label_formato = ttk.Label(container, text="", font=("Helvetica", 12))
        self.label_formato.pack(anchor="w")

        if HAS_DND:
            ttk.Label(
                container,
                text="Dica: arraste e solte um arquivo de vídeo aqui.",
                font=("Helvetica", 10, "italic"),
                foreground="#9aa0a6",
            ).pack(anchor="w", pady=(0, 6))

        # Formato
        fmt_row = ttk.Frame(container)
        fmt_row.pack(pady=(8, 5), fill="x")
        ttk.Label(fmt_row, text="Converter para:", font=("Helvetica", 14, "bold")).pack(side="left")
        self.format_menu = ttk.Combobox(
            fmt_row,
            textvariable=self.formato_destino,
            values=self.base_formats,              # NEW: lista base
            state="readonly"
        )
        self.format_menu.pack(side="left", padx=(10, 0))
        # garante coerência inicial
        self._update_format_menu()                 # NEW

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
        self.open_btn.pack(pady=10)  # <--- agora cabe com folga

    # ---------- Atualiza opções do combobox removendo o formato original ----------
    def _update_format_menu(self, original_ext=None):
        values = list(self.base_formats)
        if original_ext and original_ext in values:
            values.remove(original_ext)
        self.format_menu.config(values=values)
        current = self.formato_destino.get()
        if current not in values and values:
            self.formato_destino.set(values[0])

    # ---------- Drag & Drop ----------
    def _on_drop_files(self, event):
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.split()
        if path:
            path = path[0]
            if os.path.isfile(path):
                self._set_selected_file(path)

    # ---------- Seleção / Remoção ----------
    def selecionar_video(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=[("Arquivos de mídia", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v *.wav *.mp3")],  # NEW
        )
        if caminho:
            self._set_selected_file(caminho)

    def _set_selected_file(self, caminho):
        self.caminho_video = caminho
        formato_original = os.path.splitext(caminho)[1][1:].lower()
        self.label_video.config(text=f"Arquivo: {os.path.basename(caminho)}")
        self.label_formato.config(text=f"Formato original: {formato_original}")
        self._update_format_menu(formato_original)   # NEW

    def remover_video(self):
        self.caminho_video = ""
        self.label_video.config(text="Nenhum arquivo selecionado")
        self.label_formato.config(text="")
        self.progress_var.set(0)
        self.status_var.set("")
        self.open_btn.config(state=DISABLED)
        # volta lista para base (sem filtro de origem)
        self._update_format_menu(None)               # NEW

    # ---------- Conversão ----------
    def start_conversion(self):
        if self.is_converting:
            return
        if not self.caminho_video:
            messagebox.showerror("Erro", "Selecione um vídeo primeiro.")
            return

        formato_destino = self.formato_destino.get()
        pasta_saida = os.path.dirname(self.caminho_video)
        nome_saida = os.path.splitext(os.path.basename(self.caminho_video))[0] + f".{formato_destino}"
        caminho_saida = os.path.join(pasta_saida, nome_saida)

        self.is_converting = True
        self.cancel_requested = False
        self._current_output_path = caminho_saida
        self.convert_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Preparando...")

        t = threading.Thread(target=self._convert_worker, args=(self.caminho_video, caminho_saida), daemon=True)
        t.start()

    def cancel_conversion(self):
        if self.is_converting:
            self.cancel_requested = True
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass

    def _convert_worker(self, in_path, out_path):
        try:
            duration = self._probe_duration(in_path)
            total_seconds = float(duration) if duration else None

            # NEW: se destino for mp3, extrai só o áudio
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
                            self.ui_queue.put(("status", f"Convertendo... {pct:.1f}% ({seconds_to_hms(sec)} de {seconds_to_hms(total_seconds)})"))
                        else:
                            self.ui_queue.put(("status", f"Convertendo... {seconds_to_hms(sec)}"))
                    except Exception:
                        pass

            ret = self.proc.wait()

            if self.cancel_requested:
                # Apaga arquivo parcial e sinaliza cancelamento
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                self.ui_queue.put(("canceled", "Conversão cancelada."))
                return

            if ret == 0:
                self.ultimo_arquivo_convertido = out_path
                self.ui_queue.put(("done", f"Vídeo convertido com sucesso!\nArquivo: {os.path.basename(out_path)}"))
            else:
                self.ui_queue.put(("error", "Falha na conversão. Verifique se o arquivo é válido e se o ffmpeg está instalado."))

        except FileNotFoundError:
            self.ui_queue.put(("error", "Não encontrei o ffmpeg/ffprobe. Instale-os e adicione ao PATH."))
        except Exception as e:
            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                self.ui_queue.put(("canceled", "Conversão cancelada."))
            else:
                self.ui_queue.put(("error", f"Erro: {e}"))
        finally:
            self.proc = None

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
                    self.is_converting = False
                    self.progress_var.set(100)
                    self.status_var.set(payload)
                    self.convert_btn.config(state=NORMAL)
                    self.cancel_btn.config(state=DISABLED)
                    self.open_btn.config(state=NORMAL)  # <--- fica visível e habilitada
                    messagebox.showinfo("Sucesso", "Conversão concluída!")
                elif kind == "canceled":
                    self.is_converting = False
                    self.status_var.set(payload)  # "Conversão cancelada."
                    self.progress_var.set(0)
                    self.convert_btn.config(state=NORMAL)
                    self.cancel_btn.config(state=DISABLED)
                    self.open_btn.config(state=DISABLED)
                    self._current_output_path = None
                elif kind == "error":
                    self.is_converting = False
                    self.convert_btn.config(state=NORMAL)
                    self.cancel_btn.config(state=DISABLED)
                    self.open_btn.config(state=DISABLED)
                    self.status_var.set("")
                    messagebox.showerror("Erro", str(payload))
        except queue.Empty:
            pass
        finally:
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
