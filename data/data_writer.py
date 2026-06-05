# data/data_writer.py
import os
from datetime import datetime
from typing import Optional

CAMINHO_CSV = "data/historico.csv"


def registrar_csv(tipo: str, valor: Optional[float] = None) -> None:
    """
    Escritor central de todos os eventos do robô.
    Formato único: timestamp, tipo, valor
    Tipos usados: crash_registado | cashout_ok | crash_perdeu | pulado | falha_aposta
    """
    os.makedirs("data", exist_ok=True)
    ts        = datetime.now().isoformat(timespec="seconds")
    valor_str = f"{valor:.2f}x" if valor is not None else ""
    linha     = f"{ts},{tipo},{valor_str}\n"
    try:
        with open(CAMINHO_CSV, "a", encoding="utf-8") as f:
            f.write(linha)
        print(f"💾 [{tipo}] {valor_str or '—'}")
    except Exception as e:
        print(f"❌ Erro ao escrever CSV: {e}")


def salvar_multiplicador(valor: float) -> None:
    """Regista um crash detectado na lista lateral."""
    if not valor or valor <= 0:
        return
    registrar_csv("crash_registado", valor)


def salvar_resultado_aposta(sucesso: bool, valor: float) -> None:
    """Regista o resultado de uma aposta."""
    registrar_csv("cashout_ok" if sucesso else "crash_perdeu", valor)
