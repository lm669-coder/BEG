"""Import différé de modules lourds (accélère le démarrage, surtout sur disque réseau)."""

import importlib


class LazyModule:
    def __init__(self, name: str):
        self._name = name
        self._mod = None

    def __getattr__(self, attr):
        if self._mod is None:
            self._mod = importlib.import_module(self._name)
        return getattr(self._mod, attr)
