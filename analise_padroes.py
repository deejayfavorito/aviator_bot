"""
Análise dos padrões "Follow Patterns" — lê CSVs de sessão e calcula
desempenho por padrão (P1, P2, P3, P4, P5, P6).

Permite identificar:
  - Qual padrão é mais lucrativo
  - Qual padrão tem maior WR
  - Quais ajustes fazem sentido (subir/baixar cashout, fracção, etc.)

Uso:
    python analise_padroes.py
"""
import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════
# CARREGAR DADOS
# ═══════════════════════════════════════════════════════════════════════

def carregar_apostas_sessoes() -> list:
    """Lê todos os CSVs de sessão e retorna apostas marcadas com padrão Pn_*"""
    pasta = Path("data")
    if not pasta.exists():
        return []

    apostas = []
    for ficheiro in sorted(pasta.glob("sessao_*.csv")):
        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    estrat = linha.get("estrategia", "")
                    # Só interessa apostas da estratégia padrões
                    if not estrat.startswith("P"):
                        continue
                    if "_" not in estrat or len(estrat) < 3:
                        continue
                    # Aceita P1, P2, P3, P4, P5, P6 (formato Pn_*)
                    if estrat[1] not in "123456":
                        continue
                    try:
                        apostas.append({
                            "estrategia": estrat,
                            "round_mult": float(linha.get("multiplicador_round", "0") or 0),
                            "cashout_alvo": float(linha.get("cashout_alvo", "0") or 0),
                            "valor_apostado": float(linha.get("valor_apostado", "0") or 0),
                            "resultado": linha.get("resultado", ""),
                            "cashout_obtido": float(linha.get("cashout_obtido", "0") or 0),
                            "lucro_aposta": float(linha.get("lucro_aposta", "0") or 0),
                            "ficheiro": ficheiro.name,
                        })
                    except (ValueError, KeyError):
                        continue
        except Exception:
            continue

    return apostas


# ═══════════════════════════════════════════════════════════════════════
# ANÁLISE
# ═══════════════════════════════════════════════════════════════════════

def analisar_por_padrao(apostas: list) -> dict:
    """Agrupa apostas por nome de padrão e calcula estatísticas."""
    grupos = defaultdict(list)
    for ap in apostas:
        grupos[ap["estrategia"]].append(ap)

    resultados = {}
    for padrao, lista in grupos.items():
        wins = sum(1 for a in lista if a["resultado"] == "ganhou")
        losses = sum(1 for a in lista if a["resultado"] == "perdeu")
        total = wins + losses
        if total == 0:
            continue

        lucro_total = sum(a["lucro_aposta"] for a in lista if a["resultado"] in ("ganhou", "perdeu"))
        investido_total = sum(a["valor_apostado"] for a in lista if a["resultado"] in ("ganhou", "perdeu"))

        cashouts_ganhos = [a["cashout_obtido"] for a in lista if a["resultado"] == "ganhou"]

        resultados[padrao] = {
            "total":          total,
            "wins":           wins,
            "losses":         losses,
            "win_rate":       (wins / total * 100) if total else 0,
            "lucro_total":    lucro_total,
            "investido":      investido_total,
            "roi":            (lucro_total / investido_total * 100) if investido_total else 0,
            "cashout_medio":  sum(cashouts_ganhos) / len(cashouts_ganhos) if cashouts_ganhos else 0,
            "cashout_max":    max(cashouts_ganhos) if cashouts_ganhos else 0,
        }

    return resultados


def gerar_recomendacoes(stats: dict) -> list:
    """Sugere ajustes com base nos dados."""
    recs = []

    for padrao, s in stats.items():
        if s["total"] < 5:
            recs.append(f"⏳ {padrao}: poucas amostras ({s['total']}) — não há base para ajustar.")
            continue

        wr = s["win_rate"]
        roi = s["roi"]

        # Padrão muito mau — sugere desactivar
        if wr < 40 and s["total"] >= 10:
            recs.append(f"🔴 {padrao}: WR {wr:.0f}% MAU em {s['total']} apostas → considera REDUZIR fracção ou desactivar.")

        # Padrão excelente — sugere aumentar
        elif wr >= 85 and roi > 15:
            recs.append(f"🟢 {padrao}: WR {wr:.0f}% EXCELENTE, ROI {roi:+.1f}% → padrão sólido, manter ou aumentar fracção.")

        # Padrão promissor mas ROI baixo
        elif wr >= 70 and roi < 5:
            recs.append(f"🟡 {padrao}: WR alto ({wr:.0f}%) mas ROI baixo ({roi:+.1f}%) → considera subir cashout alvo.")

        # Padrão mediano
        elif wr >= 55:
            recs.append(f"⚪ {padrao}: WR {wr:.0f}%, ROI {roi:+.1f}% → desempenho aceitável, manter.")

        else:
            recs.append(f"🟠 {padrao}: WR {wr:.0f}%, ROI {roi:+.1f}% → desempenho fraco, observar.")

    return recs


