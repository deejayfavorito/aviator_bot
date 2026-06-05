#!/usr/bin/env python3
"""
Análise de Transições de Fase — Modo Observador.

Carrega data/observacao_fases.csv (colectado durante Modo Observador)
e analisa como as fases (quente/normal/fria) transitam.

Saídas:
  • Duração média de cada fase
  • Ciclos previsíveis
  • Sequências comuns
  • Recomendações para adaptação de cashout
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter


CAMINHO_OBSERVACAO = Path("data/observacao_fases.csv")


def carregar_dados() -> pd.DataFrame:
    """Carrega dados do CSV de observação."""
    if not CAMINHO_OBSERVACAO.exists():
        print(f"❌ {CAMINHO_OBSERVACAO} não encontrado.")
        print("   Execute o bot em Modo Observador para colectar dados.")
        return None
    
    try:
        df = pd.read_csv(CAMINHO_OBSERVACAO)
        print(f"✅ Carregados {len(df)} eventos de observação")
        return df
    except Exception as e:
        print(f"❌ Erro a carregar CSV: {e}")
        return None


def analisar_duracao_fases(df: pd.DataFrame) -> dict:
    """
    Calcula quanto tempo cada fase dura antes de mudar.
    
    Returns:
        {"fase": {"duracao_media": X, "duracao_max": Y, "count": Z}, ...}
    """
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    duracao_por_fase = defaultdict(list)
    
    for i in range(len(df) - 1):
        fase_atual = df.loc[i, 'classificacao']
        fase_proxima = df.loc[i + 1, 'classificacao']
        
        if fase_atual == fase_proxima:
            # Continua na mesma fase
            duracao = (df.loc[i + 1, 'timestamp'] - df.loc[i, 'timestamp']).total_seconds()
            duracao_por_fase[fase_atual].append(duracao)
    
    resultado = {}
    for fase, durações in duracao_por_fase.items():
        if durações:
            resultado[fase] = {
                "duracao_media": np.mean(durações),
                "duracao_max": np.max(durações),
                "duracao_min": np.min(durações),
                "count": len(durações),
            }
    
    return resultado


def analisar_transicoes(df: pd.DataFrame) -> dict:
    """
    Identifica padrões de transição entre fases.
    
    Ex: quente → normal → fria é um ciclo comum?
    """
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    transicoes = []
    for i in range(len(df) - 1):
        fase_atual = df.loc[i, 'classificacao']
        fase_proxima = df.loc[i + 1, 'classificacao']
        
        if fase_atual != fase_proxima:
            transicoes.append((fase_atual, fase_proxima))
    
    # Conta frequência
    freq_transicoes = Counter(transicoes)
    
    # Identifica ciclos (A→B→A)
    ciclos = defaultdict(int)
    for i in range(len(transicoes) - 1):
        a, b = transicoes[i]
        c, d = transicoes[i + 1]
        if a == d:  # ciclo A→B→A
            ciclos[f"{a}→{b}→{a}"] += 1
    
    return {
        "transicoes": dict(freq_transicoes),
        "ciclos": dict(ciclos),
    }


def analisar_correlacao_rosas(df: pd.DataFrame) -> dict:
    """
    Correlação entre % de rosas e duração de fase.
    
    Hipótese: fases quentes têm mais rosas? Duram menos?
    """
    resultado = {}
    
    for fase in ['fria', 'normal', 'quente']:
        dados_fase = df[df['classificacao'] == fase]
        
        if len(dados_fase) > 0:
            resultado[fase] = {
                "pct_rosas_media": dados_fase['pct_rosas'].mean(),
                "pct_rosas_std": dados_fase['pct_rosas'].std(),
                "q67_media": dados_fase['q67'].mean(),
                "crash_mediano_media": dados_fase['crash_mediano'].mean(),
                "eventos": len(dados_fase),
            }
    
    return resultado


def gerar_relatorio(df: pd.DataFrame):
    """Gera relatório completo de transições."""
    
    print("\n" + "=" * 80)
    print("📊 ANÁLISE DE TRANSIÇÕES DE FASE (Modo Observador)")
    print("=" * 80)
    
    # ─── DURAÇÕES ───────────────────────────────────────────────────────
    print("\n⏱️  DURAÇÃO MÉDIA DE CADA FASE\n")
    duracao = analisar_duracao_fases(df)
    
    for fase in ['fria', 'normal', 'quente']:
        if fase in duracao:
            d = duracao[fase]
            print(f"  {fase.upper():10} → {d['duracao_media']:7.1f}s média "
                  f"({d['duracao_min']:5.1f}s-{d['duracao_max']:5.1f}s) "
                  f"— {d['count']} observações")
        else:
            print(f"  {fase.upper():10} → sem dados")
    
    # ─── TRANSIÇÕES ──────────────────────────────────────────────────────
    print("\n🔄 TRANSIÇÕES ENTRE FASES\n")
    trans = analisar_transicoes(df)
    
    print("  Frequência:")
    for (a, b), freq in sorted(trans['transicoes'].items(), key=lambda x: x[1], reverse=True):
        print(f"    {a:7} → {b:7}  : {freq:3} vezes")
    
    if trans['ciclos']:
        print("\n  Ciclos detectados:")
        for ciclo, freq in sorted(trans['ciclos'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {ciclo:20} : {freq:3} vezes")
    else:
        print("\n  Ciclos: nenhum padrão clara detectado")
    
    # ─── CORRELAÇÃO ──────────────────────────────────────────────────────
    print("\n📈 CORRELAÇÃO: % ROSAS vs FASE\n")
    corr = analisar_correlacao_rosas(df)
    
    for fase in ['fria', 'normal', 'quente']:
        if fase in corr:
            c = corr[fase]
            print(f"  {fase.upper():10} → {c['pct_rosas_media']:5.1f}% rosas "
                  f"± {c['pct_rosas_std']:.1f}% "
                  f"| Q67: {c['q67_media']:.2f}x | Mediana: {c['crash_mediano_media']:.2f}x")
    
    # ─── RECOMENDAÇÕES ──────────────────────────────────────────────────
    print("\n💡 RECOMENDAÇÕES\n")
    
    if 'quente' in corr:
        pct_quente = corr['quente']['pct_rosas_media']
        if pct_quente > 12:
            print("  ✅ Sessões quentes têm >12% rosas — Estratégia Rosa é boa")
        else:
            print("  ⚠️ Sessões quentes têm <12% rosas — Rosa pode não valer")
    
    if 'transicoes' in trans:
        max_transicao = max(trans['transicoes'].items(), key=lambda x: x[1])
        print(f"  📌 Transição mais comum: {max_transicao[0][0]} → {max_transicao[0][1]}")
    
    duracao_quente = duracao.get('quente', {}).get('duracao_media', 0)
    duracao_fria = duracao.get('fria', {}).get('duracao_media', 0)
    
    if duracao_quente > 0 and duracao_fria > 0:
        ratio = duracao_fria / duracao_quente
        if ratio > 1.5:
            print(f"  ⏰ Fases frias duram {ratio:.1f}x mais que quentes")
            print("     → Apostar mais em fases quentes (menos tempo)")
        else:
            print(f"  ⏰ Fases são similares em duração")
    
    # ─── ESTATÍSTICAS ───────────────────────────────────────────────────
    print("\n📊 ESTATÍSTICAS GLOBAIS\n")
    
    total_eventos = len(df)
    eventos_por_fase = df['classificacao'].value_counts()
    
    print(f"  Total de eventos: {total_eventos}")
    for fase in ['fria', 'normal', 'quente']:
        if fase in eventos_por_fase.index:
            count = eventos_por_fase[fase]
            pct = (count / total_eventos * 100)
            print(f"    {fase.upper():10} : {count:4} eventos ({pct:5.1f}%)")
    
    # Timeline
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    duracao_total = (df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 3600
    print(f"\n  Período: {duracao_total:.1f} horas de observação")
    
    print("\n" + "=" * 80)
    print("✨ Análise concluída!\n")


def main():
    print("🔬 Análise de Transições de Fase — Modo Observador\n")
    
    df = carregar_dados()
    if df is None or df.empty:
        return
    
    gerar_relatorio(df)
    
    # Sugestão de próximas ações
    print("📝 PRÓXIMAS AÇÕES:\n")
    print("   1. Se há ciclos claros → calibrar Follow Patterns conforme ciclo")
    print("   2. Se fases quentes = raras → Rosa pode não ser prática")
    print("   3. Se fases duram >60s → considerar pausas entre rounds")
    print("   4. Se há transição clara (A→B) → usar isso para prever cashout\n")


if __name__ == "__main__":
    main()
