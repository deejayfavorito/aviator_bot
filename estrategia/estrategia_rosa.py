# estrategia/estrategia_rosa.py
"""
ESTRATÉGIA ROSA — apostar apenas DEPOIS de um rosa (>=10x).

Baseada no padrão observado pelo utilizador:
  "Depois de um rosa, o próximo crash tende a ser >=2x (roxo)."

Cores (definição do utilizador):
  🔵 Azul: 1.00x a 1.99x   (< 2.0)
  🟣 Roxo: 2.00x a 9.99x   (>= 2.0 e < 10.0)
  🌹 Rosa: 10.00x a +inf   (>= 10.0)

Objectivo de cashout: 1.80x a 2.00x (configurável, default 1.90x).

═══════════════════════════════════════════════════════════════════════
MÁQUINA DE ESTADOS (fiel às 3 regras do utilizador):

  ESTADO: ESPERANDO_ROSA  (não aposta)
    - se o último crash é ROSA → vai para A_APOSTAR (aposta na próxima)
    - senão → continua à espera

  ESTADO: A_APOSTAR  (já apostou; avalia o crash resultante)
    - crash ROSA  → ganhou, CONTINUA a apostar (reset tentativas)
    - crash ROXO  → ganhou (cashout 1.8-2.0 atingido), PAUSA até outro rosa
    - crash AZUL  → falhou; tenta + 1 vez (máx 2 tentativas), depois pausa
═══════════════════════════════════════════════════════════════════════

IMPORTANTE — honestidade científica:
  Esta estratégia REGISTA cada decisão e resultado em data/estrategia_rosa.csv,
  para que se possa avaliar OBJECTIVAMENTE se o padrão se confirma ou não.
  A cor do crash determina a lógica de estado; o cashout REAL (1.90x) determina
  ganho/perda. São coisas separadas.
"""
import os
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Tuple, List

from utils.logs import log


# ─── Limiares de cor ─────────────────────────────────────────────────
LIMIAR_AZUL = 2.0    # crash < 2.0 = azul
LIMIAR_ROSA = 10.0   # crash >= 10.0 = rosa
# (roxo é o intervalo [2.0, 10.0))

CASHOUT_ROSA_DEFAULT = 1.90   # meio de 1.80-2.00
MAX_TENTATIVAS_AZUL = 2

CAMINHO_LOG_ROSA = Path("data/estrategia_rosa.csv")


class EstadoRosa(Enum):
    ESPERANDO_ROSA = "esperando_rosa"
    A_APOSTAR      = "a_apostar"


# ─── Estado global (persiste entre rounds da sessão) ─────────────────
_estado = EstadoRosa.ESPERANDO_ROSA
_tentativas_azul = 0
_rosa_gatilho = 0.0   # qual o rosa que despoletou a sequência actual


def resetar_estado_rosa() -> None:
    """Reset do estado (chamar no arranque de cada sessão)."""
    global _estado, _tentativas_azul, _rosa_gatilho
    _estado = EstadoRosa.ESPERANDO_ROSA
    _tentativas_azul = 0
    _rosa_gatilho = 0.0


def _cor(c: float) -> str:
    if c >= LIMIAR_ROSA:
        return "rosa"
    elif c >= LIMIAR_AZUL:
        return "roxo"
    else:
        return "azul"


def _emoji_cor(cor: str) -> str:
    return {"rosa": "🌹", "roxo": "🟣", "azul": "🔵"}.get(cor, "❓")


def decidir_aposta_rosa(crashes_recentes: List[float],
                          cashout_alvo: float = CASHOUT_ROSA_DEFAULT
                          ) -> Tuple[bool, float, str]:
    """
    Decide se deve apostar na PRÓXIMA rodada, segundo a Estratégia Rosa.

    Args:
        crashes_recentes: lista de crashes, MAIS RECENTE PRIMEIRO
        cashout_alvo: alvo de cashout (default 1.90x)

    Returns:
        (deve_apostar, cashout_alvo, motivo)
    """
    global _estado, _tentativas_azul, _rosa_gatilho

    if not crashes_recentes:
        return False, cashout_alvo, "⏳ Estratégia Rosa: sem dados"

    ultimo = crashes_recentes[0]
    cor = _cor(ultimo)
    emoji = _emoji_cor(cor)

    # ─── ESTADO: À ESPERA DE ROSA ────────────────────────────────────
    if _estado == EstadoRosa.ESPERANDO_ROSA:
        if cor == "rosa":
            _estado = EstadoRosa.A_APOSTAR
            _tentativas_azul = 0
            _rosa_gatilho = ultimo
            return (True, cashout_alvo,
                    f"🌹 ROSA ({ultimo:.1f}x)! → APOSTAR JÁ na rodada seguinte "
                    f"(alvo {cashout_alvo:.2f}x)")
        else:
            return (False, cashout_alvo,
                    f"⏳ Estratégia Rosa: à espera de rosa "
                    f"(último {ultimo:.2f}x {emoji})")

    # ─── ESTADO: A APOSTAR (avalia o crash resultante) ───────────────
    else:  # A_APOSTAR
        if cor == "rosa":
            # Rosa de novo → ganhou e continua
            _tentativas_azul = 0
            _rosa_gatilho = ultimo
            return (True, cashout_alvo,
                    f"🌹 ROSA de novo ({ultimo:.1f}x) → CONTINUA a apostar")

        elif cor == "roxo":
            # Roxo → cashout 1.8-2.0 atingido (ganhou), pausa
            _estado = EstadoRosa.ESPERANDO_ROSA
            _tentativas_azul = 0
            return (False, cashout_alvo,
                    f"🟣 ROXO ({ultimo:.2f}x) → alvo atingido, PAUSA até próximo rosa")

        else:  # azul
            _tentativas_azul += 1
            if _tentativas_azul < MAX_TENTATIVAS_AZUL:
                return (True, cashout_alvo,
                        f"🔵 AZUL ({ultimo:.2f}x) → 2ª tentativa "
                        f"({_tentativas_azul}/{MAX_TENTATIVAS_AZUL})")
            else:
                _estado = EstadoRosa.ESPERANDO_ROSA
                tent = _tentativas_azul
                _tentativas_azul = 0
                return (False, cashout_alvo,
                        f"🔵 AZUL de novo ({ultimo:.2f}x) → {tent} tentativas falhadas, "
                        f"PAUSA até próximo rosa")


