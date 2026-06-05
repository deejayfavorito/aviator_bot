# gestor/inteligencia_adaptativa.py
"""
Inteligência adaptativa do bot — 3 módulos:

1. adaptive_strategy: ajusta o cashout alvo com base nos últimos 20 resultados
2. hot_cold_detection: pausa preventivamente em streaks frias (SESSÃO ACTUAL)
3. preservar_banca: reduz aposta quando lucro acumulado ultrapassa limiar

NOVA versão do hot_cold_detection (Maio 2026):
  - Só conta apostas da SESSÃO ACTUAL (não persiste entre sessões)
  - Exige MIN_APOSTAS_PARA_AVALIAR antes de pausar
  - Pausa temporária com limite de rondas, depois volta a tentar
"""
from typing import Tuple, List
from collections import deque
import json
from pathlib import Path

from config.configuracoes import carregar_config


# ═══════════════════════════════════════════════════════════════════════════
# HOT/COLD DETECTION — Estado na MEMÓRIA (não em ficheiro!)
# ═══════════════════════════════════════════════════════════════════════════

# Apostas reais desta sessão (apenas ganhou/perdeu, não inclui pulado)
# Deque limitado às últimas 10 apostas REAIS
_resultados_sessao: deque = deque(maxlen=10)

# Estado da pausa
_em_pausa: bool = False
_rondas_em_pausa: int = 0

# Constantes
MIN_APOSTAS_PARA_AVALIAR = 10   # só avalia hot/cold após N apostas REAIS
WIN_RATE_MINIMO = 0.30           # abaixo deste win rate → pausa
DURACAO_PAUSA_RONDAS = 5         # quantas rondas pausa antes de voltar


def _adicionar_resultado_sessao(vitoria: bool):
    """Regista UMA aposta REAL (ganhou ou perdeu). Não conta pulados."""
    _resultados_sessao.append(1 if vitoria else 0)


def _resetar_pausa():
    """Sai da pausa."""
    global _em_pausa, _rondas_em_pausa
    _em_pausa = False
    _rondas_em_pausa = 0


def _entrar_pausa():
    """Entra em pausa preventiva."""
    global _em_pausa, _rondas_em_pausa
    _em_pausa = True
    _rondas_em_pausa = 0


def deve_pausar() -> Tuple[bool, str]:
    """
    Avalia se deve pausar a aposta (hot/cold detection).

    REGRAS NOVAS (inteligentes):
      1. Se hot_cold_detection OFF → nunca pausa
      2. Se já em pausa → continua pausa até DURACAO_PAUSA_RONDAS
      3. Se < MIN_APOSTAS_PARA_AVALIAR apostas reais nesta sessão → não avalia
      4. Se win rate das últimas N apostas < WIN_RATE_MINIMO → entra em pausa

    Returns:
        (deve_pausar, mensagem)
    """
    global _em_pausa, _rondas_em_pausa

    cfg = carregar_config()
    if not cfg.get("hot_cold_detection", False):
        return False, ""

    # Caso 2: Já em pausa
    if _em_pausa:
        _rondas_em_pausa += 1
        if _rondas_em_pausa >= DURACAO_PAUSA_RONDAS:
            _resetar_pausa()
            return False, "🌡️  Saindo da pausa preventiva. A retomar apostas."
        rondas_rest = DURACAO_PAUSA_RONDAS - _rondas_em_pausa
        return True, f"❄️  Pausa preventiva ({_rondas_em_pausa}/{DURACAO_PAUSA_RONDAS}) — mais {rondas_rest} rondas"

    # Caso 3: Não há apostas suficientes para avaliar
    n_apostas = len(_resultados_sessao)
    if n_apostas < MIN_APOSTAS_PARA_AVALIAR:
        return False, ""

    # Caso 4: Calcular win rate e decidir
    win_rate = sum(_resultados_sessao) / n_apostas
    if win_rate < WIN_RATE_MINIMO:
        _entrar_pausa()
        return True, (
            f"❄️  COLD streak: win rate {win_rate*100:.0f}% "
            f"nas últimas {n_apostas} apostas REAIS desta sessão. "
            f"Pausa preventiva ({DURACAO_PAUSA_RONDAS} rondas)."
        )

    return False, ""


