# estrategia/estrategia_padroes.py
"""
Estratégia "Follow Patterns" — lê o contexto recente e adapta-se.

VERSAO ACTUALIZADA (02/06/2026):
  - Aceita o novo formato de parametros_padroes.json (aninhado por padrão)
  - Suporta toggles ativo/inativo por padrão (vindos da GUI)
  - P5 e P6 cashouts agora editáveis (antes hardcoded a 1.20)
  - P1 limiar_mega agora editável (antes hardcoded a 100)

PADRÕES DETECTADOS:
  P1. Pós-mega: último crash >= limiar_mega → NÃO APOSTAR
  P2. Azuis seguidos: 6+ azuis em sequência → cashout 2.0x (regressão)
  P3. Combo quente: minuto quente + azuis → cashout 3-5x (jackpot)
  P4. Hot streak: 2+ rosas em últimos 10 → cashout 1.50x (confiante)
  P5. Rosa queimada: último >= 5x → cashout 1.50x (cuidado)
  P6. Default: 1.50x — a máquina de ganhar

CONFIANÇA E VALOR DA APOSTA:
  - Padrões usa_cadeia_composta=True: cadeia normal
  - Padrões especulativos (P2, P3): fracção da base, SEM cadeia
  - Mínimo: 65 AOA (limite do jogo)
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List
from dataclasses import dataclass

from utils.logs import log


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO — formato aninhado (compatível com GUI)
# ═══════════════════════════════════════════════════════════════════════════

CAMINHO_PARAMS = Path("config/parametros_padroes.json")

# Defaults aninhados (mesmo formato que a GUI escreve)
_PARAMS_DEFAULT = {
    "p1_pos_mega": {
        "ativo":       True,
        "limiar_mega": 100.0,
        "rounds_skip": 3,
    },
    "p2_seis_azuis": {
        "ativo":              True,
        "min_azuis_seguidos": 6,
        "cashout_alvo":       2.0,
        "fraccao_banca":      0.5,
    },
    "p3_combo_quente": {
        "ativo":                  True,
        "min_azuis_recentes":     5,
        "cashout_alvo_normal":    3.0,
        "cashout_alvo_jackpot":   5.0,
        "minuto_jackpot":         49,
        "fraccao_banca_normal":   0.3,
        "fraccao_banca_jackpot":  0.2,
    },
    "p4_hot_streak": {
        "ativo":           True,
        "min_rosas_em_10": 2,
        "cashout_alvo":    1.5,
    },
    "p5_rosa_queimada": {
        "ativo":                True,
        "limiar_rosa_queimada": 5.0,
        "cashout_alvo":         1.5,
    },
    "p6_default": {
        "ativo":        True,
        "cashout_alvo": 1.5,
    },
    # Parametros globais
    "_global": {
        "window_analise": 10,
    },
}


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Merge profundo. Se chave existe em ambos e ambos são dicts, recursa."""
    resultado = base.copy()
    for k, v in overrides.items():
        if k in resultado and isinstance(resultado[k], dict) and isinstance(v, dict):
            resultado[k] = _deep_merge(resultado[k], v)
        else:
            resultado[k] = v
    return resultado


def _carregar_params() -> dict:
    """
    Carrega parâmetros do JSON. Usa defaults se faltar.
    Aceita formato aninhado (novo) E formato flat (antigo, para retrocompatibilidade).
    """
    import copy
    params = copy.deepcopy(_PARAMS_DEFAULT)

    if not CAMINHO_PARAMS.exists():
        return params

    try:
        with open(CAMINHO_PARAMS, "r", encoding="utf-8") as f:
            user = json.load(f)
    except Exception as e:
        log(f"⚠️ Erro a carregar parametros_padroes.json: {e}", "warning")
        return params

    # Detecta formato: se primeira chave for um dict, é aninhado (novo)
    is_aninhado = any(isinstance(v, dict) for v in user.values())

    if is_aninhado:
        # Formato novo — merge directo
        params = _deep_merge(params, user)
    else:
        # Formato antigo (flat) — mapeamento para retrocompatibilidade
        legacy_map = {
            "P2_min_azuis":            ("p2_seis_azuis",   "min_azuis_seguidos"),
            "P2_cashout":              ("p2_seis_azuis",   "cashout_alvo"),
            "P2_fracao":               ("p2_seis_azuis",   "fraccao_banca"),
            "P3_min_azuis_combo":      ("p3_combo_quente", "min_azuis_recentes"),
            "P3_cashout_normal":       ("p3_combo_quente", "cashout_alvo_normal"),
            "P3_cashout_jackpot":      ("p3_combo_quente", "cashout_alvo_jackpot"),
            "P3_fracao_normal":        ("p3_combo_quente", "fraccao_banca_normal"),
            "P3_fracao_jackpot":       ("p3_combo_quente", "fraccao_banca_jackpot"),
            "P4_min_rosas":            ("p4_hot_streak",   "min_rosas_em_10"),
            "P4_cashout":              ("p4_hot_streak",   "cashout_alvo"),
            "P5_limiar_rosa_queimada": ("p5_rosa_queimada","limiar_rosa_queimada"),
            "window_pos_mega":         ("p1_pos_mega",     "rounds_skip"),
            "window_analise":          ("_global",         "window_analise"),
        }
        for old_key, (padrao, campo) in legacy_map.items():
            if old_key in user:
                params[padrao][campo] = user[old_key]

    return params


