"""Rutas y preferencias de la aplicación. Aquí nunca se guarda un secreto: solo idioma, bases
recientes (rutas) y tiempos. El usuario puede desactivar la lista de recientes."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.0.0"
EMPAQUETADO = bool(getattr(sys, "frozen", False))
IDIOMAS = ("es", "en", "fr", "de", "it", "pt")


def recursos() -> Path:
    """Carpeta de recursos: la temporal de PyInstaller empaquetado, o la raíz del repo en desarrollo."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def carpeta_datos() -> Path:
    if os.environ.get("NARSIL_PASS_DATOS"):
        base = Path(os.environ["NARSIL_PASS_DATOS"])
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "NARSIL Pass"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "narsil-pass"
    base.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return base


@dataclass
class Preferencias:
    idioma: str = "es"
    recientes: list[str] = field(default_factory=list)
    recordar_recientes: bool = True
    bloqueo_minutos: int = 5
    portapapeles_segundos: int = 12
    autoguardado: bool = True
    copia_previa: bool = True

    @classmethod
    def cargar(cls) -> "Preferencias":
        ruta = carpeta_datos() / "preferencias.json"
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        p = cls()
        for k, v in datos.items():
            if hasattr(p, k) and isinstance(v, type(getattr(p, k))):
                setattr(p, k, v)
        if p.idioma not in IDIOMAS:
            p.idioma = "es"
        p.bloqueo_minutos = max(0, min(p.bloqueo_minutos, 240))
        p.portapapeles_segundos = max(5, min(p.portapapeles_segundos, 300))
        p.recientes = [r for r in p.recientes if isinstance(r, str)][:8]
        return p

    def guardar(self) -> None:
        if not self.recordar_recientes:
            self.recientes = []
        ruta = carpeta_datos() / "preferencias.json"
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, ruta)

    def anotar_reciente(self, ruta: str) -> None:
        if not self.recordar_recientes:
            return
        ruta = os.path.abspath(ruta)
        self.recientes = [ruta] + [r for r in self.recientes if r != ruta][:7]
        self.guardar()
