# estrategia/estrategia_dados.py
"""
Estratégia baseada em DADOS REAIS recolhidos pelo bot.

Esta estratégia complementa a `estrategia.py` (PDF-based) e activa-se quando
a flag `usar_estrategia_dados` está activa no config.

LÓGICA:
  - Default: 1.20x com aposta base (a "máquina de ganhar" — 92% WR no backtest)
  - Minutos QUENTES (rosa% >= LIMIAR_ROSA): aposta PEQUENA com cashout alto
  - Estatísticas guardadas em data/estado_estrategia_dados.json para evolução

DADOS BASE (extraídos do teu histórico real, 33 sessões):
  Min 02 → 55.6% rosa, max 71x
  Min 31 → 45.8%, max 71x
  Min 45 → 44.4%, max 291x
  Min 49 → 40.0%, max 1315x  ⚡ JACKPOT POTENCIAL
  Min 26 → 35.3%, max 573x
  Min 54 → 33.3%
  Min 17 → 30.0%, max 225x

Estes valores estão guardados nas constantes mas podem ser actualizados
correndo `recalibrar_minutos_quentes()` (TODO: futuro).
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass

from utils.logs import log


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA ESTRATÉGIA (baseado nos dados reais do utilizador)
# ═══════════════════════════════════════════════════════════════════════════

# Mapa: minuto → (% rosa esperado, cashout alvo recomendado, max visto)
MINUTOS_QUENTES = {
    # Minuto: (rosa_pct, cashout_target, max_observado)
    2:  (55.6, 3.0,  71.26),     # Top tier
    31: (45.8, 3.0,  71.31),
    45: (44.4, 3.0,  291.67),
    49: (40.0, 5.0,  1315.87),   # ⚡ Jackpot potencial — mais agressivo
    26: (35.3, 3.0,  573.21),
    54: (33.3, 2.5,  51.15),     # Max baixo, alvo conservador
    17: (30.0, 2.5,  225.79),
    36: (28.6, 2.5,  710.40),
    12: (28.6, 2.5,  571.67),
    52: (27.8, 2.5,  274.51),
    23: (27.8, 2.5,  773.72),
    58: (27.3, 2.5,  33.07),
}

# Limiar para considerar um minuto "quente" (acima deste %)
LIMIAR_ROSA_PCT = 25.0

# Cashout default (a "máquina de ganhar")
CASHOUT_DEFAULT = 1.20

# Aposta para minutos quentes: fracção da aposta base
# Ideia: aposta PEQUENA para limitar risco em apostas de alto cashout
FRACCAO_APOSTA_MIN_QUENTE = 0.5  # 50% da aposta base

# Mínimo absoluto (jogo exige 65 AOA mín)
APOSTA_MIN_JOGO = 65


# ═══════════════════════════════════════════════════════════════════════════
# ESTADO PERSISTENTE
# ═══════════════════════════════════════════════════════════════════════════

CAMINHO_ESTADO = Path("data/estado_estrategia_dados.json")


def _carregar_estado() -> dict:
    """Carrega estatísticas acumuladas da estratégia."""
    if not CAMINHO_ESTADO.exists():
        return {
            "minutos_quentes_apostas": {},   # minuto → {wins, losses, lucro}
            "default_apostas":         {"wins": 0, "losses": 0, "lucro": 0.0},
            "total_apostas":           0,
            "criado_em":               datetime.now().isoformat(),
        }
    try:
        with open(CAMINHO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "minutos_quentes_apostas": {},
            "default_apostas":         {"wins": 0, "losses": 0, "lucro": 0.0},
            "total_apostas":           0,
            "criado_em":               datetime.now().isoformat(),
        }


def _gravar_estado(estado: dict) -> None:
    """Grava estatísticas acumuladas."""
    try:
        CAMINHO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
        with open(CAMINHO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"⚠️ Erro a gravar estado da estratégia dados: {e}", "warning")


# ═══════════════════════════════════════════════════════════════════════════
# LÓGICA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DecisaoEstrategia:
    """Resultado da decisão da estratégia."""
    deve_apostar:    bool
    cashout_alvo:    float
    motivo:          str
    is_minuto_quente: bool = False
    minuto_actual:   int = -1


def aplicar_estrategia_dados(historico_mults: list, config: dict) -> Tuple[bool, float]:
    """
    Aplica a estratégia baseada em dados reais.

    Retorna (deve_apostar, cashout_alvo) — compatível com `estrategia.py`.

    Args:
        historico_mults: lista dos últimos multiplicadores (mais recente primeiro)
        config: dicionário do config.json

    Returns:
        (True, 1.20) ou (True, 3.00) ou (False, 0.0)
    """
    decisao = _decidir(historico_mults, config)
    if decisao.motivo:
        log(decisao.motivo)
    return decisao.deve_apostar, decisao.cashout_alvo


def _decidir(historico_mults: list, config: dict) -> DecisaoEstrategia:
    """Lógica interna de decisão."""
    agora = datetime.now()
    minuto = agora.minute

    # 1. Verifica se o minuto actual é "quente"
    if minuto in MINUTOS_QUENTES:
        rosa_pct, cashout_recomendado, max_visto = MINUTOS_QUENTES[minuto]

        if rosa_pct >= LIMIAR_ROSA_PCT:
            return DecisaoEstrategia(
                deve_apostar=True,
                cashout_alvo=cashout_recomendado,
                motivo=(
                    f"🔥 MIN QUENTE {minuto:02d}: rosa={rosa_pct:.0f}% "
                    f"max histórico {max_visto:.0f}x → alvo {cashout_recomendado:.1f}x"
                ),
                is_minuto_quente=True,
                minuto_actual=minuto,
            )

    # 2. Default: a máquina de ganhar
    return DecisaoEstrategia(
        deve_apostar=True,
        cashout_alvo=CASHOUT_DEFAULT,
        motivo=f"✅ Default {CASHOUT_DEFAULT:.2f}x (min {minuto:02d})",
        is_minuto_quente=False,
        minuto_actual=minuto,
    )


def calcular_valor_aposta_dados(
    cashout_alvo: float,
    aposta_base: float,
    aposta_atual_cadeia: float,
) -> Tuple[float, str]:
    """
    Calcula valor da aposta segundo a estratégia de dados.

    Lógica:
      - Cashout 1.20x (default): usa valor da cadeia composta normal
      - Cashout >= 2.0x (min quente): aposta PEQUENA (50% base, mín 65 AOA)

    Args:
        cashout_alvo: alvo da aposta
        aposta_base: aposta base do config
        aposta_atual_cadeia: valor que a cadeia composta calculou

    Returns:
        (valor_final, motivo)
    """
    if cashout_alvo == CASHOUT_DEFAULT:
        # Modo normal — usa o que a cadeia composta diz
        return aposta_atual_cadeia, ""

    # Minuto quente — aposta pequena
    valor_quente = max(APOSTA_MIN_JOGO, aposta_base * FRACCAO_APOSTA_MIN_QUENTE)
    return valor_quente, (
        f"💎 Aposta pequena para min quente: "
        f"{aposta_atual_cadeia:.0f}→{valor_quente:.0f} AOA "
        f"(alvo {cashout_alvo:.1f}x)"
    )


# ═══════════════════════════════════════════════════════════════════════════
# REGISTO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════

def registar_resultado_dados(
    minuto_da_aposta: int,
    cashout_alvo: float,
    ganhou: bool,
    lucro_aposta: float,
) -> None:
    """
    Regista o resultado de uma aposta nesta estratégia.

    Args:
        minuto_da_aposta: minuto da hora em que a aposta foi feita
        cashout_alvo: alvo que estava activo
        ganhou: True se ganhou, False se perdeu
        lucro_aposta: lucro/prejuízo (positivo ou negativo)
    """
    estado = _carregar_estado()
    estado["total_apostas"] += 1

    is_minuto_quente = (
        minuto_da_aposta in MINUTOS_QUENTES
        and MINUTOS_QUENTES[minuto_da_aposta][0] >= LIMIAR_ROSA_PCT
    )

    if is_minuto_quente:
        chave = str(minuto_da_aposta)  # JSON quer strings
        if chave not in estado["minutos_quentes_apostas"]:
            estado["minutos_quentes_apostas"][chave] = {
                "wins": 0, "losses": 0, "lucro": 0.0
            }
        if ganhou:
            estado["minutos_quentes_apostas"][chave]["wins"] += 1
        else:
            estado["minutos_quentes_apostas"][chave]["losses"] += 1
        estado["minutos_quentes_apostas"][chave]["lucro"] += lucro_aposta
    else:
        if ganhou:
            estado["default_apostas"]["wins"] += 1
        else:
            estado["default_apostas"]["losses"] += 1
        estado["default_apostas"]["lucro"] += lucro_aposta

    _gravar_estado(estado)


# ═══════════════════════════════════════════════════════════════════════════
# RELATÓRIO
# ═══════════════════════════════════════════════════════════════════════════

def relatorio_estrategia_dados() -> str:
    """Gera relatório legível do desempenho desta estratégia."""
    estado = _carregar_estado()
    linhas = []
    linhas.append("📊 RELATÓRIO — Estratégia de Dados")
    linhas.append("═" * 70)
    linhas.append(f"  Total de apostas: {estado.get('total_apostas', 0)}")
    linhas.append("")

    default = estado.get("default_apostas", {})
    w = default.get("wins", 0)
    l = default.get("losses", 0)
    lucro = default.get("lucro", 0.0)
    total = w + l
    wr = (w / total * 100) if total else 0
    linhas.append(f"  💼 DEFAULT (1.20x): {w}W / {l}L ({wr:.0f}%) | Lucro: {lucro:+.0f} AOA")
    linhas.append("")

    linhas.append("  🔥 MINUTOS QUENTES:")
    linhas.append("  ─" * 35)
    min_quentes = estado.get("minutos_quentes_apostas", {})
    if not min_quentes:
        linhas.append("    (nenhum minuto quente apostado ainda)")
    else:
        for minuto_str in sorted(min_quentes.keys(), key=int):
            m = int(minuto_str)
            dados = min_quentes[minuto_str]
            w = dados["wins"]; l = dados["losses"]; lc = dados["lucro"]
            total = w + l
            wr = (w / total * 100) if total else 0
            esperado_pct, alvo, _ = MINUTOS_QUENTES.get(m, (0, 0, 0))
            linhas.append(
                f"    min {m:02d} (rosa%={esperado_pct:.0f}, alvo={alvo:.1f}x): "
                f"{w}W/{l}L ({wr:.0f}%) | {lc:+.0f} AOA"
            )

    linhas.append("═" * 70)
    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════════════════
# INFO PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════

def esta_activa(config: dict) -> bool:
    """Retorna True se esta estratégia está activa no config."""
    return config.get("usar_estrategia_dados", False)


def info_minutos_quentes() -> list:
    """Retorna lista ordenada de minutos quentes (para exibição)."""
    return sorted(
        [(m, p, c) for m, (p, c, _) in MINUTOS_QUENTES.items() if p >= LIMIAR_ROSA_PCT],
        key=lambda x: -x[1]
    )
