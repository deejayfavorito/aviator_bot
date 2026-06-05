"""
Análise Temporal — descobre padrões nos dados de sessões.

Lê todos os ficheiros `data/sessao_*.csv` e analisa:
  - Performance por hora do dia
  - Performance por dia da semana
  - Performance por minuto da hora (validar janelas do PDF)
  - Distribuição de multiplicadores por período
  - Win rate vs hora

NÃO interfere com o bot — apenas lê ficheiros.

Uso:
    python analise_temporal.py
"""
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional


def carregar_todas_sessoes() -> List[dict]:
    """Lê todos os data/sessao_*.csv e retorna lista de apostas."""
    apostas = []
    pasta = Path("data")

    if not pasta.exists():
        return apostas

    ficheiros = sorted(pasta.glob("sessao_*.csv"))
    print(f"📂 Encontrados {len(ficheiros)} ficheiros de sessão")

    for ficheiro in ficheiros:
        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    if not linha.get("timestamp"):
                        continue
                    try:
                        linha["timestamp"] = datetime.fromisoformat(linha["timestamp"])
                        linha["multiplicador_round"] = float(linha["multiplicador_round"])
                        linha["cashout_alvo"]        = float(linha["cashout_alvo"])
                        linha["valor_apostado"]      = float(linha["valor_apostado"])
                        linha["cashout_obtido"]      = float(linha["cashout_obtido"])
                        linha["lucro_aposta"]        = float(linha["lucro_aposta"])
                        apostas.append(linha)
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            print(f"⚠️  Erro ao ler {ficheiro}: {e}")

    return apostas


def carregar_historico_csv() -> List[tuple]:
    """Lê data/historico.csv com timestamps de cada crash."""
    crashes = []
    path = Path("data/historico.csv")
    if not path.exists():
        return crashes

    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            partes = linha.strip().split(",")
            if len(partes) >= 3 and partes[1] == "crash_registado":
                try:
                    ts   = datetime.fromisoformat(partes[0])
                    mult = float(partes[2].replace("x", "").strip())
                    crashes.append((ts, mult))
                except (ValueError, IndexError):
                    pass
    return crashes


# ─── Análises ─────────────────────────────────────────────────────────────

def analisar_por_hora(apostas: List[dict]) -> Dict[int, dict]:
    """Agrupa apostas por hora do dia (0-23)."""
    por_hora = defaultdict(lambda: {"wins": 0, "losses": 0, "lucro": 0.0, "apostas": 0})

    for a in apostas:
        if a["resultado"] not in ("ganhou", "perdeu"):
            continue
        h = a["timestamp"].hour
        por_hora[h]["apostas"] += 1
        por_hora[h]["lucro"]   += a["lucro_aposta"]
        if a["resultado"] == "ganhou":
            por_hora[h]["wins"] += 1
        else:
            por_hora[h]["losses"] += 1

    return dict(sorted(por_hora.items()))


def analisar_por_dia_semana(apostas: List[dict]) -> Dict[str, dict]:
    """Agrupa apostas por dia da semana."""
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    por_dia = defaultdict(lambda: {"wins": 0, "losses": 0, "lucro": 0.0, "apostas": 0})

    for a in apostas:
        if a["resultado"] not in ("ganhou", "perdeu"):
            continue
        dia = dias[a["timestamp"].weekday()]
        por_dia[dia]["apostas"] += 1
        por_dia[dia]["lucro"]   += a["lucro_aposta"]
        if a["resultado"] == "ganhou":
            por_dia[dia]["wins"] += 1
        else:
            por_dia[dia]["losses"] += 1

    # Ordena por ordem dos dias
    return {d: por_dia[d] for d in dias if d in por_dia}


def analisar_minutos_rosa(crashes: List[tuple]) -> Dict[int, dict]:
    """
    Para cada minuto da hora (0-59), calcula:
    - Quantos crashes aconteceram
    - Quantos foram 'rosa' (>10x)
    - Multiplicador médio
    """
    por_min = defaultdict(lambda: {"total": 0, "rosa": 0, "soma_mults": 0.0, "max_mult": 0.0})

    for ts, mult in crashes:
        m = ts.minute
        por_min[m]["total"] += 1
        por_min[m]["soma_mults"] += mult
        por_min[m]["max_mult"] = max(por_min[m]["max_mult"], mult)
        if mult > 10.0:
            por_min[m]["rosa"] += 1

    return dict(sorted(por_min.items()))


