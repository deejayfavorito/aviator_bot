# utils/log_sessao.py
"""
Log estruturado por sessão.

Cria um ficheiro CSV por sessão: data/sessao_YYYY-MM-DD_HH-MM.csv

Cada linha do CSV representa uma aposta com:
  timestamp, multiplicador_round, cashout_alvo, valor_apostado,
  resultado, cashout_obtido, lucro_aposta, banca_acumulada,
  cadeia_pos, cofre, estrategia
"""
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional


_ficheiro_sessao: Optional[Path] = None


def iniciar_sessao() -> Path:
    """Cria um novo CSV para esta sessão. Retorna o caminho."""
    global _ficheiro_sessao
    pasta = Path("data")
    pasta.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    _ficheiro_sessao = pasta / f"sessao_{timestamp}.csv"

    # Escreve cabeçalho
    with open(_ficheiro_sessao, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "multiplicador_round",
            "cashout_alvo",
            "valor_apostado",
            "resultado",
            "cashout_obtido",
            "lucro_aposta",
            "banca_acumulada",
            "cadeia_pos",
            "cofre",
            "estrategia",
        ])

    print(f"📝 Log da sessão: {_ficheiro_sessao}")
    return _ficheiro_sessao


def registar_aposta(
    multiplicador_round: float,
    cashout_alvo: float,
    valor_apostado: float,
    resultado: str,
    cashout_obtido: float,
    lucro_aposta: float,
    banca_acumulada: float,
    cadeia_pos: int,
    cofre: float,
    estrategia: str = "default",
):
    """Adiciona uma linha ao CSV da sessão."""
    if _ficheiro_sessao is None:
        return  # Sessão não foi iniciada

    try:
        with open(_ficheiro_sessao, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                f"{multiplicador_round:.2f}",
                f"{cashout_alvo:.2f}",
                f"{valor_apostado:.2f}",
                resultado,
                f"{cashout_obtido:.2f}",
                f"{lucro_aposta:.2f}",
                f"{banca_acumulada:.2f}",
                cadeia_pos,
                f"{cofre:.2f}",
                estrategia,
            ])
    except Exception as e:
        print(f"⚠️ Erro ao gravar log da sessão: {e}")


def caminho_sessao_actual() -> Optional[Path]:
    return _ficheiro_sessao
