# gestor/kelly_criterion.py
"""
Kelly Criterion — bet sizing baseado em probabilidades REAIS.

Fórmula:
  f = (b·p - q) / b

  f = fracção da banca a apostar
  b = retorno líquido por unidade apostada (cashout_alvo - 1)
  p = probabilidade de ganhar (baseada em dados reais)
  q = 1 - p (probabilidade de perder)

Se f < 0, a aposta é matematicamente desfavorável (não apostar).
Se f > 0, é vantajosa. Usa-se uma fracção (1/4 Kelly) para reduzir variância.

MODOS:
  off          → não interfere (usa o valor da Estratégia 2)
  conservador  → usa 25% do Kelly (recomendado)
  pleno        → usa 100% do Kelly (mais agressivo, mais variância)
"""
import csv
from pathlib import Path
from typing import Tuple, Optional
from config.configuracoes import carregar_config


# Min apostas registadas para considerar dados de uma estratégia confiáveis
MIN_AMOSTRAS = 20

# Limites de segurança
FRACCAO_MAX_BANCA = 0.10   # Nunca apostar mais de 10% da banca


def _carregar_apostas_historicas() -> list:
    """Lê todos os sessao_*.csv e retorna apostas concluídas."""
    apostas = []
    pasta = Path("data")
    if not pasta.exists():
        return apostas

    for ficheiro in pasta.glob("sessao_*.csv"):
        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    if linha.get("resultado") in ("ganhou", "perdeu"):
                        try:
                            apostas.append({
                                "cashout_alvo":   float(linha["cashout_alvo"]),
                                "cashout_obtido": float(linha["cashout_obtido"]),
                                "resultado":      linha["resultado"],
                            })
                        except (ValueError, KeyError):
                            continue
        except Exception:
            continue
    return apostas


def calcular_probabilidade_real(cashout_alvo: float) -> Tuple[Optional[float], int]:
    """
    Calcula win rate REAL para um dado cashout_alvo a partir dos dados.

    Retorna (probabilidade, n_amostras).
    Se n_amostras < MIN_AMOSTRAS, retorna (None, n).
    """
    apostas = _carregar_apostas_historicas()

    # Filtra apostas com cashout_alvo próximo (±0.05x para agrupar similares)
    relevantes = [
        a for a in apostas
        if abs(a["cashout_alvo"] - cashout_alvo) < 0.05
    ]

    n = len(relevantes)
    if n < MIN_AMOSTRAS:
        return None, n

    vitorias = sum(1 for a in relevantes if a["resultado"] == "ganhou")
    return vitorias / n, n


def calcular_kelly(cashout_alvo: float, win_rate: float) -> float:
    """
    Calcula a fracção Kelly para um cashout e win rate.

    Retorna a fracção (0 a 1) ou negativo se aposta é desfavorável.
    """
    b = cashout_alvo - 1.0       # Retorno líquido
    p = win_rate
    q = 1.0 - p

    if b <= 0:
        return 0.0

    kelly = (b * p - q) / b
    return kelly


def calcular_valor_kelly(
    banca_actual: float,
    cashout_alvo: float,
    modo: str = "conservador"
) -> Tuple[float, str, dict]:
    """
    Calcula o valor a apostar segundo Kelly Criterion.

    Args:
        banca_actual: dinheiro disponível
        cashout_alvo: o multiplicador alvo para esta aposta
        modo: "off", "conservador", "pleno"

    Retorna:
        (valor_aposta, descricao, diagnostico_dict)
    """
    cfg = carregar_config()
    aposta_base   = float(cfg.get("aposta_base", 100.0))
    aposta_max    = float(cfg.get("aposta_limite_max", 400.0))

    # ── Modo OFF: não interferir ─────────────────────────────────────────
    if modo == "off":
        return aposta_base, "Kelly OFF (aposta base)", {"modo": "off"}

    # ── Obter probabilidade real ─────────────────────────────────────────
    p_real, n_amostras = calcular_probabilidade_real(cashout_alvo)

    if p_real is None:
        # Dados insuficientes — usa estimativa conservadora
        return aposta_base, f"Kelly: amostras insuficientes ({n_amostras}/{MIN_AMOSTRAS}). Usar base.", {
            "modo": modo,
            "p_real": None,
            "n_amostras": n_amostras,
            "fallback": True,
        }

    kelly = calcular_kelly(cashout_alvo, p_real)

    # ── Kelly negativo: aposta desfavorável ──────────────────────────────
    if kelly <= 0:
        return aposta_base, (
            f"⚠️ Kelly NEGATIVO ({kelly:.3f}) com win_rate={p_real*100:.1f}% e cashout {cashout_alvo:.2f}x. "
            f"Aposta desfavorável. Usar apenas base."
        ), {
            "modo": modo,
            "kelly": kelly,
            "p_real": p_real,
            "n_amostras": n_amostras,
            "negativo": True,
        }

    # ── Aplica fracção segundo modo ──────────────────────────────────────
    if modo == "conservador":
        kelly_efectivo = kelly * 0.25
    elif modo == "pleno":
        kelly_efectivo = kelly
    else:
        kelly_efectivo = kelly * 0.25  # default

    # Limita à fracção máxima por segurança
    kelly_efectivo = min(kelly_efectivo, FRACCAO_MAX_BANCA)

    # Calcula valor
    valor = banca_actual * kelly_efectivo

    # Aplica limites
    valor = max(valor, aposta_base)      # mínimo é a aposta base
    valor = min(valor, aposta_max)       # máximo do config

    descricao = (
        f"Kelly {modo}: f={kelly_efectivo:.3f} | "
        f"win_rate={p_real*100:.1f}% ({n_amostras} amostras) | "
        f"valor={valor:.0f}"
    )

    return valor, descricao, {
        "modo": modo,
        "kelly_bruto": kelly,
        "kelly_efectivo": kelly_efectivo,
        "p_real": p_real,
        "n_amostras": n_amostras,
        "valor": valor,
    }


def diagnostico() -> dict:
    """Retorna diagnóstico das estratégias usadas até agora."""
    apostas = _carregar_apostas_historicas()
    por_cashout = {}

    for a in apostas:
        c = a["cashout_alvo"]
        if c not in por_cashout:
            por_cashout[c] = {"total": 0, "wins": 0}
        por_cashout[c]["total"] += 1
        if a["resultado"] == "ganhou":
            por_cashout[c]["wins"] += 1

    resultado = {}
    for c, s in sorted(por_cashout.items()):
        if s["total"] >= MIN_AMOSTRAS:
            p = s["wins"] / s["total"]
            kelly = calcular_kelly(c, p)
            resultado[c] = {
                "total":     s["total"],
                "wins":      s["wins"],
                "win_rate":  p,
                "kelly":     kelly,
                "vantajoso": kelly > 0,
            }
        else:
            resultado[c] = {
                "total":     s["total"],
                "wins":      s["wins"],
                "win_rate":  None,
                "kelly":     None,
                "vantajoso": None,
                "insuficiente": True,
            }
    return resultado