def analisar_distribuicao_multiplicadores(crashes: List[tuple]) -> dict:
    """Distribuição geral dos multiplicadores."""
    if not crashes:
        return {}

    total = len(crashes)
    azuis = sum(1 for _, m in crashes if m < 2.0)
    roxos = sum(1 for _, m in crashes if 2.0 <= m <= 10.0)
    rosas = sum(1 for _, m in crashes if m > 10.0)
    mega  = sum(1 for _, m in crashes if m > 100.0)

    media = sum(m for _, m in crashes) / total

    return {
        "total":  total,
        "media":  media,
        "azul%":  azuis / total * 100,
        "roxo%":  roxos / total * 100,
        "rosa%":  rosas / total * 100,
        "mega%":  mega  / total * 100,
        "max":    max(m for _, m in crashes),
    }


# ─── Impressão ────────────────────────────────────────────────────────────

def imprimir_relatorio(apostas: List[dict], crashes: List[tuple]):
    print()
    print("═" * 72)
    print("  📊 ANÁLISE TEMPORAL")
    print("═" * 72)
    print()
    print(f"  📂 Total de apostas analisadas: {len(apostas)}")
    print(f"  📈 Total de crashes registados: {len(crashes)}")
    if apostas:
        primeiro = min(a["timestamp"] for a in apostas)
        ultimo   = max(a["timestamp"] for a in apostas)
        print(f"  📅 Período: {primeiro:%Y-%m-%d %H:%M} → {ultimo:%Y-%m-%d %H:%M}")
    print()

    # ─── 1. Distribuição de multiplicadores ──────────────────────────────
    print("─" * 72)
    print("  📊 DISTRIBUIÇÃO DE MULTIPLICADORES")
    print("─" * 72)
    dist = analisar_distribuicao_multiplicadores(crashes)
    if dist:
        print(f"  Total:  {dist['total']} crashes")
        print(f"  Média:  {dist['media']:.2f}x")
        print(f"  Máximo: {dist['max']:.2f}x")
        print()
        print(f"  🔵 Azul (<2.0x):    {dist['azul%']:.1f}%")
        print(f"  🟣 Roxo (2-10x):    {dist['roxo%']:.1f}%")
        print(f"  🌹 Rosa (>10x):     {dist['rosa%']:.1f}%")
        print(f"  💎 Mega (>100x):    {dist['mega%']:.1f}%")
    print()

    # ─── 2. Performance por hora do dia ──────────────────────────────────
    if apostas:
        print("─" * 72)
        print("  🕐 PERFORMANCE POR HORA DO DIA")
        print("─" * 72)
        print(f"  {'Hora':>5} {'Apostas':>8} {'W':>5} {'L':>5} {'Win%':>7} {'Lucro':>12}")
        print("  " + "─" * 56)
        por_hora = analisar_por_hora(apostas)
        for h, s in por_hora.items():
            win_pct = (s['wins'] / s['apostas'] * 100) if s['apostas'] > 0 else 0
            sinal = "+" if s['lucro'] >= 0 else ""
            print(f"  {h:>3}h  {s['apostas']:>8} {s['wins']:>5} {s['losses']:>5} "
                  f"{win_pct:>6.1f}% {sinal}{s['lucro']:>10.2f}")
        print()

        # ─── 3. Performance por dia da semana ────────────────────────────
        print("─" * 72)
        print("  📅 PERFORMANCE POR DIA DA SEMANA")
        print("─" * 72)
        print(f"  {'Dia':<10} {'Apostas':>8} {'W':>5} {'L':>5} {'Win%':>7} {'Lucro':>12}")
        print("  " + "─" * 56)
        por_dia = analisar_por_dia_semana(apostas)
        for d, s in por_dia.items():
            win_pct = (s['wins'] / s['apostas'] * 100) if s['apostas'] > 0 else 0
            sinal = "+" if s['lucro'] >= 0 else ""
            print(f"  {d:<10} {s['apostas']:>8} {s['wins']:>5} {s['losses']:>5} "
                  f"{win_pct:>6.1f}% {sinal}{s['lucro']:>10.2f}")
        print()

    # ─── 4. Análise dos minutos (validar janelas de rosa do PDF) ────────
    if crashes:
        print("─" * 72)
        print("  🌹 ANÁLISE POR MINUTO DA HORA (validar janelas de rosa do PDF)")
        print("─" * 72)
        print("  Janelas que o PDF marca: 02-03, 08-09, 20-22, 28-30, 38-39, 41, 55-57")
        print()
        print(f"  {'Min':>4} {'Total':>7} {'Rosas':>7} {'Rosa%':>7} {'Média':>8} {'Max':>10}")
        print("  " + "─" * 50)

        por_min = analisar_minutos_rosa(crashes)
        # Marca os minutos do PDF
        minutos_pdf = set()
        for ini, fim in [(2,3),(8,9),(20,22),(28,30),(38,39),(41,41),(55,57)]:
            for m in range(ini, fim + 1):
                minutos_pdf.add(m)

        for m, s in por_min.items():
            if s["total"] == 0:
                continue
            rosa_pct = (s['rosa'] / s['total'] * 100) if s['total'] > 0 else 0
            media    = s['soma_mults'] / s['total'] if s['total'] > 0 else 0
            marcador = "🌹" if m in minutos_pdf else "  "
            print(f"  {marcador}{m:>2}  {s['total']:>7} {s['rosa']:>7} "
                  f"{rosa_pct:>6.1f}% {media:>7.2f}x {s['max_mult']:>9.2f}x")
        print()

        # ─── 5. Verificar se a teoria do PDF se confirma ─────────────────
        rosa_pdf  = sum(s['rosa']  for m, s in por_min.items() if m in minutos_pdf)
        total_pdf = sum(s['total'] for m, s in por_min.items() if m in minutos_pdf)
        rosa_fora  = sum(s['rosa']  for m, s in por_min.items() if m not in minutos_pdf)
        total_fora = sum(s['total'] for m, s in por_min.items() if m not in minutos_pdf)

        pct_pdf  = (rosa_pdf  / total_pdf  * 100) if total_pdf  > 0 else 0
        pct_fora = (rosa_fora / total_fora * 100) if total_fora > 0 else 0

        print("─" * 72)
        print("  🔬 TESTE DA TEORIA DO PDF (janelas de rosa)")
        print("─" * 72)
        print(f"  Dentro das janelas:    {rosa_pdf}/{total_pdf} rosas ({pct_pdf:.1f}%)")
        print(f"  Fora das janelas:      {rosa_fora}/{total_fora} rosas ({pct_fora:.1f}%)")
        print()
        if total_pdf > 0 and total_fora > 0:
            diferenca = pct_pdf - pct_fora
            if abs(diferenca) < 1.0:
                print(f"  📊 Conclusão: NÃO há diferença significativa ({diferenca:+.1f}pp).")
                print(f"     A teoria do PDF não se confirma com estes dados.")
            elif diferenca > 0:
                print(f"  ✅ Conclusão: dentro das janelas há +{diferenca:.1f}pp mais rosas.")
                print(f"     A teoria do PDF parece confirmar-se.")
            else:
                print(f"  ❌ Conclusão: dentro das janelas há {diferenca:.1f}pp MENOS rosas.")
                print(f"     A teoria do PDF parece INVÁLIDA com estes dados.")
        print()

    print("═" * 72)
    print()


if __name__ == "__main__":
    print("🔍 Análise Temporal do Aviator Bot")
    print()

    apostas = carregar_todas_sessoes()
    crashes = carregar_historico_csv()

    if not apostas and not crashes:
        print("❌ Sem dados para analisar.")
        print("   Joga algumas sessões primeiro.")
        exit(1)

    imprimir_relatorio(apostas, crashes)
