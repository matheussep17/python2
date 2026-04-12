import os
from tkinter import filedialog

from app.utils import get_output_folder, save_output_folder


class OutputFolderMixin:
    def init_output_folder(self, empty_label: str) -> None:
        self.destination_folder = get_output_folder()
        self._destination_folder_empty_label = empty_label

    def get_destination_label_text(self) -> str:
        return self.destination_folder or self._destination_folder_empty_label

    def choose_dest_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return ""

        self.destination_folder = save_output_folder(folder)
        dest_label = getattr(self, "dest_label", None)
        if dest_label is not None:
            dest_label.config(text=self.get_destination_label_text())
        return self.destination_folder

    def resolve_output_dir(self, fallback_path: str) -> str:
        fallback_dir = os.path.dirname(fallback_path) if fallback_path else ""
        return self.destination_folder or fallback_dir

    def ensure_output_dir(self, fallback_path: str) -> str:
        output_dir = self.resolve_output_dir(fallback_path)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
