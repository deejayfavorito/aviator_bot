# utils/dashboard.py
"""
Dashboard visual no terminal — mostra estado actual a cada round.

Não interfere com a lógica do bot. É uma "view" pura sobre o estado.
"""
import json
from pathlib import Path
from typing import Optional


def _carregar_json(caminho: Path) -> dict:
    """Lê JSON com tolerância a erro."""
    if not caminho.exists():
        return {}
    try:
        with open(caminho) as f:
            return json.load(f)
    except Exception:
        return {}


def imprimir_dashboard(
    multiplicador_round: Optional[float] = None,
    resultado: Optional[str] = None,
    valor_apostado: float = 0,
    cashout_obtido: float = 0,
    vitorias_sessao: int = 0,
    derrotas_sessao: int = 0,
):
    """
    Imprime painel visual depois de cada round.

    resultado: "ganhou", "perdeu", "pulado", "falha"
    """
    estado_aposta   = _carregar_json(Path("data/estado_aposta_composta.json"))
    estado_estrat   = _carregar_json(Path("data/estado_estrategia.json"))
    estado_banca    = _carregar_json(Path("data/estado_banca.json"))

    valor_base       = estado_aposta.get("valor_base", 100.0)
    valor_atual      = estado_aposta.get("valor_atual", valor_base)
    vitorias_cadeia  = estado_aposta.get("vitorias_seguidas", 0)
    reset_apos       = estado_aposta.get("reset_apos_vitorias", 3)
    cofre            = estado_aposta.get("lucro_cofre", 0.0)

    lucro_total      = estado_banca.get("lucro", 0.0)
    ganhos           = estado_banca.get("ganhos", 0.0)
    perdas           = estado_banca.get("perdas", 0.0)

    perdas_seg       = estado_estrat.get("consecutivas_perdas", 0)
    ganhos_seg       = estado_estrat.get("consecutivas_ganhos", 0)

    # ── Símbolo do resultado ─────────────────────────────────────────────
    simbolo = {
        "ganhou": "💰",
        "perdeu": "💥",
        "pulado": "⏭️",
        "falha":  "⚠️",
    }.get(resultado, "📊")

    # ── Win rate ─────────────────────────────────────────────────────────
    total_apostas = vitorias_sessao + derrotas_sessao
    win_rate = (vitorias_sessao / total_apostas * 100) if total_apostas > 0 else 0

    # ── ROI ──────────────────────────────────────────────────────────────
    investido = ganhos + perdas
    roi = (lucro_total / investido * 100) if investido > 0 else 0

    # ── Linha de progresso da cadeia ─────────────────────────────────────
    barra = "▮" * vitorias_cadeia + "▯" * (reset_apos - vitorias_cadeia)

    print()
    print("═" * 67)
    if multiplicador_round is not None:
        print(f"  {simbolo}  Round {multiplicador_round:.2f}x  |  Cashout obtido: {cashout_obtido:.2f}x")
    print(f"  💰 Banca: {lucro_total:+.0f} AOA  |  🏦 Cofre: {cofre:.0f} AOA")
    print(f"  📊 Aposta actual: {valor_atual:.0f} AOA  |  Próxima: {valor_atual:.0f} AOA")
    print(f"  🔗 Cadeia: [{barra}] {vitorias_cadeia}/{reset_apos}")
    print(f"  📈 Sessão: {vitorias_sessao}W / {derrotas_sessao}L  ({win_rate:.0f}%)  |  ROI: {roi:+.1f}%")
    print(f"  🔄 Seguidas: {ganhos_seg}W em curso  |  {perdas_seg}L consecutivas")
    print("═" * 67)
    print()