def registar_aposta_real_hot_cold(vitoria: bool):
    """
    Função pública: chamar SEMPRE que houver uma aposta REAL (ganhou/perdeu).
    NÃO chamar quando a aposta foi pulada.
    """
    _adicionar_resultado_sessao(vitoria)


def info_hot_cold() -> str:
    """Retorna info debug sobre o estado actual."""
    n = len(_resultados_sessao)
    if n == 0:
        return "hot_cold: 0 apostas reais ainda"
    wr = sum(_resultados_sessao) / n * 100
    estado = " [PAUSA]" if _em_pausa else ""
    return f"hot_cold: {n} apostas, win rate {wr:.0f}%{estado}"


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTIVE STRATEGY — ajusta cashout alvo com base em performance
# ═══════════════════════════════════════════════════════════════════════════

_ultimas_apostas_adaptive: deque = deque(maxlen=20)


def registar_resultado_adaptive(alvo: float, ganhou: bool):
    """Regista um resultado para o adaptive_strategy."""
    _ultimas_apostas_adaptive.append({"alvo": alvo, "ganhou": ganhou})


def ajustar_alvo(cashout_alvo: float) -> Tuple[float, str]:
    """
    Ajusta o cashout alvo dinamicamente.

    Se as últimas 20 apostas têm win rate alto (>80%) → pode tentar alvo mais alto
    Se win rate baixo (<60%) → reduz alvo para o mínimo (1.20x)

    Returns:
        (cashout_ajustado, motivo)
    """
    cfg = carregar_config()
    if not cfg.get("adaptive_strategy", False):
        return cashout_alvo, ""

    n = len(_ultimas_apostas_adaptive)
    if n < 10:
        return cashout_alvo, ""

    ganhos = sum(1 for a in _ultimas_apostas_adaptive if a["ganhou"])
    win_rate = ganhos / n

    if win_rate >= 0.85 and cashout_alvo == 1.20:
        # Win rate excelente em 1.20x — tentar 1.30x
        return 1.30, f"adaptive: WR {win_rate*100:.0f}% — subindo alvo 1.20→1.30"

    if win_rate < 0.60 and cashout_alvo > 1.20:
        # Win rate baixo num alvo alto — voltar a 1.20x
        return 1.20, f"adaptive: WR {win_rate*100:.0f}% — descendo alvo {cashout_alvo:.2f}→1.20"

    return cashout_alvo, ""


# ═══════════════════════════════════════════════════════════════════════════
# PRESERVAR BANCA — reduz aposta quando lucro acumula
# ═══════════════════════════════════════════════════════════════════════════

def ajustar_valor(valor_proposto: float, lucro_actual: float) -> Tuple[float, str]:
    """
    Reduz o valor da aposta proporcionalmente ao lucro acumulado.

    Tiers:
      lucro < limiar              → valor original (sem mudança)
      lucro >= limiar (1000)      → 50% do valor (mínimo: aposta_base)
      lucro >= 2*limiar (2000)    → 30% do valor (mínimo: aposta_base)
      lucro >= 3*limiar (3000)    → aposta_base apenas

    Returns:
        (valor_ajustado, motivo)
    """
    cfg = carregar_config()
    if not cfg.get("preservar_banca", False):
        return valor_proposto, ""

    limiar = cfg.get("preservar_banca_limiar", 1000.0)
    aposta_base = cfg.get("aposta_base", 100)

    if lucro_actual < limiar:
        return valor_proposto, ""

    if lucro_actual >= 3 * limiar:
        return aposta_base, (
            f"preservar: 🛡️  MÁXIMO (lucro {lucro_actual:.0f}) | valor "
            f"{valor_proposto:.0f}→{aposta_base}"
        )

    if lucro_actual >= 2 * limiar:
        valor_reduzido = max(aposta_base, valor_proposto * 0.30)
        return valor_reduzido, (
            f"preservar: 🛡️  ALTO (lucro {lucro_actual:.0f}) | valor "
            f"{valor_proposto:.0f}→{valor_reduzido:.0f}"
        )

    # Tier MÉDIO (1x-2x limiar)
    valor_reduzido = max(aposta_base, valor_proposto * 0.50)
    if valor_reduzido < valor_proposto:
        return valor_reduzido, (
            f"preservar: 🛡️  MÉDIO (lucro {lucro_actual:.0f}) | valor "
            f"{valor_proposto:.0f}→{valor_reduzido:.0f}"
        )
    return valor_proposto, ""
