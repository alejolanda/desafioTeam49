"""Hace importable la raiz del proyecto desde los tests (`import app`, `from src import ...`)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
