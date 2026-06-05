# utils/regioes.py
from config.configuracoes import carregar_config


def carregar_regioes() -> dict:
    """
    Organiza as regiões calibradas a partir do config.json.
    Retorna dicionário com as áreas padronizadas.
    """
    config = carregar_config()
    mapa   = {
        "bet_button_region":  "area_apostar",
        "mult_region":        "regiao_multiplicador_voo",
        "cashout_region":     "area_cashout",
        "crash_list_region":  "regiao_lista_multiplicadores",
        "red_area_region":    "area_vermelho_final",
    }
    regioes  = {}
    ausentes = []
    for nome, chave in mapa.items():
        valor = config.get(chave)
        if not valor:
            ausentes.append(chave)
        else:
            regioes[nome] = valor

    if ausentes:
        print(f"⚠️ Regiões não configuradas: {ausentes}")
        print("   Execute os scripts da pasta calibrar/ para definir estas áreas.")

    return regioes
