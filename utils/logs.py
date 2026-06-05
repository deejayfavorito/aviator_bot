# utils/logs.py
import logging
import os
from datetime import datetime

_configurado = False


def _configurar():
    global _configurado
    if _configurado:
        return
    os.makedirs("logs", exist_ok=True)
    nome = datetime.now().strftime("logs/%Y-%m-%d.log")
    logging.basicConfig(
        filename=nome,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"
    )
    _configurado = True


def log(msg: str, level: str = "info"):
    """Imprime no ecrã e regista no ficheiro de log."""
    _configurar()
    print(msg)
    fn = getattr(logging, level, None)
    if callable(fn):
        fn(msg)
    else:
        logging.info(msg)
