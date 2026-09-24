"""Punto de entrada de NARSIL Pass (también el que empaqueta PyInstaller)."""
import sys

from app.lanzador import main

if __name__ == "__main__":
    sys.exit(main())
