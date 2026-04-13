# app/frames/lyrics_search.py
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from urllib.parse import quote

import requests
import ttkbootstrap as ttk
from bs4 import BeautifulSoup

from app.ui.theme import get_theme_profile


class LyricsSearchFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status
        self.is_searching = False
        self.cancel_requested = False
        self.ui_queue = queue.Queue()
        self.current_artist = ""
        self.current_song = ""

        self._build_ui()
        self.after(100, self._drain_ui_queue)

    def _build_ui(self):
        """Constroi a interface do usuario."""
        profile = get_theme_profile(getattr(self.winfo_toplevel(), "theme_mode", None))

        card = ttk.Frame(self, padding=20, style="Card.TFrame")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Busca de Letras", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        input_frame = ttk.Labelframe(card, text="Buscar Letra", style="Hero.TLabelframe")
        input_frame.pack(fill="x")

        inner_frame = ttk.Frame(input_frame, padding=14, style="Surface.TFrame")
        inner_frame.pack(fill="x")
        inner_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(inner_frame, text="Artista:", style="SectionLabel.TLabel").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.artist_var = tk.StringVar()
        self.artist_entry = ttk.Entry(inner_frame, textvariable=self.artist_var)
        self.artist_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(inner_frame, text="Musica:", style="SectionLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.song_var = tk.StringVar()
        self.song_entry = ttk.Entry(inner_frame, textvariable=self.song_var)
        self.song_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        button_frame = ttk.Frame(inner_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.search_button = ttk.Button(
            button_frame,
            text="Pesquisar",
            bootstyle="primary",
            command=self._start_search,
        )
        self.search_button.pack(side="left", padx=5)

        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancelar",
            bootstyle="danger-outline",
            command=self._cancel_search,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=5)

        result_frame = ttk.Labelframe(card, text="Letra da Musica", style="TLabelframe")
        result_frame.pack(fill="both", expand=True, pady=(12, 0))

        result_inner = ttk.Frame(result_frame, padding=14, style="Surface.TFrame")
        result_inner.pack(fill="both", expand=True)
        result_inner.grid_rowconfigure(1, weight=1)
        result_inner.grid_columnconfigure(0, weight=1)

        header_frame = ttk.Frame(result_inner, style="Inset.TFrame", padding=12)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        self.song_title_var = tk.StringVar(value="Nenhuma musica carregada")
        ttk.Label(
            header_frame,
            textvariable=self.song_title_var,
            font=("Segoe UI Semibold", 13),
        ).grid(row=0, column=0, sticky="w")

        self.artist_name_var = tk.StringVar(value="")
        ttk.Label(
            header_frame,
            textvariable=self.artist_name_var,
            style="InsetMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        scrollbar = ttk.Scrollbar(result_inner)
        scrollbar.grid(row=1, column=1, sticky="ns")

        self.lyrics_text = tk.Text(
            result_inner,
            wrap="word",
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10,
            undo=True,
            relief="flat",
            bd=0,
            background=profile["panel_alt_bg"],
            foreground=profile["field_fg"],
            insertbackground=profile["field_fg"],
            selectbackground=profile["panel_highlight"],
            selectforeground="#FFFFFF",
        )
        self.lyrics_text.grid(row=1, column=0, sticky="nsew")
        scrollbar.config(command=self.lyrics_text.yview)
        self._build_context_menu()

        self.status_var = tk.StringVar(value="Pronto para pesquisar")
        ttk.Label(card, textvariable=self.status_var, style="CardMuted.TLabel", anchor="w").pack(
            fill="x", pady=(10, 0)
        )

    def _build_context_menu(self):
        """Cria o menu de clique direito para edicao rapida."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copiar", command=lambda: self.lyrics_text.event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Colar", command=lambda: self.lyrics_text.event_generate("<<Paste>>"))
        self.context_menu.add_command(label="Recortar", command=lambda: self.lyrics_text.event_generate("<<Cut>>"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Selecionar tudo", command=self._select_all_lyrics)
        self.lyrics_text.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Exibe o menu de contexto."""
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _select_all_lyrics(self):
        """Seleciona todo o texto da letra."""
        self.lyrics_text.tag_add("sel", "1.0", "end-1c")
        self.lyrics_text.mark_set("insert", "1.0")
        self.lyrics_text.see("insert")

    def _start_search(self):
        """Inicia a busca em uma thread separada."""
        artist = self.artist_var.get().strip()
        song = self.song_var.get().strip()

        if not artist or not song:
            messagebox.showwarning("Aviso", "Por favor, preencha o artista e o nome da musica")
            return

        self.is_searching = True
        self.cancel_requested = False
        self.current_artist = artist
        self.current_song = song
        self.search_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.artist_entry.config(state="disabled")
        self.song_entry.config(state="disabled")

        self._set_status("Pesquisando letras...")

        thread = threading.Thread(target=self._search_lyrics, args=(artist, song), daemon=True)
        thread.start()

    def _cancel_search(self):
        """Cancela a busca."""
        self.cancel_requested = True
        self._set_status("Operacao cancelada")
        self._reset_buttons()

    def _search_lyrics(self, artist: str, song: str):
        """Busca a letra da musica."""
        try:
            self._set_status(f"Procurando: {artist} - {song}...")
            lyrics = self._search_letrasmus(artist, song)

            if self.cancel_requested:
                return

            if lyrics:
                self.ui_queue.put(("success", lyrics, f"{artist} - {song}"))
            else:
                self.ui_queue.put(("error", "Letra nao encontrada. Tente outro artista ou musica.", None))
        except Exception as exc:
            self.ui_queue.put(("error", f"Erro na busca: {exc}", None))

    def _search_letrasmus(self, artist: str, song: str) -> str | None:
        """Busca letra no LetrasMus com multiplas tentativas."""
        try:
            urls = [
                f"https://www.letrasmus.com/s/{quote(artist)}/{quote(song)}",
                f"https://www.letrasmus.com/{quote(artist)}/{quote(song)}",
                f"https://letrasmus.com/s/{quote(artist)}/{quote(song)}",
            ]
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            }
            selectors = [
                ("div", "lyric-content"),
                ("div", "lyrics"),
                ("article", None),
                ("div", "letra"),
            ]

            for url in urls:
                if self.cancel_requested:
                    return None

                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.content, "html.parser")
                    for tag, css_class in selectors:
                        lyrics_div = soup.find(tag, class_=css_class) if css_class else soup.find(tag)
                        if not lyrics_div:
                            continue

                        for script in lyrics_div(["script", "style"]):
                            script.decompose()

                        text = self._clean_lyrics_text(lyrics_div.get_text(separator="\n"))
                        if len(text) > 50:
                            return text
                except Exception:
                    continue

            return self._search_azlyrics(artist, song)
        except Exception as exc:
            print(f"Erro ao buscar em LetrasMus: {exc}")
            return None

    def _search_azlyrics(self, artist: str, song: str) -> str | None:
        """Busca letra no AZLyrics."""
        try:
            artist_formatted = artist.lower().replace(" ", "").replace(".", "")
            song_formatted = song.lower().replace(" ", "").replace(".", "").replace("'", "")
            url = f"https://www.azlyrics.com/lyrics/{artist_formatted}/{song_formatted}.html"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                for div in soup.find_all("div"):
                    classes = div.get("class", [])
                    if classes and any("lyrics" in str(css_class).lower() for css_class in classes):
                        text = self._clean_lyrics_text(div.get_text(separator="\n"))
                        if len(text) > 50:
                            return text

                for div in soup.find_all("div"):
                    text = self._clean_lyrics_text(div.get_text(separator="\n"))
                    lines = [line for line in text.splitlines() if line.strip()]
                    if len(lines) > 20:
                        candidate = "\n".join(lines)
                        if len(candidate) > 500:
                            return candidate

            return self._search_genius(artist, song)
        except Exception as exc:
            print(f"Erro ao buscar em AZLyrics: {exc}")
            return self._search_genius(artist, song)

    def _search_genius(self, artist: str, song: str) -> str | None:
        """Busca letra no Genius como fallback."""
        try:
            search_url = "https://genius.com/api/search"
            params = {"q": f"{artist} {song}"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            hits = data.get("response", {}).get("hits", [])
            if not hits:
                return None

            best_hit = self._select_best_genius_hit(hits, artist, song)
            if not best_hit:
                return None

            song_url = best_hit["result"]["url"]
            song_response = requests.get(song_url, headers=headers, timeout=10)
            song_response.raise_for_status()

            soup = BeautifulSoup(song_response.content, "html.parser")
            lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
            if not lyrics_divs:
                return None

            lyrics_text = "\n\n".join(div.get_text(separator="\n") for div in lyrics_divs)
            lyrics_text = self._clean_lyrics_text(lyrics_text)
            return lyrics_text or None
        except Exception as exc:
            print(f"Erro ao buscar em Genius: {exc}")
            return None

    def _select_best_genius_hit(self, hits, artist: str, song: str):
        """Escolhe o resultado do Genius mais proximo da musica pedida."""
        artist_key = self._normalize_key(artist)
        song_key = self._normalize_key(song)
        ranked_hits = []

        for hit in hits:
            result = hit.get("result", {})
            if result.get("lyrics_state") != "complete":
                continue

            title = result.get("title", "")
            full_title = result.get("full_title", "")
            primary_artist = result.get("primary_artist", {}).get("name", "")
            hit_type = hit.get("type", "")
            url = result.get("url", "")

            score = 0
            title_key = self._normalize_key(title)
            full_title_key = self._normalize_key(full_title)
            primary_artist_key = self._normalize_key(primary_artist)

            if hit_type == "song":
                score += 5
            if song_key and song_key == title_key:
                score += 8
            elif song_key and song_key in title_key:
                score += 5
            elif song_key and song_key in full_title_key:
                score += 3

            if artist_key and artist_key == primary_artist_key:
                score += 8
            elif artist_key and artist_key in primary_artist_key:
                score += 5
            elif artist_key and artist_key in full_title_key:
                score += 2

            if "/albums/" in url.lower():
                score -= 10

            ranked_hits.append((score, hit))

        ranked_hits.sort(key=lambda item: item[0], reverse=True)
        if ranked_hits and ranked_hits[0][0] > 0:
            return ranked_hits[0][1]

        return None

    def _normalize_key(self, value: str) -> str:
        """Normaliza texto para comparacao simples."""
        allowed = []
        for char in value.lower():
            if char.isalnum():
                allowed.append(char)
            elif char.isspace():
                allowed.append(" ")

        return " ".join("".join(allowed).split())

    def _clean_lyrics_text(self, text: str) -> str:
        """Remove excesso de ruido e preserva paragrafos."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_lines = [line.strip() for line in normalized.split("\n")]

        cleaned_lines = []
        blank_streak = 0
        unwanted_snippets = (
            "facebook",
            "instagram",
            "twitter",
            "youtube",
            "whatsapp",
            "advertisement",
            "anuncio",
            "ads",
            "submit corrections",
            "writer(s):",
            "contributors",
            "translations",
            "see ",
            "embed",
            "you may also like",
            "you might also like",
            "search",
        )
        stop_markers = (
            "you may also like",
            "you might also like",
            "contributors",
            "embed",
        )
        started_lyrics = False

        for line in raw_lines:
            lowered = line.lower()
            if any(marker in lowered for marker in stop_markers) and cleaned_lines:
                break
            if any(snippet in lowered for snippet in unwanted_snippets):
                continue
            if self._looks_like_metadata_line(line):
                continue

            if line:
                started_lyrics = True
                cleaned_lines.append(line)
                blank_streak = 0
                continue

            blank_streak += 1
            if started_lyrics and cleaned_lines and blank_streak == 1:
                cleaned_lines.append("")

        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    def _looks_like_metadata_line(self, line: str) -> bool:
        """Filtra linhas que parecem tracklists, anos ou rotulos de pagina."""
        stripped = line.strip()
        lowered = stripped.lower()

        if not stripped:
            return False
        if lowered in {"lyrics", "paroles", "letra"}:
            return True
        if stripped.startswith('"') and stripped.endswith('"'):
            return True
        if stripped.startswith("(") and stripped.endswith(")") and stripped[1:-1].isdigit():
            return True
        if "reloaded" in lowered or "bonus track" in lowered:
            return True
        if lowered.endswith("album") or lowered.endswith("tracklist"):
            return True
        if stripped == self.current_artist or stripped == self.current_song:
            return True

        words = stripped.split()
        if len(words) <= 6 and all(word[:1].isupper() or word.isupper() for word in words if word):
            return True

        return False

    def _drain_ui_queue(self):
        """Processa mensagens da thread de busca."""
        try:
            while True:
                msg_type, content, info = self.ui_queue.get_nowait()

                if msg_type == "success":
                    self._display_lyrics(content, info)
                    self._set_status("Letra encontrada!")
                elif msg_type == "error":
                    messagebox.showerror("Erro", content)
                    self._set_status("Erro na busca")

                self._reset_buttons()
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100 if self.is_searching else 500, self._drain_ui_queue)

    def _display_lyrics(self, lyrics: str, title: str = ""):
        """Exibe a letra no campo de texto."""
        self.lyrics_text.delete("1.0", "end")
        self.song_title_var.set(self.current_song or title or "Musica sem titulo")
        self.artist_name_var.set(self.current_artist or "")
        self.lyrics_text.insert("1.0", lyrics)
        self.lyrics_text.see("1.0")

    def _reset_buttons(self):
        """Reseta os botoes apos a busca."""
        self.is_searching = False
        self.search_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.artist_entry.config(state="normal")
        self.song_entry.config(state="normal")

    def _set_status(self, msg: str):
        """Atualiza a mensagem de status."""
        self.status_var.set(msg)
        self.on_status(msg)
