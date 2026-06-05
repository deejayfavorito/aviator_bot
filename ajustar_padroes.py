"""
Utilitário para AJUSTAR os parâmetros da estratégia "Follow Patterns".

Permite alterar:
  - Cashout alvo de cada padrão
  - Fracção da banca apostada
  - Limiares (quantos azuis = regressão? quantas rosas = hot streak?)

Sem precisar de mexer em estrategia_padroes.py.

Uso:
    python ajustar_padroes.py
"""
import json
from pathlib import Path
from datetime import datetime


CAMINHO_PARAMS = Path("config/parametros_padroes.json")

# Valores DEFAULT (caso o ficheiro não exista)
DEFAULTS = {
    "P2_min_azuis":            6,      # mínimo de azuis seguidos para P2
    "P2_cashout":              2.0,    # alvo do P2
    "P2_fracao":               0.5,    # 50% da base
    "P3_min_azuis_combo":      5,      # azuis para combo
    "P3_cashout_normal":       3.0,    # alvo combo normal
    "P3_cashout_jackpot":      5.0,    # alvo combo min 49
    "P3_fracao_normal":        0.3,
    "P3_fracao_jackpot":       0.2,
    "P4_min_rosas":            2,      # mínimo de rosas em 10 para hot
    "P4_cashout":              1.30,
    "P5_limiar_rosa_queimada": 5.0,    # se último >= isto = P5
    "window_pos_mega":         3,      # rondas a evitar após mega
    "window_analise":          10,     # janela para analisar
    "actualizado_em":          datetime.now().isoformat(),
    "notas":                   "Auto-gerado. Edita à mão se quiseres."
}


def carregar():
    """Carrega parâmetros (cria ficheiro default se não existir)."""
    if not CAMINHO_PARAMS.exists():
        gravar(DEFAULTS.copy())
        print(f"✅ Ficheiro criado: {CAMINHO_PARAMS}")
        return DEFAULTS.copy()
    try:
        with open(CAMINHO_PARAMS, "r", encoding="utf-8") as f:
            params = json.load(f)
        # Garantir que tem todos os campos (se adicionarmos novos)
        for k, v in DEFAULTS.items():
            if k not in params:
                params[k] = v
        return params
    except Exception as e:
        print(f"⚠ Erro a ler {CAMINHO_PARAMS}: {e}")
        return DEFAULTS.copy()


def gravar(params: dict):
    """Grava parâmetros no ficheiro."""
    CAMINHO_PARAMS.parent.mkdir(parents=True, exist_ok=True)
    params["actualizado_em"] = datetime.now().isoformat()
    with open(CAMINHO_PARAMS, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)


def mostrar(params: dict):
    print()
    print("═" * 65)
    print("  ⚙ PARÂMETROS ACTUAIS — Follow Patterns")
    print("═" * 65)
    print()
    print(f"  P2 (Regressão — azuis seguidos):")
    print(f"     Mínimo de azuis:  {params['P2_min_azuis']}")
    print(f"     Cashout alvo:     {params['P2_cashout']:.2f}x")
    print(f"     Fracção da base:  {params['P2_fracao']*100:.0f}%")
    print()
    print(f"  P3 (Combo — min quente + azuis):")
    print(f"     Min azuis combo:  {params['P3_min_azuis_combo']}")
    print(f"     Cashout normal:   {params['P3_cashout_normal']:.2f}x")
    print(f"     Cashout jackpot:  {params['P3_cashout_jackpot']:.2f}x")
    print(f"     Fracção normal:   {params['P3_fracao_normal']*100:.0f}%")
    print(f"     Fracção jackpot:  {params['P3_fracao_jackpot']*100:.0f}%")
    print()
    print(f"  P4 (Hot streak — rosas recentes):")
    print(f"     Min rosas em 10:  {params['P4_min_rosas']}")
    print(f"     Cashout alvo:     {params['P4_cashout']:.2f}x")
    print()
    print(f"  P5 (Rosa queimada):")
    print(f"     Limiar último:    {params['P5_limiar_rosa_queimada']:.2f}x")
    print()
    print(f"  Janelas:")
    print(f"     Rondas pós-mega:  {params['window_pos_mega']}")
    print(f"     Janela análise:   {params['window_analise']}")
    print()
    print(f"  Última actualização: {params.get('actualizado_em', '?')}")
    print("═" * 65)


