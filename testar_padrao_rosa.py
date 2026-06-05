# testar_padrao_rosa.py
"""
Testa empiricamente o PADRÃO DO ROSA observado pelo utilizador:

  Hipótese 1: depois de um ROSA (>=10x), o próximo crash tende a ser >=2x?
  Hipótese 2: depois de ROSA→AZUL(<2x), o crash seguinte tende a ser >=2x?
  Hipótese 3: depois de um ROSA, qual a hipótese de vir outro ROSA?

Compara com a BASE RATE (a taxa normal, sem condição) para ver se o padrão
é real ou é apenas a frequência natural do jogo.

Usa os crashes ORDENADOS de data/historico.csv (mesma fonte do analise_temporal).

Uso:
  python testar_padrao_rosa.py
"""
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

LIMIAR_ROSA = 10.0
LIMIAR_ROXO = 2.0   # "decente" = aposta a 1.5-2x ganha


def carregar_crashes_ordenados():
    """Lê data/historico.csv e retorna lista de crashes na ordem cronológica."""
    crashes = []
    path = Path("data/historico.csv")
    if not path.exists():
        print(f"❌ {path} não existe.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            partes = linha.strip().split(",")
            if len(partes) >= 3 and partes[1] == "crash_registado":
                try:
                    mult = float(partes[2].replace("x", "").strip())
                    if mult >= 1.0:
                        crashes.append(mult)
                except ValueError:
                    continue
    return crashes


def classificar(c):
    if c >= LIMIAR_ROSA:
        return "rosa"
    elif c >= LIMIAR_ROXO:
        return "roxo"
    else:
        return "azul"


def pct(n, total):
    return (n / total * 100) if total else 0.0


def main():
    crashes = carregar_crashes_ordenados()
    if len(crashes) < 50:
        print(f"⚠️ Só {len(crashes)} crashes — amostra pequena. "
              f"(Idealmente 500+). A continuar mesmo assim.")
        if not crashes:
            return

    n = len(crashes)

    # ─── BASE RATES (taxas normais, sem condição) ────────────────────
    base_2x   = sum(1 for c in crashes if c >= LIMIAR_ROXO)
    base_10x  = sum(1 for c in crashes if c >= LIMIAR_ROSA)
    base_15x  = sum(1 for c in crashes if c >= 1.5)

    print("=" * 64)
    print("📊 BASE RATES (a taxa NORMAL do jogo, sem qualquer condição)")
    print("=" * 64)
    print(f"  Total de crashes: {n}")
    print(f"  P(crash >= 1.5x) = {pct(base_15x, n):.1f}%   ← relevante p/ cashout 1.5x")
    print(f"  P(crash >= 2.0x) = {pct(base_2x, n):.1f}%   ← 'vem roxo ou melhor'")
    print(f"  P(crash >= 10x)  = {pct(base_10x, n):.1f}%   ← 'vem rosa'")
    print()
    print("  ⚠️ Para o teu padrão ser REAL, as probabilidades CONDICIONAIS")
    print("     abaixo têm de ser CLARAMENTE MAIORES que estas base rates.")
    print()

    # ─── HIPÓTESE 1: depois de ROSA, o próximo crash ─────────────────
    # Percorre os crashes; sempre que crashes[i] é rosa, olha crashes[i+1]
    apos_rosa = []
    for i in range(n - 1):
        if crashes[i] >= LIMIAR_ROSA:
            apos_rosa.append(crashes[i + 1])

    if apos_rosa:
        m = len(apos_rosa)
        ar_15 = sum(1 for c in apos_rosa if c >= 1.5)
        ar_2  = sum(1 for c in apos_rosa if c >= LIMIAR_ROXO)
        ar_10 = sum(1 for c in apos_rosa if c >= LIMIAR_ROSA)

        print("=" * 64)
        print(f"🌹 HIPÓTESE 1: o que vem DEPOIS de um ROSA? ({m} casos)")
        print("=" * 64)
        print(f"  P(próximo >= 1.5x | rosa antes) = {pct(ar_15, m):.1f}%   "
              f"(base: {pct(base_15x, n):.1f}%)  → {_delta(pct(ar_15,m), pct(base_15x,n), m)}")
        print(f"  P(próximo >= 2.0x | rosa antes) = {pct(ar_2, m):.1f}%   "
              f"(base: {pct(base_2x, n):.1f}%)  → {_delta(pct(ar_2,m), pct(base_2x,n), m)}")
        print(f"  P(próximo >= 10x  | rosa antes) = {pct(ar_10, m):.1f}%   "
              f"(base: {pct(base_10x, n):.1f}%)  → {_delta(pct(ar_10,m), pct(base_10x,n), m)}")
        print()

    # ─── HIPÓTESE 2: ROSA → AZUL, depois? ────────────────────────────
    apos_rosa_azul = []
    for i in range(n - 2):
        if crashes[i] >= LIMIAR_ROSA and crashes[i + 1] < LIMIAR_ROXO:
            apos_rosa_azul.append(crashes[i + 2])

    if apos_rosa_azul:
        m = len(apos_rosa_azul)
        ra_2 = sum(1 for c in apos_rosa_azul if c >= LIMIAR_ROXO)
        ra_15 = sum(1 for c in apos_rosa_azul if c >= 1.5)
        print("=" * 64)
        print(f"🌹→🔵 HIPÓTESE 2: ROSA seguido de AZUL, o que vem depois? ({m} casos)")
        print("=" * 64)
        print(f"  P(>= 1.5x | rosa→azul) = {pct(ra_15, m):.1f}%   "
              f"(base: {pct(base_15x, n):.1f}%)  → {_delta(pct(ra_15,m), pct(base_15x,n), m)}")
        print(f"  P(>= 2.0x | rosa→azul) = {pct(ra_2, m):.1f}%   "
              f"(base: {pct(base_2x, n):.1f}%)  → {_delta(pct(ra_2,m), pct(base_2x,n), m)}")
        print()

    # ─── HIPÓTESE 3: ROSA → ROSA consecutivo? ────────────────────────
    if apos_rosa:
        m = len(apos_rosa)
        print("=" * 64)
        print(f"🌹🌹 HIPÓTESE 3: rosas consecutivos ({m} rosas analisados)")
        print("=" * 64)
        print(f"  P(próximo também ser rosa | rosa antes) = {pct(ar_10, m):.1f}%")
        print(f"  (base de rosa: {pct(base_10x, n):.1f}%)  → {_delta(pct(ar_10,m), pct(base_10x,n), m)}")
        print()

    # ─── SIMULAÇÃO DA ESTRATÉGIA DO UTILIZADOR ───────────────────────
    print("=" * 64)
    print("🎲 SIMULAÇÃO: a TUA estratégia (apostar só depois de rosa)")
    print("=" * 64)
    print("  Regra: depois de rosa, aposta cashout 2.0x. Se falha, aposta")
    print("  a seguinte. Se 2 falham, para até vir outro rosa.")
    print()

    for alvo in (1.5, 2.0):
        resultado = _simular_estrategia(crashes, alvo)
        sinal = "✅ LUCRO" if resultado["lucro"] > 0 else "❌ PERDA"
        print(f"  Cashout alvo {alvo:.1f}x:")
        print(f"     Apostas: {resultado['apostas']} | "
              f"{resultado['wins']}W/{resultado['losses']}L "
              f"({pct(resultado['wins'], resultado['apostas']):.1f}%)")
        print(f"     Lucro simulado (aposta 100/round): {resultado['lucro']:+.0f} AOA  {sinal}")
        print()

    # ─── CONCLUSÃO ───────────────────────────────────────────────────
    print("=" * 64)
    print("🧠 CONCLUSÃO")
    print("=" * 64)
    if apos_rosa:
        m_rosa = len(apos_rosa)
        diff_2x = pct(ar_2, m_rosa) - pct(base_2x, n)
        margem = _margem_erro(m_rosa)
        print(f"  Depois de rosa, P(>=2x) = {pct(ar_2,m_rosa):.1f}% vs base {pct(base_2x,n):.1f}%")
        print(f"  Diferença: {diff_2x:+.1f}pp | Margem de erro (±): {margem:.1f}pp")
        print()
        if abs(diff_2x) <= margem:
            print(f"  ⚠️ A diferença ({abs(diff_2x):.1f}pp) está DENTRO da margem de erro")
            print(f"     ({margem:.1f}pp). Isto significa: SEM SINAL ESTATÍSTICO.")
            print(f"     O rosa não prevê o próximo crash — é a falácia do jogador.")
            print(f"     O padrão que viste foi memória selectiva (lembramo-nos dos")
            print(f"     acertos, esquecemos as falhas).")
        else:
            print(f"  ⁉️ A diferença ({abs(diff_2x):.1f}pp) EXCEDE a margem de erro")
            print(f"     ({margem:.1f}pp). Pode haver sinal real — vale investigar")
            print(f"     com mais dados para confirmar que não é variância.")
        print()
        print(f"  💡 LEMBRA: a simulação acima pode dar 'lucro' por variância mesmo")
        print(f"     quando NÃO há sinal (testei com RNG puro e deu lucro às vezes).")
        print(f"     Só confia se a diferença EXCEDER a margem de erro de forma")
        print(f"     consistente em MUITOS dados (500+ rosas, idealmente).")
    print()
    print(f"  📈 Baseado em {n} crashes reais das tuas sessões.")


def _delta(cond, base, n_casos=None):
    d = cond - base
    # Margem de erro aproximada (95% CI) para uma proporção
    aviso = ""
    if n_casos and n_casos < 200:
        aviso = f"  ⚠️ só {n_casos} casos — pouco fiável"
    if abs(d) < 1.5:
        return f"≈ igual (sem sinal){aviso}"
    elif d > 0:
        return f"+{d:.1f}pp{aviso}"
    else:
        return f"{d:.1f}pp menor{aviso}"


def _margem_erro(n):
    """Margem de erro aproximada (95% CI) para uma proporção, em pontos percentuais."""
    if n <= 0:
        return 100.0
    import math
    # 1.96 * sqrt(0.25/n) * 100 — pior caso (p=0.5)
    return 1.96 * math.sqrt(0.25 / n) * 100


def _simular_estrategia(crashes, alvo):
    """
    Simula: depois de rosa, aposta a 'alvo'. Se falha, aposta a seguinte.
    Se 2 seguidas falham, para até vir outro rosa.
    Aposta fixa de 100 por round (sem cadeia, para medir o sinal puro).
    """
    aposta = 100.0
    lucro = 0.0
    wins = losses = apostas = 0
    n = len(crashes)
    i = 0
    while i < n - 1:
        if crashes[i] >= LIMIAR_ROSA:
            # Veio rosa — apostar nos próximos (até 2 tentativas)
            tentativas = 0
            j = i + 1
            while j < n and tentativas < 2:
                crash = crashes[j]
                apostas += 1
                if crash >= alvo:
                    lucro += aposta * (alvo - 1)
                    wins += 1
                    # Ganhou — se o próprio crash for rosa, continua; senão para
                    if crash >= LIMIAR_ROSA:
                        i = j  # novo rosa, recomeça
                        break
                    else:
                        i = j + 1
                        break
                else:
                    lucro -= aposta
                    losses += 1
                    tentativas += 1
                    j += 1
            else:
                i = j
                continue
            if tentativas >= 2:
                i = j
        else:
            i += 1
    return {"lucro": lucro, "wins": wins, "losses": losses, "apostas": apostas}


if __name__ == "__main__":
    main()
