# utils/jogo.py
import re
import os
from datetime import datetime
from typing import List


def extrair_multiplicadores(texto: str) -> List[float]:
    """Extrai multiplicadores válidos de texto OCR."""
    return [
        float(m) for m in re.findall(r"(\d+\.\d{1,2})x?", texto)
        if 0.8 <= float(m) <= 500.0
    ]


def salvar_multiplicador(valor: float, arquivo: str = "data/historico.csv") -> bool:
    """
    Salva crash no histórico com formato consistente:
    timestamp, crash_registado, valor
    """
    try:
        os.makedirs("data", exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"{ts},crash_registado,{valor:.2f}x\n")
        print(f"💾 Crash salvo: {valor:.2f}x")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")
        return False