def menu():
    while True:
        params = carregar()
        mostrar(params)
        print()
        print("  Opções:")
        print("    1. Ajustar cashout de um padrão")
        print("    2. Ajustar fracção de aposta de um padrão")
        print("    3. Ajustar limiar de azuis (P2 ou P3)")
        print("    4. Ajustar limiar de rosas (P4)")
        print("    5. Repor valores default")
        print("    6. Editar ficheiro JSON à mão (mostra caminho)")
        print("    0. Sair")
        print()
        op = input("  Escolhe: ").strip()

        if op == "0":
            print("👋 Até à próxima!")
            break

        if op == "1":
            print("\n  Para qual padrão? (P2 / P3 / P3_jackpot / P4)")
            p = input("  > ").strip().upper()
            if p in ("P2", "P3", "P3_JACKPOT", "P4"):
                novo = input(f"  Novo cashout (actual {params.get(_map_cashout(p), '?')}): ").strip()
                try:
                    valor = float(novo)
                    if 1.0 < valor < 100.0:
                        params[_map_cashout(p)] = valor
                        gravar(params)
                        print(f"  ✅ Cashout de {p} alterado para {valor:.2f}x")
                    else:
                        print("  ⚠ Valor deve estar entre 1.01 e 99.99")
                except ValueError:
                    print("  ⚠ Valor inválido")
            else:
                print("  ⚠ Padrão desconhecido")
            input("\n  [Enter para continuar]")

        elif op == "2":
            print("\n  Para qual padrão? (P2 / P3_normal / P3_jackpot)")
            p = input("  > ").strip().lower()
            if p in ("p2", "p3_normal", "p3_jackpot"):
                key = _map_fracao(p)
                novo = input(f"  Nova fracção em % (actual {params[key]*100:.0f}%): ").strip()
                try:
                    valor = float(novo) / 100
                    if 0.05 < valor <= 1.0:
                        params[key] = valor
                        gravar(params)
                        print(f"  ✅ Fracção de {p} alterada para {valor*100:.0f}%")
                    else:
                        print("  ⚠ Fracção deve estar entre 5% e 100%")
                except ValueError:
                    print("  ⚠ Valor inválido")
            input("\n  [Enter para continuar]")

        elif op == "3":
            print("\n  P2 (regressão) ou P3 (combo)?")
            p = input("  > ").strip().upper()
            if p == "P2":
                novo = input(f"  Novo mínimo de azuis P2 (actual {params['P2_min_azuis']}): ").strip()
                try:
                    valor = int(novo)
                    if 3 <= valor <= 15:
                        params["P2_min_azuis"] = valor
                        gravar(params)
                        print(f"  ✅ Mínimo de azuis P2 alterado para {valor}")
                    else:
                        print("  ⚠ Valor deve estar entre 3 e 15")
                except ValueError:
                    print("  ⚠ Valor inválido")
            elif p == "P3":
                novo = input(f"  Novo mínimo combo (actual {params['P3_min_azuis_combo']}): ").strip()
                try:
                    valor = int(novo)
                    if 3 <= valor <= 15:
                        params["P3_min_azuis_combo"] = valor
                        gravar(params)
                        print(f"  ✅ Mínimo de azuis P3 alterado para {valor}")
                except ValueError:
                    print("  ⚠ Valor inválido")
            input("\n  [Enter para continuar]")

        elif op == "4":
            novo = input(f"  Novo mínimo de rosas em 10 (actual {params['P4_min_rosas']}): ").strip()
            try:
                valor = int(novo)
                if 1 <= valor <= 8:
                    params["P4_min_rosas"] = valor
                    gravar(params)
                    print(f"  ✅ Mínimo de rosas P4 alterado para {valor}")
                else:
                    print("  ⚠ Valor deve estar entre 1 e 8")
            except ValueError:
                print("  ⚠ Valor inválido")
            input("\n  [Enter para continuar]")

        elif op == "5":
            conf = input("  Tens a certeza? Vai reverter tudo. (s/n): ").strip().lower()
            if conf == "s":
                gravar(DEFAULTS.copy())
                print("  ✅ Valores repostos para defaults.")
            input("\n  [Enter para continuar]")

        elif op == "6":
            print(f"\n  📁 Ficheiro: {CAMINHO_PARAMS.absolute()}")
            print("     Abre num editor de texto (Notepad++, VS Code, etc.)")
            print("     Atenção: usa formato JSON válido!")
            input("\n  [Enter para continuar]")

        else:
            print("  ⚠ Opção inválida")
            input("\n  [Enter para continuar]")


def _map_cashout(p: str) -> str:
    return {
        "P2":          "P2_cashout",
        "P3":          "P3_cashout_normal",
        "P3_JACKPOT":  "P3_cashout_jackpot",
        "P4":          "P4_cashout",
    }.get(p.upper(), "")


def _map_fracao(p: str) -> str:
    return {
        "p2":          "P2_fracao",
        "p3_normal":   "P3_fracao_normal",
        "p3_jackpot":  "P3_fracao_jackpot",
    }.get(p.lower(), "")


if __name__ == "__main__":
    menu()
