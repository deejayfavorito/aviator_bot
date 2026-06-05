"""
Aplica retroactivamente a estratégia 'Follow Patterns' às sessões
ANTIGAS para descobrir quais padrões teriam disparado e o desempenho
hipotético de cada um.

Como funciona:
  1. Lê todas as sessões em data/sessao_*.csv
  2. Para cada aposta REAL nessas sessões, reconstrói o contexto:
     - Quais foram os últimos N crashes antes daquela aposta
  3. Aplica a lógica de decidir_padrao() para identificar qual padrão
     teria disparado
  4. Cruza com o resultado REAL (ganhou/perdeu, cashout obtido)
  5. Calcula estatísticas hipotéticas por padrão

Esta análise NÃO altera nenhum ficheiro — só lê.

Uso:
    python aplicar_padroes_retroactivo.py
"""
import csv
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA SIMULAÇÃO (espelho de estrategia_padroes.py)
# ═══════════════════════════════════════════════════════════════════════

MINUTOS_QUENTES = {
    2: 55.6, 31: 45.8, 45: 44.4, 49: 40.0, 26: 35.3,
    54: 33.3, 17: 30.0, 36: 28.6, 12: 28.6, 52: 27.8,
    23: 27.8, 58: 27.3,
}

LIMIAR_AZUL = 2.0
LIMIAR_ROSA = 10.0
LIMIAR_MEGA = 100.0
LIMIAR_ROSA_QUEIMADA = 5.0

MIN_AZUIS_REGRESSAO = 6
MIN_AZUIS_COMBO     = 5
MIN_ROSAS_HOT       = 2
WINDOW_ANALISE      = 10
WINDOW_POS_MEGA     = 3


# ═══════════════════════════════════════════════════════════════════════
# DETECTOR DE PADRÃO (versão pura — sem dependências do bot)
# ═══════════════════════════════════════════════════════════════════════

def _contar_azuis_seguidos(crashes: List[float]) -> int:
    contagem = 0
    for c in crashes:
        if c < LIMIAR_AZUL:
            contagem += 1
        else:
            break
    return contagem


def _contar_rosas(crashes: List[float], janela: int = WINDOW_ANALISE) -> int:
    return sum(1 for c in crashes[:janela] if c >= LIMIAR_ROSA)


def _houve_mega_recente(crashes: List[float], janela: int = WINDOW_POS_MEGA) -> bool:
    return any(c >= LIMIAR_MEGA for c in crashes[:janela])


def detectar_padrao(crashes_recentes: List[float], minuto: int) -> dict:
    """Replica a lógica de decidir_padrao(). Retorna dict com info."""
    if not crashes_recentes or len(crashes_recentes) < 3:
        return {"padrao": "P6_default", "cashout": 1.20, "deve_apostar": True}

    ultimo = crashes_recentes[0]
    azuis = _contar_azuis_seguidos(crashes_recentes)
    rosas = _contar_rosas(crashes_recentes)
    pct_quente = MINUTOS_QUENTES.get(minuto)

    # P1
    if _houve_mega_recente(crashes_recentes):
        return {"padrao": "P1_pos_mega", "cashout": 0.0, "deve_apostar": False}

    # P3 COMBO
    if pct_quente is not None and azuis >= MIN_AZUIS_COMBO:
        if minuto == 49:
            return {"padrao": "P3_combo_jackpot", "cashout": 5.0, "deve_apostar": True}
        return {"padrao": "P3_combo", "cashout": 3.0, "deve_apostar": True}

    # P2
    if azuis >= MIN_AZUIS_REGRESSAO:
        return {"padrao": "P2_regressao", "cashout": 2.0, "deve_apostar": True}

    # P4
    if rosas >= MIN_ROSAS_HOT:
        return {"padrao": "P4_hot_streak", "cashout": 1.30, "deve_apostar": True}

    # P5
    if ultimo >= LIMIAR_ROSA_QUEIMADA:
        return {"padrao": "P5_rosa_queimada", "cashout": 1.20, "deve_apostar": True}

    # P6
    return {"padrao": "P6_default", "cashout": 1.20, "deve_apostar": True}


# ═══════════════════════════════════════════════════════════════════════
# CARREGAR HISTÓRICO
# ═══════════════════════════════════════════════════════════════════════

