# gestor/banca.py
"""
Gestao da banca - com SISTEMA DE MISSAO.

Conceito:
  - banca_inicial   = quanto tens para arriscar     (ex: 10000 AOA)
  - objectivo_pct   = quanto queres lucrar em %     (ex: 100% = duplicar)
  - stop_loss_pct   = perda maxima aceitavel em %   (ex: 30% da banca)

Para quando:
  - lucro LIQUIDO >= banca_inicial * objectivo_pct/100   -> objectivo
  - lucro LIQUIDO <= -banca_inicial * stop_loss_pct/100  -> stop loss

Bug 6 fix: carregar_estado() reseta se ficheiro nao existe.
"""
import json
import os
from datetime import datetime
from typing import Tuple
from config.configuracoes import carregar_config

CAMINHO_ESTADO = "data/estado_banca.json"
CAMINHO_CSV    = "data/historico.csv"

estado: dict = {"ganhos": 0.0, "perdas": 0.0, "lucro": 0.0}


def _estado_default() -> dict:
    return {"ganhos": 0.0, "perdas": 0.0, "lucro": 0.0}


def carregar_estado() -> None:
    """Carrega do disco OU reseta se ficheiro nao existe."""
    global estado
    if os.path.exists(CAMINHO_ESTADO):
        try:
            with open(CAMINHO_ESTADO, "r", encoding="utf-8") as f:
                estado.clear()
                estado.update(json.load(f))
        except Exception as e:
            print(f"⚠️ Erro ao carregar estado da banca: {e}")
            estado.clear()
            estado.update(_estado_default())
    else:
        estado.clear()
        estado.update(_estado_default())


def salvar_estado() -> None:
    try:
        os.makedirs("data", exist_ok=True)
        with open(CAMINHO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=4)
    except Exception as e:
        print(f"⚠️ Erro ao salvar estado da banca: {e}")


carregar_estado()


# ===================================================================
# SISTEMA DE MISSAO
# ===================================================================

def info_missao() -> dict:
    """Retorna info completa sobre a missao actual."""
    config = carregar_config()

    banca_inicial = float(config.get("banca_inicial",
                                      config.get("saldo_inicial", 10000)))
    objectivo_pct = float(config.get("objectivo_pct", 100))
    stop_loss_pct = float(config.get("stop_loss_pct", 30))

    lucro_alvo = banca_inicial * (objectivo_pct / 100)
    perda_max  = banca_inicial * (stop_loss_pct / 100)

    lucro_actual = float(estado.get("lucro", 0.0))

    if lucro_alvo > 0:
        progresso_pct = (lucro_actual / lucro_alvo) * 100
    else:
        progresso_pct = 0

    dist_stop = perda_max + lucro_actual

    if lucro_actual >= lucro_alvo:
        estado_missao = "objectivo_atingido"
    elif lucro_actual <= -perda_max:
        estado_missao = "stop_loss_atingido"
    elif dist_stop < perda_max * 0.25:
        estado_missao = "zona_perigo"
    else:
        estado_missao = "em_rota"

    return {
        "banca_inicial": banca_inicial,
        "objectivo_pct": objectivo_pct,
        "stop_loss_pct": stop_loss_pct,
        "lucro_actual":  lucro_actual,
        "lucro_alvo":    lucro_alvo,
        "perda_max":     perda_max,
        "banca_actual":  banca_inicial + lucro_actual,
        "banca_alvo":    banca_inicial + lucro_alvo,
        "banca_stop":    banca_inicial - perda_max,
        "progresso_pct": progresso_pct,
        "dist_stop":     dist_stop,
        "estado_missao": estado_missao,
    }


_banner_objectivo_mostrado = False
_banner_stop_mostrado = False


def deve_continuar() -> bool:
    """Verifica se ainda deve continuar baseado na MISSAO."""
    global _banner_objectivo_mostrado, _banner_stop_mostrado
    missao = info_missao()
    estado_m = missao["estado_missao"]

    if estado_m == "objectivo_atingido":
        if not _banner_objectivo_mostrado:   # só imprime UMA vez
            print()
            print("🏆 ============================================")
            print(f"🏆  OBJECTIVO ATINGIDO!")
            print(f"🏆  Banca inicial:  {missao['banca_inicial']:.0f} AOA")
            print(f"🏆  Banca actual:   {missao['banca_actual']:.0f} AOA")
            print(f"🏆  Lucro:          +{missao['lucro_actual']:.0f} AOA "
                  f"({missao['progresso_pct']:.0f}% do alvo {missao['objectivo_pct']:.0f}%)")
            print("🏆 ============================================")
            print()
            _banner_objectivo_mostrado = True
        return False

    if estado_m == "stop_loss_atingido":
        if not _banner_stop_mostrado:   # só imprime UMA vez
            print()
            print("🛡️ ============================================")
            print(f"🛡️  STOP LOSS ATINGIDO!")
            print(f"🛡️  Banca inicial:  {missao['banca_inicial']:.0f} AOA")
            print(f"🛡️  Banca actual:   {missao['banca_actual']:.0f} AOA")
            print(f"🛡️  Perda:          {missao['lucro_actual']:.0f} AOA "
                  f"(limite -{missao['perda_max']:.0f} = -{missao['stop_loss_pct']:.0f}%)")
            print("🛡️ ============================================")
            print()
            _banner_stop_mostrado = True
        return False

    return True


