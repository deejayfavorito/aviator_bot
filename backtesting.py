"""
Backtesting — simula a estratégia usando o histórico real de multiplicadores.

Uso:
    python backtesting.py

NÃO interfere com o bot. Apenas lê `data/historico.csv` e simula o que
teria acontecido se o bot tivesse jogado com a estratégia actual.

Mostra:
  - Win rate
  - ROI
  - Drawdown máximo (maior perda acumulada)
  - Sequência mais longa de vitórias
  - Sequência mais longa de derrotas
  - Lucro/perda total
  - Análise por estratégia
"""
import csv
import datetime
from pathlib import Path
from typing import List, Tuple


# ─── Configuração da simulação ────────────────────────────────────────────
APOSTA_BASE       = 100.0
APOSTA_LIMITE_MAX = 400.0
RESET_APOS_VITORIAS = 3
MAX_PERDAS_SEGUIDAS = 4
DURACAO_PAUSA_ROUNDS = 3


def cor(v: float) -> str:
    if v < 2.0:   return "azul"
    if v <= 10.0: return "roxo"
    return "rosa"


def _consecutivos(cores: List[str], alvo: str) -> int:
    n = 0
    for c in cores:
        if c == alvo: n += 1
        else: break
    return n


def _janela_rosa(minuto: int) -> bool:
    """Determina se o minuto cai numa janela de rosa."""
    for ini, fim in [(2,3),(8,9),(20,22),(28,30),(38,39),(41,41),(55,57)]:
        if ini <= minuto <= fim:
            return True
    return False


def aplicar_estrategia(historico: List[float], minuto_simulado: int) -> Tuple[bool, float, str]:
    """
    Replica a estratégia do bot. Retorna (deve_apostar, cashout_alvo, nome_estrat).
    """
    if len(historico) < 6:
        return True, 1.20, "default"

    # Pausa por rodada má (4+ baixos em 5)
    recentes_baixos = sum(1 for v in historico[:5] if v < 1.50)
    if recentes_baixos >= 4:
        return False, 0.0, "pausa_rodada_ma"

    cores_recentes = [cor(v) for v in historico]
    azuis_seg = _consecutivos(cores_recentes, "azul")
    roxos_seg = _consecutivos(cores_recentes, "roxo")

    # Padrões fortes
    if roxos_seg >= 5:
        return True, 20.0, "P2.3_roxos"

    if azuis_seg >= 6:
        return True, 10.0, "P2.2_azuis"

    # P2.1: alternância + 2 azuis
    if (len(cores_recentes) >= 4
            and cores_recentes[0] == "azul" and cores_recentes[1] == "azul"
            and cores_recentes[2] in ("azul","roxo")
            and cores_recentes[3] in ("azul","roxo")
            and cores_recentes[2] != cores_recentes[3]):
        return True, 2.0, "P2.1_alternancia"

    # Janela de rosa
    if _janela_rosa(minuto_simulado):
        if any(v > 10.0 for v in historico[:15]):
            return True, 1.20, "rosa_recente"
        return True, 2.00, "rosa_janela"

    return True, 1.20, "default_1.20x"


def calcular_proxima_aposta(valor_atual: float, cashout_alvo: float) -> float:
    """Replica gestor_aposta.py — cashout >2x usa base, caso contrário usa composta."""
    if cashout_alvo > 2.0:
        return APOSTA_BASE  # padrão agressivo usa base
    return min(valor_atual, APOSTA_LIMITE_MAX)


def carregar_historico() -> List[float]:
    """Lê data/historico.csv e retorna lista de multiplicadores (cronológica)."""
    path = Path("data/historico.csv")
    if not path.exists():
        print("❌ data/historico.csv não encontrado")
        return []

    mults = []
    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            partes = linha.strip().split(",")
            if len(partes) >= 3 and partes[1] == "crash_registado":
                try:
                    mults.append(float(partes[2].replace("x", "").strip()))
                except ValueError:
                    pass
    return mults