def carregar_historico_crashes() -> List[tuple]:
    """
    Carrega data/historico.csv e retorna lista de (timestamp, multiplicador)
    ordenada por timestamp ascendente.
    """
    caminho = Path("data/historico.csv")
    if not caminho.exists():
        print(f"⚠ Histórico não encontrado: {caminho}")
        return []

    eventos = []
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            partes = linha.strip().split(",")
            if len(partes) >= 3 and partes[1] == "crash_registado":
                try:
                    ts = datetime.fromisoformat(partes[0])
                    mult = float(partes[2].replace("x", "").strip())
                    eventos.append((ts, mult))
                except (ValueError, IndexError):
                    continue
    return sorted(eventos, key=lambda x: x[0])


def carregar_sessoes() -> List[dict]:
    """
    Lê TODAS as apostas de TODAS as sessões.
    Inclui timestamp para podermos cruzar com o histórico.
    """
    pasta = Path("data")
    if not pasta.exists():
        return []

    apostas = []
    for ficheiro in sorted(pasta.glob("sessao_*.csv")):
        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    resultado = linha.get("resultado", "")
                    # Só apostas reais
                    if resultado not in ("ganhou", "perdeu"):
                        continue
                    try:
                        ts_str = linha.get("timestamp", "")
                        # Vários formatos possíveis — tentar parsear
                        ts = None
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                                    "%Y-%m-%d %H:%M:%S.%f"):
                            try:
                                ts = datetime.strptime(ts_str, fmt)
                                break
                            except ValueError:
                                continue
                        if ts is None:
                            try:
                                ts = datetime.fromisoformat(ts_str)
                            except Exception:
                                continue

                        apostas.append({
                            "timestamp":      ts,
                            "round_mult":     float(linha.get("multiplicador_round", "0") or 0),
                            "cashout_alvo":   float(linha.get("cashout_alvo", "0") or 0),
                            "valor_apostado": float(linha.get("valor_apostado", "0") or 0),
                            "resultado":      resultado,
                            "cashout_obtido": float(linha.get("cashout_obtido", "0") or 0),
                            "lucro_aposta":   float(linha.get("lucro_aposta", "0") or 0),
                            "estrategia_real": linha.get("estrategia", "?"),
                            "ficheiro":       ficheiro.name,
                        })
                    except (ValueError, KeyError):
                        continue
        except Exception:
            continue
    return apostas


# ═══════════════════════════════════════════════════════════════════════
# RECONSTRUIR CONTEXTO E SIMULAR
# ═══════════════════════════════════════════════════════════════════════

def obter_crashes_anteriores(timestamp_aposta: datetime,
                              historico: List[tuple],
                              n: int = 20) -> List[float]:
    """
    Retorna os N crashes que aconteceram ANTES do timestamp da aposta.
    Lista por ordem cronológica reversa (mais recente primeiro).
    """
    crashes_antes = [m for (ts, m) in historico if ts < timestamp_aposta]
    crashes_antes.reverse()  # mais recente primeiro
    return crashes_antes[:n]


def simular_padroes_retroactivos(apostas: List[dict],
                                  historico: List[tuple]) -> List[dict]:
    """
    Para cada aposta, aplica o detector de padrões usando o contexto
    histórico que existia naquele momento.
    """
    resultados = []
    for ap in apostas:
        crashes_antes = obter_crashes_anteriores(ap["timestamp"], historico, n=20)
        if not crashes_antes:
            continue

        minuto = ap["timestamp"].minute
        deteccao = detectar_padrao(crashes_antes, minuto)

        # Calcula lucro HIPOTÉTICO usando a estratégia padrões
        ganhou_real = ap["resultado"] == "ganhou"
        cashout_obtido_real = ap["cashout_obtido"]
        cashout_alvo_hipotetico = deteccao["cashout"]

        # Se padrão diz "não apostar" → poupou perda OU perdeu ganho
        if not deteccao["deve_apostar"]:
            # Cenário: o bot teria pulado esta aposta
            lucro_hipotetico = 0.0
            ganhou_hipotetico = None  # nem ganho nem perda
        else:
            # Cenário: o bot teria apostado COM ESTE CASHOUT
            # Ganha se o crash real (cashout_obtido_real, que é o máximo
            # que vimos antes do crash) for >= cashout_alvo_hipotetico
            if ganhou_real:
                # No real, vimos cashout_obtido (alguma vez ultrapassou alvo real)
                # Como cashout_obtido_real >= cashout_alvo_real,
                # se cashout_alvo_hipotetico <= cashout_obtido_real → ganha
                if cashout_alvo_hipotetico <= cashout_obtido_real:
                    ganhou_hipotetico = True
                    lucro_hipotetico = ap["valor_apostado"] * (cashout_alvo_hipotetico - 1)
                else:
                    # O alvo hipotético é > do que o real conseguiu — perdeu
                    ganhou_hipotetico = False
                    lucro_hipotetico = -ap["valor_apostado"]
            else:
                # No real perdeu → o crash foi antes do alvo real
                # Para sabermos se ganhamos com alvo hipotético mais baixo,
                # comparamos com o cashout_obtido (max visto)
                if cashout_alvo_hipotetico <= cashout_obtido_real:
                    ganhou_hipotetico = True
                    lucro_hipotetico = ap["valor_apostado"] * (cashout_alvo_hipotetico - 1)
                else:
                    ganhou_hipotetico = False
                    lucro_hipotetico = -ap["valor_apostado"]

        resultados.append({
            **ap,
            "padrao_detectado":          deteccao["padrao"],
            "cashout_hipotetico":        cashout_alvo_hipotetico,
            "deve_apostar_hipotetico":   deteccao["deve_apostar"],
            "ganhou_hipotetico":         ganhou_hipotetico,
            "lucro_hipotetico":          lucro_hipotetico,
            "ganhou_real":               ganhou_real,
            "n_crashes_contexto":        len(crashes_antes),
            "azuis_seguidos":            _contar_azuis_seguidos(crashes_antes),
            "rosas_em_10":               _contar_rosas(crashes_antes),
        })

    return resultados


