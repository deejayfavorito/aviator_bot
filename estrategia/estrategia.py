# estrategia/estrategia.py
"""
Estratégia baseada no PDF — versão melhorada.

Mudança chave nesta versão: a PAUSA após N perdas tem um TEMPO/ROUNDS
de duração, não fica presa para sempre. Após 3 rounds em pausa, reseta
o contador e volta a tentar.
"""
import json
import datetime
from pathlib import Path
from typing import Tuple
from config.configuracoes import carregar_config

_ESTADO_PATH = Path("data/estado_estrategia.json")


def cor(v: float) -> str:
    if v < 2.0:   return "azul"
    if v <= 10.0: return "roxo"
    return "rosa"

def cores_lista(historico: list) -> list:
    return [cor(v) for v in historico]

def _consecutivos(cores: list, alvo: str) -> int:
    n = 0
    for c in cores:
        if c == alvo: n += 1
        else: break
    return n


def _carregar_estado() -> dict:
    default = {
        "consecutivas_perdas": 0,
        "consecutivas_ganhos": 0,
        "rounds_em_pausa":     0,
    }
    if _ESTADO_PATH.exists():
        try:
            with open(_ESTADO_PATH) as f:
                default.update(json.load(f))
        except Exception:
            pass
    return default


def _salvar_estado(estado: dict):
    _ESTADO_PATH.parent.mkdir(exist_ok=True)
    with open(_ESTADO_PATH, "w") as f:
        json.dump(estado, f, indent=2)


def registar_resultado(sucesso: bool):
    estado = _carregar_estado()
    if sucesso:
        estado["consecutivas_perdas"] = 0
        estado["consecutivas_ganhos"] += 1
        estado["rounds_em_pausa"]     = 0
    else:
        estado["consecutivas_ganhos"] = 0
        estado["consecutivas_perdas"] += 1
    _salvar_estado(estado)


def _janela_rosa() -> Tuple[bool, str]:
    m = datetime.datetime.now().minute
    for ini, fim in [(2,3),(8,9),(20,22),(28,30),(38,39),(41,41),(55,57)]:
        if ini <= m <= fim:
            return True, f"{ini:02d}-{fim:02d}min"
    return False, ""


def aplicar_estrategia(historico: list, config: dict) -> Tuple[bool, float]:
    if len(historico) < 6:
        return True, 1.20

    estado = _carregar_estado()
    max_perdas       = int(config.get("max_perdas_seguidas", 4))
    duracao_pausa    = int(config.get("duracao_pausa_rounds", 3))  # rounds em pausa

    # ─── PAUSA por perdas consecutivas ────────────────────────────────────
    if estado["consecutivas_perdas"] >= max_perdas:
        estado["rounds_em_pausa"] += 1

        if estado["rounds_em_pausa"] >= duracao_pausa:
            # Fim da pausa — reseta contador e volta a apostar
            print(f"▶️  Fim da pausa ({duracao_pausa} rounds) — a retomar apostas")
            estado["consecutivas_perdas"] = 0
            estado["rounds_em_pausa"]     = 0
            _salvar_estado(estado)
        else:
            print(f"⏸️  PAUSA: {estado['consecutivas_perdas']} perdas — round {estado['rounds_em_pausa']}/{duracao_pausa}")
            _salvar_estado(estado)
            return False, 0.0

    # ─── PAUSA por rodada má ──────────────────────────────────────────────
    recentes_baixos = sum(1 for v in historico[:5] if v < 1.50)
    if recentes_baixos >= 4:
        print(f"⏸️  PAUSA: rodada má ({recentes_baixos}/5 <1.50x)")
        return False, 0.0

    c         = cores_lista(historico)
    azuis_seg = _consecutivos(c, "azul")
    roxos_seg = _consecutivos(c, "roxo")

    # ─── Padrões fortes ──────────────────────────────────────────────────
    if roxos_seg >= 5:
        print(f"🌹 P2.3: {roxos_seg} roxos seguidos → cashout 20x")
        return True, 20.0

    if azuis_seg >= 6:
        print(f"🌹 P2.2: {azuis_seg} azuis seguidos → cashout 10x")
        return True, 10.0

    # ─── P2.1: alternância + 2 azuis ─────────────────────────────────────
    if len(c) >= 4 and c[0] == "azul" and c[1] == "azul":
        if c[2] in ("azul","roxo") and c[3] in ("azul","roxo"):
            if c[2] != c[3]:
                print(f"🌹 P2.1: 2 azuis após alternância → cashout 2x")
                return True, 2.0   # baixado de 3x para 2x (mais conservador)

    # ─── Janela de rosa SEM padrão ──────────────────────────────────────
    em_janela, desc = _janela_rosa()
    if em_janela:
        if any(v > 10.0 for v in historico[:15]):
            print(f"🕐 {desc}: rosa recente — base 1.20x")
            return True, 1.20
        print(f"🕐 {desc}: janela activa → cashout 2.00x")
        return True, 2.00

    # ─── Default: Estratégia 2 do PDF ────────────────────────────────────
    print(f"✅ Estratégia base: cashout 1.20x")
    return True, 1.20


def registrar_resultado_martingale(sucesso: bool, config: dict):
    registar_resultado(sucesso)