def simular(historico: List[float], verbose: bool = False) -> dict:
    """Simula a estratégia no histórico. Retorna estatísticas."""

    if len(historico) < 10:
        print("⚠️ Histórico muito curto (<10 rounds). Não dá para simular.")
        return {}

    # Estado da simulação
    valor_atual         = APOSTA_BASE
    vitorias_seguidas   = 0
    perdas_seguidas     = 0
    rounds_em_pausa     = 0
    lucro_cofre         = 0.0

    # Estatísticas
    total_apostas       = 0
    vitorias            = 0
    derrotas            = 0
    puladas             = 0
    investido_total     = 0.0
    ganho_total         = 0.0
    perda_total         = 0.0
    lucro_acumulado     = 0.0
    maior_drawdown      = 0.0
    pico_lucro          = 0.0
    maior_seq_vitorias  = 0
    maior_seq_derrotas  = 0
    seq_vitorias_atual  = 0
    seq_derrotas_atual  = 0

    # Estatísticas por estratégia
    stats_estrategia    = {}  # nome → {wins, losses, lucro}

    # Simula round a round (índice 0 = mais antigo)
    # Para cada round, "histórico visto" é tudo ANTES dele (reverso, mais recente em pos 0)
    for i, multiplicador_actual in enumerate(historico):
        if i < 6:
            continue  # precisa de pelo menos 6 rounds de histórico para decidir

        # Histórico visto até agora: do mais recente para o mais antigo
        historico_visto = list(reversed(historico[:i]))

        # Minuto simulado: distribui ao longo das horas (cíclico 0-59)
        minuto_simulado = i % 60

        # Verifica pausa
        if perdas_seguidas >= MAX_PERDAS_SEGUIDAS:
            rounds_em_pausa += 1
            if rounds_em_pausa >= DURACAO_PAUSA_ROUNDS:
                perdas_seguidas = 0
                rounds_em_pausa = 0
            else:
                puladas += 1
                continue

        # Decisão da estratégia
        deve_apostar, cashout_alvo, nome_estrat = aplicar_estrategia(historico_visto, minuto_simulado)

        if not deve_apostar:
            puladas += 1
            continue

        # Calcula valor da aposta
        valor_aposta = calcular_proxima_aposta(valor_atual, cashout_alvo)
        valor_aposta = max(valor_aposta, APOSTA_BASE)

        # Stats da estratégia
        if nome_estrat not in stats_estrategia:
            stats_estrategia[nome_estrat] = {"wins": 0, "losses": 0, "lucro": 0.0, "apostas": 0}
        stats_estrategia[nome_estrat]["apostas"] += 1

        # Resultado: ganhou se multiplicador_actual >= cashout_alvo
        ganhou = multiplicador_actual >= cashout_alvo

        total_apostas += 1
        investido_total += valor_aposta

        if ganhou:
            ganho_round = valor_aposta * cashout_alvo
            lucro_round = ganho_round - valor_aposta
            lucro_acumulado += lucro_round
            ganho_total += ganho_round
            vitorias += 1
            vitorias_seguidas += 1
            perdas_seguidas = 0
            seq_vitorias_atual += 1
            seq_derrotas_atual = 0
            maior_seq_vitorias = max(maior_seq_vitorias, seq_vitorias_atual)

            stats_estrategia[nome_estrat]["wins"] += 1
            stats_estrategia[nome_estrat]["lucro"] += lucro_round

            # Reset após N vitórias
            if vitorias_seguidas >= RESET_APOS_VITORIAS and cashout_alvo <= 2.0:
                lucro_cofre += lucro_round  # guarda lucro
                valor_atual = APOSTA_BASE
                vitorias_seguidas = 0
            else:
                valor_atual = min(ganho_round, APOSTA_LIMITE_MAX)
        else:
            lucro_round = -valor_aposta
            lucro_acumulado += lucro_round
            perda_total += valor_aposta
            derrotas += 1
            perdas_seguidas += 1
            vitorias_seguidas = 0
            seq_derrotas_atual += 1
            seq_vitorias_atual = 0
            maior_seq_derrotas = max(maior_seq_derrotas, seq_derrotas_atual)

            stats_estrategia[nome_estrat]["losses"] += 1
            stats_estrategia[nome_estrat]["lucro"] += lucro_round

            valor_atual = APOSTA_BASE

        # Drawdown
        if lucro_acumulado > pico_lucro:
            pico_lucro = lucro_acumulado
        drawdown_actual = pico_lucro - lucro_acumulado
        maior_drawdown = max(maior_drawdown, drawdown_actual)

    win_rate = (vitorias / total_apostas * 100) if total_apostas > 0 else 0
    roi      = (lucro_acumulado / investido_total * 100) if investido_total > 0 else 0

    return {
        "total_rounds":       len(historico),
        "total_apostas":      total_apostas,
        "vitorias":           vitorias,
        "derrotas":           derrotas,
        "puladas":            puladas,
        "win_rate":           win_rate,
        "investido_total":    investido_total,
        "ganho_total":        ganho_total,
        "perda_total":        perda_total,
        "lucro_acumulado":    lucro_acumulado,
        "lucro_cofre":        lucro_cofre,
        "lucro_efectivo":     lucro_acumulado,  # cofre já incluído no lucro_acumulado
        "roi":                roi,
        "maior_drawdown":     maior_drawdown,
        "maior_seq_vitorias": maior_seq_vitorias,
        "maior_seq_derrotas": maior_seq_derrotas,
        "stats_estrategia":   stats_estrategia,
    }


