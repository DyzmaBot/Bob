"""Prosty, atomowy zapis ustawień DyzmaBota (bez zapisu tokenów)."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path

DEFAULT_STATE = {
    "schedule": "Godziny transmisji będą ogłaszane tutaj. Obserwuj serwer, żeby niczego nie przegapić.",
    "welcome": "Witaj w społeczności NikodemDyzmaYT! Rozgość się na czacie, poznaj ekipę i baw się dobrze.",
    "messages": {},
    "last_youtube_live_id": "",
    "last_manual_live_url": "",
}

class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = copy.deepcopy(DEFAULT_STATE)
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Plik danych nie zawiera obiektu JSON")
            for key in self.data:
                if key in loaded and isinstance(loaded[key], type(self.data[key])):
                    self.data[key] = loaded[key]

    def get(self, key: str):
        return self.data[key]

    def set(self, key: str, value):
        if key not in DEFAULT_STATE:
            raise KeyError(key)
        if not isinstance(value, type(DEFAULT_STATE[key])):
            raise TypeError(key)
        self.data[key] = value
        self.save()

    def save(self):
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temp.replace(self.path)
