# gestor/gestor_aposta.py
"""
Gestor de Aposta Composta — Estratégia 2 do PDF.

REGRAS:
  - Aposta base: 50 AOA (configurável)
  - Após VITÓRIA: próxima aposta = ganho da anterior (composição)
  - Após PERDA: reset para valor base
  - Após N vitórias seguidas: RESET para guardar o lucro no cofre
  - Limite máximo de aposta: nunca passa de X AOA

CONCILIAÇÃO COM ESTRATÉGIA 1 (padrões):
  - Padrão agressivo detectado (cashout >2x) → usa valor BASE (não arrisca a cadeia)
  - Padrão normal (cashout ≤2x, ex: 1.20x) → usa o valor da cadeia composta
"""
import json
from pathlib import Path
from typing import Tuple
from config.configuracoes import carregar_config

_ESTADO_PATH = Path("data/estado_aposta_composta.json")


def _carregar_estado() -> dict:
    cfg = carregar_config()

    # Valores que vêm SEMPRE do config (são CONFIGURAÇÕES, não estado):
    base_config       = float(cfg.get("aposta_base", 50.0))
    limite_config     = float(cfg.get("aposta_limite_max", 500.0))
    reset_config      = int(cfg.get("reset_apos_vitorias", 6))

    default = {
        "valor_atual":         base_config,
        "valor_base":          base_config,
        "limite_max":          limite_config,
        "reset_apos_vitorias": reset_config,
        "vitorias_seguidas":   0,
        "lucro_cofre":         0.0,
    }

    if _ESTADO_PATH.exists():
        try:
            with open(_ESTADO_PATH) as f:
                dados = json.load(f)
                # Só restauramos o ESTADO DINÂMICO do ficheiro.
                # As CONFIGURAÇÕES (valor_base, limite_max, reset) vêm
                # SEMPRE do config — senão mudanças na GUI não fazem efeito.
                for chave_dinamica in ("valor_atual", "vitorias_seguidas", "lucro_cofre"):
                    if chave_dinamica in dados:
                        default[chave_dinamica] = dados[chave_dinamica]

                # Se o valor_base do config mudou, o valor_atual da cadeia
                # antiga pode estar "preso" no valor antigo. Se a cadeia
                # está no início (0 vitórias), alinha valor_atual ao novo base.
                if default["vitorias_seguidas"] == 0:
                    default["valor_atual"] = base_config

                # Segurança: valor_atual nunca abaixo do base nem acima do limite
                if default["valor_atual"] < base_config:
                    default["valor_atual"] = base_config
                if default["valor_atual"] > limite_config:
                    default["valor_atual"] = limite_config
        except Exception:
            pass
    return default


def _salvar_estado(estado: dict):
    _ESTADO_PATH.parent.mkdir(exist_ok=True)
    with open(_ESTADO_PATH, "w") as f:
        json.dump(estado, f, indent=2)


def calcular_valor_aposta(cashout_alvo: float) -> Tuple[float, str]:
    """
    Decide o valor da próxima aposta baseado em:
      - Estado da cadeia composta (vitórias seguidas)
      - Cashout escolhido pela Estratégia 1

    Retorna (valor_aposta, descricao_decisao).
    """
    estado = _carregar_estado()

    # ── Padrão agressivo da Estratégia 1: NÃO arrisca a cadeia ──────────
    # Para cashouts >2x usa só o valor base — alvos altos têm taxa de
    # acerto baixa e não devem destruir a cadeia composta.
    if cashout_alvo > 2.0:
        valor = estado["valor_base"]
        desc  = f"Padrão agressivo (cashout {cashout_alvo:.1f}x) → aposta base {valor:.0f} AOA"
        return valor, desc

    # ── Padrão normal: usa o valor da cadeia composta ───────────────────
    valor = estado["valor_atual"]

    # Aplica limite máximo
    if valor > estado["limite_max"]:
        valor = estado["limite_max"]
        desc = f"Cadeia composta: {valor:.0f} AOA (limite atingido) | {estado['vitorias_seguidas']} vitórias"
    else:
        desc = f"Cadeia composta: {valor:.0f} AOA | {estado['vitorias_seguidas']} vitórias seguidas"

    return valor, desc


def registar_resultado_composta(
    sucesso: bool,
    valor_apostado: float,
    cashout_obtido: float = 0.0
) -> dict:
    """
    Actualiza o estado da cadeia após uma aposta.
    Retorna o estado actualizado para logging.
    """
    estado = _carregar_estado()

    if sucesso:
        ganho = valor_apostado * cashout_obtido
        lucro = ganho - valor_apostado

        estado["vitorias_seguidas"] += 1

        # ── Reset após N vitórias → guarda lucro no cofre ────────────────
        if estado["vitorias_seguidas"] >= estado["reset_apos_vitorias"]:
            # Calcula quanto a cadeia rendeu (do base até agora)
            estado["lucro_cofre"] += lucro
            estado["valor_atual"]  = estado["valor_base"]
            print(f"🏦 COFRE: cadeia completa de {estado['vitorias_seguidas']} vitórias")
            print(f"        Lucro guardado: +{lucro:.0f} AOA | Cofre total: {estado['lucro_cofre']:.0f}")
            print(f"        A reiniciar cadeia com {estado['valor_base']:.0f} AOA")
            estado["vitorias_seguidas"] = 0
        else:
            # Próxima aposta = ganho actual (composição)
            estado["valor_atual"] = ganho
            print(f"📈 Vitória {estado['vitorias_seguidas']}/{estado['reset_apos_vitorias']} | Próxima aposta: {ganho:.0f} AOA")

    else:
        # ── Perda: cadeia quebrada, reset para base ──────────────────────
        if estado["vitorias_seguidas"] > 0:
            print(f"💔 Cadeia quebrada após {estado['vitorias_seguidas']} vitórias")
        estado["vitorias_seguidas"] = 0
        estado["valor_atual"]       = estado["valor_base"]
        print(f"🔄 Reset para aposta base: {estado['valor_base']:.0f} AOA")

    _salvar_estado(estado)
    return estado


def info_estado() -> str:
    """Retorna info formatada do estado actual para logs."""
    e = _carregar_estado()
    return (f"Cadeia: {e['vitorias_seguidas']}/{e['reset_apos_vitorias']} | "
            f"Aposta: {e['valor_atual']:.0f} | "
            f"Cofre: {e['lucro_cofre']:.0f} AOA")


def reset_cadeia():
    """Força reset completo da cadeia (uso manual ou em ferramentas)."""
    estado = _carregar_estado()
    estado["vitorias_seguidas"] = 0
    estado["valor_atual"]       = estado["valor_base"]
    _salvar_estado(estado)
    print("🔄 Cadeia composta reiniciada manualmente")