# ═══════════════════════════════════════════════════════════════════════
# AGREGAR E APRESENTAR
# ═══════════════════════════════════════════════════════════════════════

def agregar_por_padrao(resultados: List[dict]) -> dict:
    """Agrupa resultados por padrão e calcula estatísticas hipotéticas."""
    grupos = defaultdict(list)
    for r in resultados:
        grupos[r["padrao_detectado"]].append(r)

    stats = {}
    for padrao, lista in grupos.items():
        n = len(lista)

        # Se padrão P1 (não apostar) → contabilizar perdas evitadas
        if padrao == "P1_pos_mega":
            perdas_evitadas = sum(1 for r in lista if not r["ganhou_real"])
            ganhos_perdidos = sum(1 for r in lista if r["ganhou_real"])
            lucro_real_perdido = sum(r["lucro_aposta"] for r in lista)
            stats[padrao] = {
                "total":              n,
                "tipo":               "pular",
                "perdas_evitadas":    perdas_evitadas,
                "ganhos_perdidos":    ganhos_perdidos,
                "lucro_real_perdido": lucro_real_perdido,
            }
            continue

        # Padrões normais
        wins = sum(1 for r in lista if r["ganhou_hipotetico"])
        losses = sum(1 for r in lista if r["ganhou_hipotetico"] is False)
        total = wins + losses
        lucro = sum(r["lucro_hipotetico"] for r in lista)
        investido = sum(r["valor_apostado"] for r in lista if r["ganhou_hipotetico"] is not None)

        stats[padrao] = {
            "total":     n,
            "tipo":      "apostar",
            "wins":      wins,
            "losses":    losses,
            "win_rate":  (wins / total * 100) if total else 0,
            "lucro":     lucro,
            "investido": investido,
            "roi":       (lucro / investido * 100) if investido else 0,
        }

    return stats