def imprimir_relatorio(stats: dict):
    """Imprime relatório formatado dos resultados."""

    print()
    print("═" * 72)
    print("  📊 RELATÓRIO DE BACKTESTING")
    print("═" * 72)
    print()
    print(f"  📂 Total de rounds no histórico:    {stats['total_rounds']}")
    print(f"  🎯 Total de apostas simuladas:      {stats['total_apostas']}")
    print(f"  ⏭️  Rounds pulados:                  {stats['puladas']}")
    print()
    print(f"  ✅ Vitórias:                        {stats['vitorias']}")
    print(f"  ❌ Derrotas:                        {stats['derrotas']}")
    print(f"  🏆 Win rate:                        {stats['win_rate']:.1f}%")
    print()
    print(f"  💰 Investido total:                 {stats['investido_total']:.2f} AOA")
    print(f"  💵 Ganhos totais:                   {stats['ganho_total']:.2f} AOA")
    print(f"  💸 Perdas totais:                   {stats['perda_total']:.2f} AOA")
    print()
    sinal = "+" if stats['lucro_acumulado'] >= 0 else ""
    print(f"  🎯 Lucro/Prejuízo:                  {sinal}{stats['lucro_acumulado']:.2f} AOA")
    print(f"  📊 ROI:                             {sinal}{stats['roi']:.2f}%")
    print()
    print(f"  📉 Maior drawdown:                  {stats['maior_drawdown']:.2f} AOA")
    print(f"  📈 Maior sequência de vitórias:     {stats['maior_seq_vitorias']}")
    print(f"  📉 Maior sequência de derrotas:     {stats['maior_seq_derrotas']}")
    print()
    print("─" * 72)
    print("  📋 ANÁLISE POR ESTRATÉGIA")
    print("─" * 72)
    print(f"  {'Estratégia':<22} {'Apostas':>8} {'W':>5} {'L':>5} {'Win%':>7} {'Lucro':>12}")
    print("  " + "─" * 68)

    # Ordena por número de apostas
    ordenado = sorted(stats['stats_estrategia'].items(),
                      key=lambda x: x[1]['apostas'], reverse=True)
    for nome, s in ordenado:
        win_pct = (s['wins'] / s['apostas'] * 100) if s['apostas'] > 0 else 0
        sinal_l = "+" if s['lucro'] >= 0 else ""
        print(f"  {nome:<22} {s['apostas']:>8} {s['wins']:>5} {s['losses']:>5} "
              f"{win_pct:>6.1f}% {sinal_l}{s['lucro']:>10.2f}")

    print()
    print("═" * 72)
    print()

    # ── Avaliação final ──────────────────────────────────────────────────
    if stats['lucro_acumulado'] > 0:
        print(f"  ✅ A estratégia FOI lucrativa neste histórico: +{stats['lucro_acumulado']:.2f} AOA")
        print(f"     ROI de +{stats['roi']:.2f}% sobre o investido total.")
    else:
        print(f"  ⚠️  A estratégia teve PREJUÍZO neste histórico: {stats['lucro_acumulado']:.2f} AOA")
        print(f"     ROI de {stats['roi']:.2f}% sobre o investido total.")

    print()
    print(f"  💡 Nota: a janela de rosa usa um minuto simulado cíclico.")
    print(f"     Em uso real, os timings reais podem dar resultados ligeiramente diferentes.")
    print()


if __name__ == "__main__":
    print("🔬 Backtesting do Aviator Bot")
    print(f"   Parâmetros: base={APOSTA_BASE} | limite={APOSTA_LIMITE_MAX} | "
          f"reset={RESET_APOS_VITORIAS}W | pausa={MAX_PERDAS_SEGUIDAS}L")
    print()

    historico = carregar_historico()
    if not historico:
        print("❌ Sem histórico para simular. Joga algumas sessões primeiro.")
        exit(1)

    print(f"📂 Carregado: {len(historico)} multiplicadores históricos")
    print(f"   Range: {min(historico):.2f}x → {max(historico):.2f}x")
    print(f"   Média: {sum(historico)/len(historico):.2f}x")
    print()
    print("⏳ A simular...")

    stats = simular(historico)
    imprimir_relatorio(stats)
