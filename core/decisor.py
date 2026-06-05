# core/decisor.py
from typing import Tuple
from config.configuracoes import carregar_config


def decidir_aposta(previsao: int, confianca: float) -> Tuple[bool, str]:
    """
    Decisão centralizada de aposta.
    Lê o limiar directamente do config para ser sempre consistente.
    Retorna (deve_apostar, motivo).
    """
    config  = carregar_config()
    limiar  = float(config.get("limiar_conf", 0.65))

    if previsao != 1:
        return False, "Previsão negativa"
    if confianca < limiar:
        return False, f"Confiança {confianca:.2f} abaixo do limiar {limiar:.2f}"
    return True, f"Confiança {confianca:.2f} >= limiar {limiar:.2f}"
