# relatorio_estrategia_rosa.py
"""
Mostra o relatório de desempenho da ESTRATÉGIA ROSA.

Lê data/estrategia_rosa.csv (gerado pelo bot quando a Estratégia Rosa
está activa) e mostra: total de apostas pós-rosa, win rate, lucro, e
se o padrão "depois de rosa vem >=2x" se confirma vs a base rate.

Uso:
  python relatorio_estrategia_rosa.py
"""
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from estrategia.estrategia_rosa import relatorio_rosa
    print(relatorio_rosa())
except ImportError as e:
    print(f"❌ Não consegui importar a estratégia rosa: {e}")
    print("   Verifica que tens estrategia/estrategia_rosa.py")
except Exception as e:
    print(f"⚠️ Erro: {e}")