def imprimir_relatorio(resultados: List[dict], stats: dict):
    print()
    print("═" * 78)
    print("  🔬 ANÁLISE RETROACTIVA — 'Follow Patterns' aplicado às sessões ANTIGAS")
    print("═" * 78)
    print()

    n_total = len(resultados)
    if n_total == 0:
        print("  ⚠ Sem apostas para analisar.")
        print("     Verifica se data/historico.csv e data/sessao_*.csv existem.")
        return

    print(f"  📂 Apostas reais analisadas:  {n_total}")

    # Comparação geral
    lucro_real = sum(r["lucro_aposta"] for r in resultados)
    lucro_hip = sum(r["lucro_hipotetico"] for r in resultados
                    if r["ganhou_hipotetico"] is not None)

    diff = lucro_hip - lucro_real
    print(f"  💵 Lucro REAL (estratégia antiga):     {lucro_real:+10.0f} AOA")
    print(f"  💰 Lucro HIPOTÉTICO (Follow Patterns): {lucro_hip:+10.0f} AOA")
    print(f"  📊 Diferença:                          {diff:+10.0f} AOA "
          f"({'MELHOR ✅' if diff > 0 else 'PIOR ❌' if diff < 0 else 'IGUAL'})")
    print()

    # Detalhe por padrão
    print("─" * 78)
    print("  📋 SE TIVÉSSEMOS USADO FOLLOW PATTERNS NAS SESSÕES ANTIGAS:")
    print("─" * 78)

    # Separar P1 dos outros
    if "P1_pos_mega" in stats:
        s = stats["P1_pos_mega"]
        print(f"\n  🚫 P1_pos_mega (apostas evitadas):")
        print(f"     Total de skips:      {s['total']}")
        print(f"     Perdas evitadas:     {s['perdas_evitadas']}  ✅")
        print(f"     Ganhos perdidos:     {s['ganhos_perdidos']}  ❌")
        print(f"     Lucro real perdido:  {s['lucro_real_perdido']:+.0f} AOA "
              f"(positivo = perdemos oportunidade; negativo = salvámos)")

    # Padrões de aposta
    print(f"\n  {'Padrão':25s} {'Apostas':>8s} {'W':>4s} {'L':>4s} "
          f"{'WR':>7s} {'ROI':>8s}  {'Lucro AOA':>10s}")
    print("  " + "─" * 76)

    padroes_aposta = {k: v for k, v in stats.items() if v.get("tipo") == "apostar"}
    for padrao in sorted(padroes_aposta.keys(), key=lambda p: -padroes_aposta[p]["lucro"]):
        s = padroes_aposta[padrao]
        emoji = "🟢" if s["roi"] > 10 else ("🟡" if s["roi"] > 0 else "🔴")
        print(f"  {emoji} {padrao:23s} {s['total']:>6d}  {s['wins']:>4d} {s['losses']:>4d} "
              f"{s['win_rate']:>6.1f}% {s['roi']:>+7.1f}% {s['lucro']:>+10.0f}")

    print()
    print("─" * 78)
    print("  💡 RECOMENDAÇÕES")
    print("─" * 78)

    # P1
    if "P1_pos_mega" in stats:
        s = stats["P1_pos_mega"]
        if s["lucro_real_perdido"] > 0:
            print(f"  🟡 P1: As apostas pós-mega no histórico RENDERAM "
                  f"{s['lucro_real_perdido']:+.0f} AOA — talvez P1 seja demasiado conservador.")
        elif s["lucro_real_perdido"] < 0:
            print(f"  🟢 P1: As apostas pós-mega no histórico PERDERAM "
                  f"{s['lucro_real_perdido']:+.0f} AOA — P1 SALVA dinheiro!")
        else:
            print(f"  ⚪ P1: Sem amostras significativas pós-mega.")

    # Outros
    for padrao, s in padroes_aposta.items():
        if s["total"] < 5:
            continue
        if s["win_rate"] < 40:
            print(f"  🔴 {padrao}: WR baixo ({s['win_rate']:.0f}%) — não usar.")
        elif s["win_rate"] >= 80 and s["roi"] > 10:
            print(f"  🟢 {padrao}: EXCELENTE — WR {s['win_rate']:.0f}%, "
                  f"ROI {s['roi']:+.1f}%.")
        elif s["win_rate"] >= 60:
            print(f"  🟡 {padrao}: aceitável — WR {s['win_rate']:.0f}%, "
                  f"ROI {s['roi']:+.1f}%.")

    print()
    print("═" * 78)
    print(f"\n  📌 Resumo: se Follow Patterns estivesse activo nas {n_total} "
          f"apostas, terias ganhado {diff:+.0f} AOA a mais (ou menos).")
    print("═" * 78)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("🔍 Análise retroactiva 'Follow Patterns'")
    print()

    print("1️⃣  A carregar histórico de crashes...")
    historico = carregar_historico_crashes()
    print(f"    {len(historico)} crashes carregados")

    if not historico:
        print("\n⚠ Sem histórico de crashes. Abortar.")
        return

    print()
    print("2️⃣  A carregar apostas de todas as sessões...")
    apostas = carregar_sessoes()
    print(f"    {len(apostas)} apostas reais carregadas")

    if not apostas:
        print("\n⚠ Sem apostas em sessões. Abortar.")
        return

    print()
    print("3️⃣  A simular padrões retroactivamente...")
    resultados = simular_padroes_retroactivos(apostas, historico)
    print(f"    {len(resultados)} apostas analisadas com contexto")

    if not resultados:
        print("\n⚠ Sem resultados (timestamps podem não cruzar com o histórico).")
        return

    print()
    print("4️⃣  A agregar por padrão...")
    stats = agregar_por_padrao(resultados)

    imprimir_relatorio(resultados, stats)


if __name__ == "__main__":
    main()
