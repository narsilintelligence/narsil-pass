"""La CSP de la interfaz: sin red, pero compatible con el puente de pywebview.

La prueba de la ventana real (scripts/humo_ventana.py) demostró que sin 'unsafe-eval' el puente
no funciona (pywebview usa new Function y eval). Esto vigila las dos cosas a la vez."""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("fichero", ["ui/index.html", "ui/dist/index.html"])
def test_csp(fichero):
    ruta = RAIZ / fichero
    if not ruta.exists():
        pytest.skip("interfaz sin compilar")
    csp = re.search(r'Content-Security-Policy"\s+content="([^"]+)"', ruta.read_text(encoding="utf-8")).group(1)
    reglas = {r.split()[0]: r.split()[1:] for r in (x.strip() for x in csp.split(";")) if r}
    assert reglas["default-src"] == ["'none'"]
    assert reglas["connect-src"] == ["'none'"]
    assert "'unsafe-eval'" in reglas["script-src"]
    assert not any(v.startswith(("http", "ws", "*")) for vs in reglas.values() for v in vs)


def test_ningun_fichero_choca_por_mayusculas():
    """Windows no distingue mayúsculas: dos módulos como Identidad.tsx e identidad.ts serían el mismo y la
    compilación de Windows fallaría. Ningún par de rutas del repo puede diferir solo en mayúsculas."""
    import subprocess
    rutas = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split()
    vistas: dict[str, str] = {}
    for r in rutas:
        sin_ext = r.rsplit(".", 1)[0].lower() if r.startswith("ui/src/") else r.lower()
        assert sin_ext not in vistas, f"{r} choca con {vistas[sin_ext]} en Windows"
        vistas[sin_ext] = r