def registar_resultado_rosa(crash_apostado: float,
                              cashout_alvo: float,
                              ganhou: bool,
                              cashout_obtido: float) -> None:
    """
    Regista o resultado de uma aposta da Estratégia Rosa no CSV,
    para análise posterior do desempenho do padrão.
    """
    try:
        os.makedirs("data", exist_ok=True)
        existe = CAMINHO_LOG_ROSA.exists()
        with open(CAMINHO_LOG_ROSA, "a", newline="", encoding="utf-8") as f:
            if not existe:
                f.write("timestamp,rosa_gatilho,crash_resultante,cor_resultante,"
                        "cashout_alvo,ganhou,cashout_obtido\n")
            ts = datetime.now().isoformat(timespec="seconds")
            cor = _cor(crash_apostado)
            f.write(f"{ts},{_rosa_gatilho:.2f},{crash_apostado:.2f},{cor},"
                    f"{cashout_alvo:.2f},{int(ganhou)},{cashout_obtido:.2f}\n")
    except Exception:
        pass


def esta_activa(config: dict) -> bool:
    """Retorna True se a Estratégia Rosa está activa no config."""
    return config.get("usar_estrategia_rosa", False)


def relatorio_rosa() -> str:
    """Gera relatório do desempenho da Estratégia Rosa a partir do CSV."""
    if not CAMINHO_LOG_ROSA.exists():
        return ("📊 Estratégia Rosa: ainda sem dados.\n"
                "   Corre o bot com a Estratégia Rosa activa primeiro.")

    import csv
    total = wins = 0
    lucro_unidades = 0.0   # em múltiplos da aposta
    por_cor_resultante = {"rosa": [0, 0], "roxo": [0, 0], "azul": [0, 0]}  # [wins, total]

    try:
        with open(CAMINHO_LOG_ROSA, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                total += 1
                ganhou = row["ganhou"] == "1"
                alvo = float(row["cashout_alvo"])
                cor = row["cor_resultante"]
                if ganhou:
                    wins += 1
                    lucro_unidades += (alvo - 1)
                    if cor in por_cor_resultante:
                        por_cor_resultante[cor][0] += 1
                else:
                    lucro_unidades -= 1
                if cor in por_cor_resultante:
                    por_cor_resultante[cor][1] += 1
    except Exception as e:
        return f"⚠️ Erro a ler {CAMINHO_LOG_ROSA}: {e}"

    if total == 0:
        return "📊 Estratégia Rosa: CSV vazio."

    wr = wins / total * 100
    linhas = []
    linhas.append("📊 ═══ RELATÓRIO DA ESTRATÉGIA ROSA ═══")
    linhas.append(f"  Total de apostas (pós-rosa): {total}")
    linhas.append(f"  Vitórias: {wins} ({wr:.1f}%)")
    linhas.append(f"  Lucro acumulado: {lucro_unidades:+.2f}× a aposta")
    linhas.append(f"    (ex: aposta 100 → {lucro_unidades*100:+.0f} AOA)")
    linhas.append("")
    linhas.append("  Distribuição do crash logo a seguir ao rosa:")
    for cor in ("rosa", "roxo", "azul"):
        w, t = por_cor_resultante[cor]
        emoji = _emoji_cor(cor)
        pct = (t / total * 100) if total else 0
        linhas.append(f"    {emoji} {cor:5s}: {t:3d} ({pct:4.1f}%)")
    linhas.append("")
    # Conclusão sobre o padrão
    azuis = por_cor_resultante["azul"][1]
    nao_azuis = total - azuis
    pct_nao_azul = nao_azuis / total * 100 if total else 0
    linhas.append(f"  🎯 'Depois de rosa vem >=2x': {pct_nao_azul:.1f}% das vezes")
    linhas.append(f"     (base rate típica do jogo ≈ 62%)")
    if pct_nao_azul > 67:
        linhas.append("     ⁉️ ACIMA da base — pode haver sinal, recolhe mais dados")
    elif pct_nao_azul < 58:
        linhas.append("     ⬇️ ABAIXO da base — padrão não se confirma")
    else:
        linhas.append("     ≈ Dentro do esperado por acaso — sem sinal claro")
    return "\n".join(linhas)