# Minutos quentes (vindos dos dados reais) — só usados para combos P3
MINUTOS_QUENTES = {
    2:  55.6,   # max 71x
    31: 45.8,   # max 71x
    45: 44.4,   # max 291x
    49: 40.0,   # max 1315x — ⚡ jackpot potencial
    26: 35.3,   # max 573x
    54: 33.3,
    17: 30.0,
    36: 28.6,
    12: 28.6,
    52: 27.8,
    23: 27.8,
    58: 27.3,
}

# Constantes fixas (limites técnicos do jogo)
LIMIAR_AZUL     = 2.0
LIMIAR_ROSA     = 10.0
APOSTA_MIN_JOGO = 65

# Estado persistente
CAMINHO_ESTADO = Path("data/estado_estrategia_padroes.json")
CAMINHO_HISTORICO_INICIAL = Path("data/historico_inicial.json")


# ═══════════════════════════════════════════════════════════════════════════
# TEMPERATURA DA SESSAO (IA Adaptativa v2)
# ═══════════════════════════════════════════════════════════════════════════

# Cache da temperatura (carregada uma vez por sessao)
_temperatura_cache: Optional[dict] = None
_temperatura_carregada: bool = False


def _carregar_temperatura() -> Optional[dict]:
    """Carrega estatisticas do historico capturado (uma vez por sessao)."""
    global _temperatura_cache, _temperatura_carregada
    if _temperatura_carregada:
        return _temperatura_cache

    _temperatura_carregada = True
    if not CAMINHO_HISTORICO_INICIAL.exists():
        return None
    try:
        with open(CAMINHO_HISTORICO_INICIAL, "r", encoding="utf-8") as f:
            hist = json.load(f)
        _temperatura_cache = hist.get("estatisticas")
        return _temperatura_cache
    except Exception:
        return None


def resetar_temperatura() -> None:
    """Forca recarregar temperatura na proxima chamada (uso: reinicio de sessao)."""
    global _temperatura_cache, _temperatura_carregada
    _temperatura_cache = None
    _temperatura_carregada = False


CAMINHO_TEMPERATURA_ATUAL = Path("data/temperatura_atual.json")