def resetar_banners_missao() -> None:
    """Reset dos flags dos banners (chamar no arranque de cada sessao)."""
    global _banner_objectivo_mostrado, _banner_stop_mostrado
    _banner_objectivo_mostrado = False
    _banner_stop_mostrado = False


def info_estado_missao_curto() -> str:
    m = info_missao()
    return (f"🎯 {m['banca_actual']:.0f}/{m['banca_alvo']:.0f} AOA "
            f"({m['progresso_pct']:+.0f}%) | "
            f"Stop em -{m['perda_max']:.0f}")


# ===================================================================
# RESTANTES FUNCOES
# ===================================================================

def obter_saldo_banca() -> float:
    config        = carregar_config()
    banca_inicial = float(config.get("banca_inicial",
                                      config.get("saldo_inicial", 10000)))
    return banca_inicial + float(estado.get("lucro", 0.0))


def registrar_resultado(sucesso: bool, valor_apostado: float = None,
                          multiplicador_cashout: float = None) -> None:
    """
    Regista o resultado de uma aposta.

    CORRECCAO (Bug critico encontrado em 01/06/2026):
      - Antes: em caso de vitoria, somava-se a APOSTA inteira aos ganhos.
        Isto inflacionava o lucro porque a aposta nao e' o ganho liquido.
      - Agora: o ganho liquido = aposta * (multiplicador - 1).
        Exemplo: aposta 1000, cashout 1.22x -> recebes 1220, lucro liquido 220.

    Em caso de perda, perde-se a aposta inteira (sem alteracao).
    """
    config = carregar_config()
    valor  = (valor_apostado if valor_apostado is not None
                else float(config.get("valor_aposta", 10.0)))

    if sucesso:
        if multiplicador_cashout is None or multiplicador_cashout <= 1.0:
            print("⚠️ registrar_resultado: vitoria sem multiplicador valido. "
                  "A assumir 1.0 (sem lucro). Verifica a chamada!")
            ganho_liquido = 0.0
        else:
            ganho_liquido = valor * (float(multiplicador_cashout) - 1.0)

        estado["ganhos"] += ganho_liquido
        estado["lucro"]  += ganho_liquido
    else:
        estado["perdas"] += valor
        estado["lucro"]  -= valor

    salvar_estado()
    print(f"💳 Banca actualizada | Lucro: {estado['lucro']:.2f} | "
          f"Ganhos: {estado['ganhos']:.2f} | Perdas: {estado['perdas']:.2f}")


def registrar_resultado_csv(tipo: str, valor: float = None) -> None:
    try:
        os.makedirs("data", exist_ok=True)
        ts        = datetime.now().isoformat(timespec="seconds")
        valor_str = f"{valor:.2f}x" if valor is not None else ""
        with open(CAMINHO_CSV, "a", newline="", encoding="utf-8") as f:
            f.write(f"{ts},{tipo},{valor_str}\n")
    except Exception as e:
        print(f"⚠️ Erro ao registrar CSV: {e}")


def obter_resultados_dia() -> Tuple[float, float]:
    ganhos, perdas = 0.0, 0.0
    if not os.path.exists(CAMINHO_CSV):
        return ganhos, perdas
    hoje = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(CAMINHO_CSV, "r", encoding="utf-8") as f:
            for linha in f:
                if not linha.startswith(hoje):
                    continue
                partes = linha.strip().split(",")
                if len(partes) < 3:
                    continue
                tipo      = partes[1]
                valor_str = partes[2].replace("x", "")
                try:
                    v = float(valor_str)
                    if tipo == "cashout_ok":
                        ganhos += v
                    elif tipo == "crash_perdeu":
                        perdas += v
                except ValueError:
                    pass
    except Exception as e:
        print(f"⚠️ Erro ao ler resultados do dia: {e}")
    return ganhos, perdas


def resetar_banca() -> None:
    """Reseta o estado da banca em memoria E no disco."""
    estado.clear()
    estado.update(_estado_default())
    salvar_estado()
    print("🔄 Banca resetada.")