# ═══════════════════════════════════════════════════════════════════════
# RELATÓRIO
# ═══════════════════════════════════════════════════════════════════════

def imprimir_relatorio(apostas: list, stats: dict):
    print()
    print("═" * 75)
    print("  📊 ANÁLISE DE PADRÕES — Follow Patterns")
    print("═" * 75)
    print()

    if not apostas:
        print("  ⚠ Sem dados de estratégia 'Follow Patterns' ainda.")
        print("     Activa a estratégia em Config → Guardar e corre uma sessão.")
        print("═" * 75)
        return

    # Resumo global
    total = sum(s["total"] for s in stats.values())
    wins = sum(s["wins"] for s in stats.values())
    losses = sum(s["losses"] for s in stats.values())
    wr_global = (wins / (wins + losses) * 100) if (wins + losses) else 0
    lucro_global = sum(s["lucro_total"] for s in stats.values())
    investido_global = sum(s["investido"] for s in stats.values())
    roi_global = (lucro_global / investido_global * 100) if investido_global else 0

    print(f"  📂 Apostas analisadas: {total}")
    print(f"  📈 Win rate global:    {wr_global:.1f}% ({wins}W / {losses}L)")
    print(f"  💰 Lucro total:        {lucro_global:+.0f} AOA")
    print(f"  📊 ROI global:         {roi_global:+.1f}%")
    print()

    # Tabela por padrão
    print("─" * 75)
    print("  📋 DESEMPENHO POR PADRÃO")
    print("─" * 75)
    print(f"  {'Padrão':25s} {'Apostas':>8s} {'W':>4s} {'L':>4s} {'WR':>7s} {'ROI':>8s}  {'Lucro AOA':>10s}")
    print("  " + "─" * 73)

    # Ordena por lucro (descendente)
    for padrao in sorted(stats.keys(), key=lambda p: -stats[p]["lucro_total"]):
        s = stats[padrao]
        emoji = "🟢" if s["roi"] > 10 else ("🟡" if s["roi"] > 0 else "🔴")
        print(f"  {emoji} {padrao:23s} {s['total']:>6d}  {s['wins']:>4d} {s['losses']:>4d} "
              f"{s['win_rate']:>6.1f}% {s['roi']:>+7.1f}% {s['lucro_total']:>+10.0f}")

    print()
    print("─" * 75)
    print("  🔬 ESTATÍSTICAS DETALHADAS")
    print("─" * 75)
    for padrao in sorted(stats.keys()):
        s = stats[padrao]
        print(f"  {padrao}:")
        print(f"     Apostas: {s['total']} | WR: {s['win_rate']:.1f}% | ROI: {s['roi']:+.2f}%")
        print(f"     Cashout médio (vitórias): {s['cashout_medio']:.2f}x | Max: {s['cashout_max']:.2f}x")
        print(f"     Lucro: {s['lucro_total']:+.0f} AOA | Investido: {s['investido']:.0f} AOA")
        print()

    print("─" * 75)
    print("  💡 RECOMENDAÇÕES")
    print("─" * 75)
    for rec in gerar_recomendacoes(stats):
        print(f"  {rec}")
    print()
    print("═" * 75)


def main():
    print("🔍 A carregar sessões...")
    apostas = carregar_apostas_sessoes()
    print(f"📂 Encontradas {len(apostas)} apostas de estratégia 'Follow Patterns'")

    if not apostas:
        print()
        print("⚠ Ainda não há apostas com a estratégia 'Follow Patterns'.")
        print("   • Vai à aba Config")
        print("   • Marca '🎯 Follow Patterns'")
        print("   • Guarda e inicia o bot")
        print("   • Depois de algumas sessões, volta a correr esta análise")
        return

    stats = analisar_por_padrao(apostas)
    imprimir_relatorio(apostas, stats)


if __name__ == "__main__":
    main()