def recalcular_temperatura_dinamica(crashes_recentes: list,
                                       min_amostra: int = 20) -> Optional[dict]:
    """
    Recalcula a temperatura a partir dos crashes recentes da sessao (janela viva).

    Esta e' a TEMPERATURA DINAMICA — substitui a temperatura estatica do
    historico inicial assim que houver amostra suficiente da propria sessao.

    Args:
        crashes_recentes: lista da janela viva (mais recente primeiro)
        min_amostra: minimo de crashes para recalcular (default 20)

    Returns:
        dict de estatisticas, ou None se amostra insuficiente.
        Tambem grava em data/temperatura_atual.json para a GUI ler.
    """
    global _temperatura_cache

    if not crashes_recentes or len(crashes_recentes) < min_amostra:
        return None

    # Usa ate 80 crashes mais recentes
    amostra = crashes_recentes[:80]
    n = len(amostra)

    azuis = sum(1 for c in amostra if c < 2.0)
    rosas = sum(1 for c in amostra if c >= 10.0)
    megas = sum(1 for c in amostra if c >= 100.0)
    pct_rosas = rosas / n * 100

    ordenados = sorted(amostra)
    mediana = ordenados[n // 2]
    q50 = ordenados[int(n * 0.50)]
    q67 = ordenados[int(n * 0.67)]
    q75 = ordenados[int(n * 0.75)]

    if pct_rosas < 6.0:
        cls = "fria"
    elif pct_rosas > 13.0:
        cls = "quente"
    else:
        cls = "normal"

    stats = {
        "total": n,
        "azuis": azuis,
        "rosas": rosas,
        "megas": megas,
        "pct_azuis": azuis / n * 100,
        "pct_rosas": pct_rosas,
        "pct_megas": megas / n * 100,
        "crash_mediano": mediana,
        "quantil_50": q50,
        "quantil_67": q67,
        "quantil_75": q75,
        "max_visto": max(amostra),
        "classificacao": cls,
        "fonte": "dinamica",   # marca que veio da sessao, nao do historico inicial
    }

    # Actualiza cache interno (para os padroes usarem)
    _temperatura_cache = stats

    # Grava para a GUI ler em tempo real
    try:
        CAMINHO_TEMPERATURA_ATUAL.parent.mkdir(parents=True, exist_ok=True)
        with open(CAMINHO_TEMPERATURA_ATUAL, "w", encoding="utf-8") as f:
            json.dump({
                "estatisticas": stats,
                "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            }, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return stats


def _cashout_adaptativo(padrao_default: float, modo: str) -> Tuple[float, str]:
    """
    Calcula cashout adaptado a' temperatura da sessao.

    Args:
        padrao_default: cashout do JSON para esse padrao
        modo: 'agressivo' (P4) | 'cauteloso' (P5) | 'normal' (P6)

    Returns:
        (cashout, sufixo_motivo)
        Se nao houver temperatura disponivel, retorna (padrao_default, "")
    """
    temp = _carregar_temperatura()
    if not temp:
        return padrao_default, ""

    q67 = temp.get("quantil_67", padrao_default)
    q50 = temp.get("quantil_50", padrao_default)
    cls = temp.get("classificacao", "normal")

    if modo == "agressivo":   # P4 hot streak — pode subir um pouco
        cashout = max(padrao_default, q67)
        cashout = min(cashout, 2.0)
    elif modo == "cauteloso": # P5 rosa queimada — sempre baixo
        cashout = min(padrao_default, max(q50, 1.20))
    else:                      # P6 default — adapta directo a' classificacao
        if cls == "fria":
            cashout = min(padrao_default, max(q50, 1.20))
        elif cls == "quente":
            cashout = max(padrao_default, min(q67, 2.0))
        else:  # normal
            cashout = max(1.30, min(q67, 1.70))

    # Arredondar a 2 casas
    cashout = round(cashout, 2)
    emoji_cls = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}.get(cls, "🟡")
    motivo = f" [IA: {emoji_cls} q67={q67:.2f} → {cashout:.2f}x]"
    return cashout, motivo


# ═══════════════════════════════════════════════════════════════════════════
# RESULTADO DA DECISÃO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DecisaoPadrao:
    """Resultado da análise de padrões."""
    deve_apostar:        bool
    cashout_alvo:        float
    fracao_aposta:       float    # multiplica a aposta base ou cadeia
    usa_cadeia_composta: bool     # True só nos casos default 1.20-1.50x
    nome_padrao:         str
    motivo:              str
    minuto:              int = -1
    contagem_azuis:      int = 0
    contagem_rosas:      int = 0


# ═══════════════════════════════════════════════════════════════════════════
# ANÁLISE DOS CRASHES RECENTES
# ═══════════════════════════════════════════════════════════════════════════

def _contar_azuis_seguidos(crashes: List[float]) -> int:
    """Conta quantos crashes <2x estão SEGUIDOS desde o início (mais recente)."""
    contagem = 0
    for c in crashes:
        if c < LIMIAR_AZUL:
            contagem += 1
        else:
            break
    return contagem


def _contar_rosas(crashes: List[float], janela: int = 10) -> int:
    """Conta crashes >=10x nos últimos N."""
    return sum(1 for c in crashes[:janela] if c >= LIMIAR_ROSA)


def _houve_mega_recente(crashes: List[float], janela: int, limiar: float) -> bool:
    """Houve um mega (>=limiar) nos últimos N crashes?"""
    return any(c >= limiar for c in crashes[:janela])


def _minuto_e_quente(minuto: int) -> Optional[float]:
    """Retorna a % de rosas esperada se for minuto quente, senão None."""
    return MINUTOS_QUENTES.get(minuto)


# ═══════════════════════════════════════════════════════════════════════════
# DECISÃO PRINCIPAL — agora respeita "ativo" de cada padrão
# ═══════════════════════════════════════════════════════════════════════════

def decidir_padrao(crashes_recentes: List[float]) -> DecisaoPadrao:
    """
    Analisa os crashes recentes e decide qual padrão se aplica.

    Args:
        crashes_recentes: lista de crashes, MAIS RECENTE PRIMEIRO

    Returns:
        DecisaoPadrao com tudo necessário para o bot agir
    """
    p = _carregar_params()
    p1 = p["p1_pos_mega"]
    p2 = p["p2_seis_azuis"]
    p3 = p["p3_combo_quente"]
    p4 = p["p4_hot_streak"]
    p5 = p["p5_rosa_queimada"]
    p6 = p["p6_default"]
    glob = p.get("_global", {"window_analise": 10})

    minuto = datetime.now().minute

    # Sem histórico → P6 default
    if not crashes_recentes or len(crashes_recentes) < 3:
        return _decisao_p6_default(p6, minuto, 0, 0,
                                      motivo_extra=f"Histórico insuficiente ({len(crashes_recentes)})")

    ultimo = crashes_recentes[0]
    azuis_seguidos = _contar_azuis_seguidos(crashes_recentes)
    rosas_recentes = _contar_rosas(crashes_recentes, glob["window_analise"])
    pct_quente = _minuto_e_quente(minuto)

    # ═════════════════════════════════════════════════════════════════
    # P1. Pós-mega: NÃO APOSTAR (se ativo)
    # ═════════════════════════════════════════════════════════════════
    if p1.get("ativo", True):
        if _houve_mega_recente(crashes_recentes, p1["rounds_skip"], p1["limiar_mega"]):
            mega_valor = next((c for c in crashes_recentes[:p1["rounds_skip"]] if c >= p1["limiar_mega"]), 0)
            return DecisaoPadrao(
                deve_apostar=False,
                cashout_alvo=0.0,
                fracao_aposta=0.0,
                usa_cadeia_composta=False,
                nome_padrao="P1_pos_mega",
                motivo=f"❄️ P1 Pós-mega ({mega_valor:.0f}x recente) — skip (cold expectado)",
                minuto=minuto,
                contagem_azuis=azuis_seguidos,
                contagem_rosas=rosas_recentes,
            )

    # ═════════════════════════════════════════════════════════════════
    # P3. COMBO: minuto quente + azuis seguidos = JACKPOT POTENCIAL
    # ═════════════════════════════════════════════════════════════════
    if p3.get("ativo", True):
        if pct_quente is not None and azuis_seguidos >= p3["min_azuis_recentes"]:
            if minuto == p3.get("minuto_jackpot", 49):
                return DecisaoPadrao(
                    deve_apostar=True,
                    cashout_alvo=p3["cashout_alvo_jackpot"],
                    fracao_aposta=p3["fraccao_banca_jackpot"],
                    usa_cadeia_composta=False,
                    nome_padrao="P3_combo_jackpot",
                    motivo=(f"🎯 P3 COMBO JACKPOT: min {minuto} + {azuis_seguidos} azuis "
                            f"→ {p3['cashout_alvo_jackpot']:.1f}x ({int(p3['fraccao_banca_jackpot']*100)}% banca)"),
                    minuto=minuto,
                    contagem_azuis=azuis_seguidos,
                    contagem_rosas=rosas_recentes,
                )
            return DecisaoPadrao(
                deve_apostar=True,
                cashout_alvo=p3["cashout_alvo_normal"],
                fracao_aposta=p3["fraccao_banca_normal"],
                usa_cadeia_composta=False,
                nome_padrao="P3_combo",
                motivo=(f"🎯 P3 COMBO: min {minuto:02d} ({pct_quente:.0f}% rosa) + "
                        f"{azuis_seguidos} azuis → {p3['cashout_alvo_normal']:.1f}x "
                        f"({int(p3['fraccao_banca_normal']*100)}% banca)"),
                minuto=minuto,
                contagem_azuis=azuis_seguidos,
                contagem_rosas=rosas_recentes,
            )

    # ═════════════════════════════════════════════════════════════════
    # P2. Regressão: muitos azuis seguidos (sem combo)
    # ═════════════════════════════════════════════════════════════════
    if p2.get("ativo", True):
        if azuis_seguidos >= p2["min_azuis_seguidos"]:
            return DecisaoPadrao(
                deve_apostar=True,
                cashout_alvo=p2["cashout_alvo"],
                fracao_aposta=p2["fraccao_banca"],
                usa_cadeia_composta=False,
                nome_padrao="P2_regressao",
                motivo=(f"📈 P2 Regressão: {azuis_seguidos} azuis seguidos "
                        f"→ {p2['cashout_alvo']:.1f}x ({int(p2['fraccao_banca']*100)}% banca)"),
                minuto=minuto,
                contagem_azuis=azuis_seguidos,
                contagem_rosas=rosas_recentes,
            )

    # ═════════════════════════════════════════════════════════════════
    # P4. Hot streak: várias rosas recentes
    # ═════════════════════════════════════════════════════════════════
    if p4.get("ativo", True):
        if rosas_recentes >= p4["min_rosas_em_10"]:
            cashout_p4, sufixo_ia = _cashout_adaptativo(p4["cashout_alvo"], "agressivo")
            return DecisaoPadrao(
                deve_apostar=True,
                cashout_alvo=cashout_p4,
                fracao_aposta=1.0,
                usa_cadeia_composta=True,
                nome_padrao="P4_hot_streak",
                motivo=(f"🔥 P4 Hot streak: {rosas_recentes} rosas em {glob['window_analise']} "
                        f"→ {cashout_p4:.2f}x{sufixo_ia}"),
                minuto=minuto,
                contagem_azuis=azuis_seguidos,
                contagem_rosas=rosas_recentes,
            )

    # ═════════════════════════════════════════════════════════════════
    # P5. Rosa queimada: último crash >= limiar
    # ═════════════════════════════════════════════════════════════════
    if p5.get("ativo", True):
        if ultimo >= p5["limiar_rosa_queimada"]:
            cashout_p5, sufixo_ia = _cashout_adaptativo(p5["cashout_alvo"], "cauteloso")
            return DecisaoPadrao(
                deve_apostar=True,
                cashout_alvo=cashout_p5,
                fracao_aposta=1.0,
                usa_cadeia_composta=True,
                nome_padrao="P5_rosa_queimada",
                motivo=f"💨 P5 Rosa queimada ({ultimo:.1f}x) — cauteloso {cashout_p5:.2f}x{sufixo_ia}",
                minuto=minuto,
                contagem_azuis=azuis_seguidos,
                contagem_rosas=rosas_recentes,
            )

    # ═════════════════════════════════════════════════════════════════
    # P6. Default — a "máquina"
    # ═════════════════════════════════════════════════════════════════
    return _decisao_p6_default(p6, minuto, azuis_seguidos, rosas_recentes,
                                 ultimo=ultimo)


def _decisao_p6_default(p6: dict, minuto: int, azuis: int, rosas: int,
                          ultimo: float = 0.0, motivo_extra: str = "") -> DecisaoPadrao:
    """Helper para criar a decisão P6 default."""
    if not p6.get("ativo", True):
        return DecisaoPadrao(
            deve_apostar=False,
            cashout_alvo=0.0,
            fracao_aposta=0.0,
            usa_cadeia_composta=False,
            nome_padrao="P6_default_inactivo",
            motivo="⏸️ P6 default DESACTIVADO no config — skip",
            minuto=minuto,
            contagem_azuis=azuis,
            contagem_rosas=rosas,
        )

    cashout, sufixo_ia = _cashout_adaptativo(p6["cashout_alvo"], "normal")
    if motivo_extra:
        motivo = f"✅ P6 Default {cashout:.2f}x ({motivo_extra}){sufixo_ia}"
    else:
        motivo = f"✅ P6 Default {cashout:.2f}x (último {ultimo:.2f}x, {azuis} azuis){sufixo_ia}"

    return DecisaoPadrao(
        deve_apostar=True,
        cashout_alvo=cashout,
        fracao_aposta=1.0,
        usa_cadeia_composta=True,
        nome_padrao="P6_default",
        motivo=motivo,
        minuto=minuto,
        contagem_azuis=azuis,
        contagem_rosas=rosas,
    )


# ═══════════════════════════════════════════════════════════════════════════
# INTERFACE PÚBLICA (inalterada — compatível com core.py existente)
# ═══════════════════════════════════════════════════════════════════════════

def aplicar_estrategia_padroes(historico_mults: list, config: dict) -> Tuple[bool, float]:
    """
    Aplica a estratégia de padrões.

    Compatível com core.py: retorna (deve_apostar, cashout_alvo).
    """
    decisao = decidir_padrao(historico_mults)
    _guardar_ultima_decisao(decisao)
    log(decisao.motivo)
    return decisao.deve_apostar, decisao.cashout_alvo


# Cache da última decisão (para o core acessar a info extra)
_ultima_decisao: Optional[DecisaoPadrao] = None


def _guardar_ultima_decisao(d: DecisaoPadrao) -> None:
    global _ultima_decisao
    _ultima_decisao = d


def obter_ultima_decisao() -> Optional[DecisaoPadrao]:
    """Retorna a última decisão tomada."""
    return _ultima_decisao


def calcular_valor_aposta_padroes(
    aposta_base: float,
    valor_cadeia: float,
) -> Tuple[float, str]:
    """Calcula valor da aposta segundo a última decisão."""
    d = obter_ultima_decisao()
    if d is None:
        return valor_cadeia, ""

    if d.usa_cadeia_composta:
        return valor_cadeia, ""

    # Padrões especulativos
    valor_calculado = aposta_base * d.fracao_aposta
    valor_final = max(APOSTA_MIN_JOGO, valor_calculado)
    return valor_final, (
        f"💼 Aposta especulativa ({d.nome_padrao}): "
        f"{valor_cadeia:.0f}→{valor_final:.0f} AOA "
        f"({int(d.fracao_aposta*100)}% da base)"
    )


# ═══════════════════════════════════════════════════════════════════════════
# REGISTO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════

def _carregar_estado() -> dict:
    if not CAMINHO_ESTADO.exists():
        return {"padroes": {}, "total_apostas": 0,
                "criado_em": datetime.now().isoformat()}
    try:
        with open(CAMINHO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"padroes": {}, "total_apostas": 0,
                "criado_em": datetime.now().isoformat()}


def _gravar_estado(estado: dict) -> None:
    try:
        CAMINHO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
        with open(CAMINHO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"⚠️ Erro a gravar estado padroes: {e}", "warning")


def registar_resultado_padrao(ganhou: bool, lucro_aposta: float) -> None:
    """Regista o resultado da última aposta no padrão correspondente."""
    d = obter_ultima_decisao()
    if d is None:
        return

    estado = _carregar_estado()
    estado["total_apostas"] += 1

    chave = d.nome_padrao
    if chave not in estado["padroes"]:
        estado["padroes"][chave] = {"wins": 0, "losses": 0, "lucro": 0.0}

    if ganhou:
        estado["padroes"][chave]["wins"] += 1
    else:
        estado["padroes"][chave]["losses"] += 1
    estado["padroes"][chave]["lucro"] += lucro_aposta

    _gravar_estado(estado)


def esta_activa(config: dict) -> bool:
    """Retorna True se esta estratégia está activa no config."""
    return config.get("usar_estrategia_padroes", False)


def relatorio_padroes() -> str:
    """Gera relatório legível do desempenho de cada padrão."""
    estado = _carregar_estado()
    linhas = []
    linhas.append("📊 RELATÓRIO — Estratégia Follow Patterns")
    linhas.append("═" * 70)
    linhas.append(f"  Total de apostas: {estado.get('total_apostas', 0)}")
    linhas.append("")
    linhas.append("  Padrões e desempenho:")
    linhas.append("  ─" * 35)

    padroes = estado.get("padroes", {})
    if not padroes:
        linhas.append("    (sem dados ainda)")
    else:
        for nome in sorted(padroes.keys()):
            dados = padroes[nome]
            w = dados["wins"]; l = dados["losses"]; lc = dados["lucro"]
            total = w + l
            wr = (w / total * 100) if total else 0
            sinal = "+" if lc >= 0 else ""
            linhas.append(
                f"    {nome:25s}: {w:3d}W/{l:3d}L ({wr:5.1f}%) | "
                f"{sinal}{lc:.0f} AOA"
            )

    linhas.append("═" * 70)
    return "\n".join(linhas)
