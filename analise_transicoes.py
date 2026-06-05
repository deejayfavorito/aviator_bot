# analise_transicoes.py
"""
Analisa os dados recolhidos pelo MODO OBSERVADOR (data/observacao_fases.csv).

Responde a' pergunta central da tese das "3 estacoes":
  - Apos uma fase QUENTE, o que costuma vir?
  - Apos uma fase FRIA, o que costuma vir?
  - Quanto tempo dura cada fase em media?
  - Ha' ciclos previsiveis ou e' tudo aleatorio?

Uso:
  python analise_transicoes.py
"""
import sys
import os
import csv
from collections import defaultdict, Counter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CAMINHO = "data/observacao_fases.csv"


def carregar_observacoes():
    if not os.path.exists(CAMINHO):
        print(f"❌ Ficheiro {CAMINHO} não existe.")
        print("   Corre o bot em MODO OBSERVADOR primeiro (deixa-o a observar")
        print("   após atingir a meta/stop) para recolher dados.")
        return []

    obs = []
    with open(CAMINHO, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                obs.append({
                    "timestamp": row["timestamp"],
                    "crash": float(row["crash"]),
                    "classificacao": row["classificacao"],
                    "pct_rosas": float(row["pct_rosas"]),
                    "q67": float(row["q67"]),
                    "mediana": float(row["mediana"]),
                })
            except (ValueError, KeyError):
                continue
    return obs


def analisar_transicoes(obs):
    """Analisa transicoes entre fases consecutivas."""
    if len(obs) < 2:
        print("⚠️ Dados insuficientes (precisa de pelo menos 2 observações).")
        return

    # Sequencia de classificacoes
    fases = [o["classificacao"] for o in obs]

    # 1. Distribuicao geral das fases
    print("=" * 60)
    print("📊 DISTRIBUIÇÃO GERAL DAS FASES")
    print("=" * 60)
    contador = Counter(fases)
    total = len(fases)
    for fase in ["fria", "normal", "quente"]:
        n = contador.get(fase, 0)
        pct = n / total * 100 if total else 0
        emoji = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[fase]
        barra = "█" * int(pct / 2)
        print(f"  {emoji} {fase:8s}: {n:4d} ({pct:5.1f}%) {barra}")
    print(f"\n  Total de observações: {total}")

    # 2. Matriz de transicoes
    print()
    print("=" * 60)
    print("🔄 MATRIZ DE TRANSIÇÕES (de → para)")
    print("=" * 60)
    print("   Quando estou em fase X, qual é a próxima?")
    print()

    transicoes = defaultdict(Counter)
    for i in range(len(fases) - 1):
        atual = fases[i]
        proxima = fases[i + 1]
        transicoes[atual][proxima] += 1

    for origem in ["fria", "normal", "quente"]:
        emoji_o = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[origem]
        destinos = transicoes[origem]
        total_o = sum(destinos.values())
        if total_o == 0:
            print(f"  {emoji_o} De {origem}: (sem dados)")
            continue
        print(f"  {emoji_o} De {origem} ({total_o} transições):")
        for destino in ["fria", "normal", "quente"]:
            n = destinos.get(destino, 0)
            pct = n / total_o * 100 if total_o else 0
            emoji_d = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[destino]
            barra = "█" * int(pct / 5)
            print(f"      → {emoji_d} {destino:8s}: {pct:5.1f}% ({n})  {barra}")
        print()

    # 3. Duracao media de cada fase (sequencias consecutivas)
    print("=" * 60)
    print("⏱️ DURAÇÃO DAS FASES (rounds consecutivos na mesma fase)")
    print("=" * 60)

    duracoes = defaultdict(list)
    fase_atual = fases[0]
    duracao = 1
    for i in range(1, len(fases)):
        if fases[i] == fase_atual:
            duracao += 1
        else:
            duracoes[fase_atual].append(duracao)
            fase_atual = fases[i]
            duracao = 1
    duracoes[fase_atual].append(duracao)

    for fase in ["fria", "normal", "quente"]:
        ds = duracoes[fase]
        emoji = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[fase]
        if ds:
            media = sum(ds) / len(ds)
            print(f"  {emoji} {fase:8s}: média {media:.1f} rounds | "
                  f"max {max(ds)} | ocorrências {len(ds)}")
        else:
            print(f"  {emoji} {fase:8s}: (sem dados)")

    # 4. Conclusao automatica
    print()
    print("=" * 60)
    print("🧠 CONCLUSÕES")
    print("=" * 60)

    # Verifica se ha' padrao forte de transicao
    achou_padrao = False
    for origem in ["fria", "normal", "quente"]:
        destinos = transicoes[origem]
        total_o = sum(destinos.values())
        if total_o < 5:
            continue
        # Destino mais provavel
        mais_provavel, n = destinos.most_common(1)[0]
        pct = n / total_o * 100
        if pct >= 60:  # padrao forte
            emoji_o = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[origem]
            emoji_d = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}[mais_provavel]
            print(f"  ✅ PADRÃO: após {emoji_o} {origem}, "
                  f"{pct:.0f}% das vezes vem {emoji_d} {mais_provavel}")
            achou_padrao = True

    if not achou_padrao:
        print("  ⚠️ Não há padrões fortes de transição (>60%).")
        print("     As fases parecem mudar de forma maioritariamente aleatória.")
        print("     Isto é consistente com RNG — o histórico não prevê o futuro.")
    else:
        print()
        print("  💡 Se há padrões, podemos usá-los na IA Adaptativa v3:")
        print("     o bot anteciparia a próxima fase com base na actual.")

    print()
    print(f"  📈 Recolhe MAIS dados para conclusões mais fiáveis.")
    print(f"     ({total} observações actuais — ideal: 500+)")


def main():
    obs = carregar_observacoes()
    if not obs:
        return
    analisar_transicoes(obs)


if __name__ == "__main__":
    main()
