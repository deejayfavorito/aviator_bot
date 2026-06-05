"""
Diagnóstico do Kelly Criterion — mostra estatísticas das estratégias.

Uso:
    python diagnostico_kelly.py
"""
from gestor.kelly_criterion import diagnostico, MIN_AMOSTRAS


def main():
    print("🔬 Diagnóstico Kelly Criterion")
    print()

    diag = diagnostico()

    if not diag:
        print("❌ Sem dados de apostas. Joga algumas sessões primeiro.")
        return

    print("─" * 72)
    print(f"  📊 ESTATÍSTICAS POR CASHOUT ALVO (min. {MIN_AMOSTRAS} amostras para Kelly)")
    print("─" * 72)
    print(f"  {'Cashout':>9} {'Total':>7} {'Wins':>6} {'Win%':>7} {'Kelly':>9} {'Status':>20}")
    print("  " + "─" * 64)

    for cashout, info in sorted(diag.items()):
        if info.get("insuficiente"):
            print(f"  {cashout:>7.2f}x  {info['total']:>7} {info['wins']:>6} "
                  f"{'?':>7} {'?':>9}  amostras insuficientes")
        else:
            status = "✅ Vantajoso" if info["vantajoso"] else "❌ Desvantajoso"
            print(f"  {cashout:>7.2f}x  {info['total']:>7} {info['wins']:>6} "
                  f"{info['win_rate']*100:>6.1f}% {info['kelly']:>+8.3f}  {status}")
    print()

    print("─" * 72)
    print("  💡 INTERPRETAÇÃO")
    print("─" * 72)
    print()
    print("  Kelly > 0: aposta tem expectativa matemática POSITIVA. Vale apostar.")
    print("  Kelly < 0: aposta tem expectativa NEGATIVA. Não devias apostar.")
    print("  Quanto maior Kelly, maior a vantagem matemática.")
    print()
    print("  Modos:")
    print("    off          → desliga Kelly, usa aposta da Estratégia 2 normal")
    print("    conservador  → 25% do Kelly (recomendado, menos variância)")
    print("    pleno        → 100% do Kelly (mais agressivo)")
    print()


if __name__ == "__main__":
    main()
