# utils/watchdog.py
"""
Watchdog — vigia o estado do bot e reage a problemas.

ESCALADA PROGRESSIVA quando rondas param de ser detectadas:
  Nível 1 (2 min):  Mexer o rato (mouse jiggle)
  Nível 2 (4 min):  Mexer o rato + scroll suave
  Nível 3 (6 min):  Verificar internet (ping)
  Nível 4 (10 min): Reportar problema sério e parar de tentar

Mantém compatibilidade com o core.py existente:
  - verificar()                 — chamado no loop principal
  - registar_nova_rodada()      — chamado quando há novo round
"""
import time
import subprocess
import platform
from datetime import datetime
from typing import Optional

import pyautogui


# ─── Estado interno ──────────────────────────────────────────────────────
_ultima_rodada_ts: Optional[float] = None
_nivel_actual: int                 = 0
_ultimo_aviso_ts: Optional[float]  = None

# ─── Limiares (em segundos) ──────────────────────────────────────────────
LIMIAR_NIVEL_1 = 120   # 2 min  — mouse jiggle
LIMIAR_NIVEL_2 = 240   # 4 min  — scroll
LIMIAR_NIVEL_3 = 360   # 6 min  — ping internet
LIMIAR_NIVEL_4 = 600   # 10 min — paragem


def registar_nova_rodada():
    """Reseta o watchdog — chamado quando há novo round detectado."""
    global _ultima_rodada_ts, _nivel_actual
    _ultima_rodada_ts = time.time()
    if _nivel_actual > 0:
        print(f"✅ Watchdog: rondas retomadas, a baixar o alerta.")
    _nivel_actual = 0


def _tempo_sem_rondas() -> float:
    """Segundos desde a última ronda detectada."""
    if _ultima_rodada_ts is None:
        return 0.0
    return time.time() - _ultima_rodada_ts


def _testar_internet() -> bool:
    """Testa se a internet está acessível."""
    try:
        comando = "ping -n 1 8.8.8.8" if platform.system() == "Windows" else "ping -c 1 8.8.8.8"
        resultado = subprocess.run(
            comando.split(),
            capture_output=True,
            timeout=5
        )
        return resultado.returncode == 0
    except Exception:
        return False


def _mexer_rato_suave():
    """Mexe o rato para fora-e-volta, sem interferir com cliques."""
    try:
        x, y = pyautogui.position()
        # Move um pouco e volta — apenas para sinalizar actividade
        pyautogui.moveTo(x + 5, y + 5, duration=0.2)
        time.sleep(0.1)
        pyautogui.moveTo(x, y, duration=0.2)
    except Exception as e:
        print(f"⚠️  Watchdog: erro ao mexer rato: {e}")


def _scroll_suave():
    """Scroll de 1 unidade e volta — só para acordar a página."""
    try:
        pyautogui.scroll(-1)
        time.sleep(0.3)
        pyautogui.scroll(1)
    except Exception as e:
        print(f"⚠️  Watchdog: erro ao fazer scroll: {e}")


def verificar():
    """
    Chamado a cada iteração do loop principal.
    Verifica há quanto tempo não há rondas e reage progressivamente.
    """
    global _nivel_actual, _ultimo_aviso_ts, _ultima_rodada_ts

    # Inicializa na primeira chamada
    if _ultima_rodada_ts is None:
        _ultima_rodada_ts = time.time()
        return

    tempo_inactivo = _tempo_sem_rondas()
    agora = time.time()

    # Espaça os avisos: não mais que 1 por minuto
    if _ultimo_aviso_ts and (agora - _ultimo_aviso_ts) < 60:
        return

    # ── NÍVEL 4: paragem total (>10 min) ────────────────────────────────
    if tempo_inactivo >= LIMIAR_NIVEL_4 and _nivel_actual < 4:
        _nivel_actual = 4
        _ultimo_aviso_ts = agora
        minutos = tempo_inactivo / 60
        print()
        print("🚨" * 30)
        print(f"🚨 WATCHDOG: {minutos:.1f} minutos sem rondas detectadas!")
        print(f"🚨 O jogo provavelmente travou ou perdeu conexão.")
        print(f"🚨 Recomendação: verifica o navegador e a internet.")
        print(f"🚨 O bot continua a tentar — para se quiseres com Ctrl+C.")
        print("🚨" * 30)
        print()
        return

    # ── NÍVEL 3: verificar internet (6 min) ─────────────────────────────
    if tempo_inactivo >= LIMIAR_NIVEL_3 and _nivel_actual < 3:
        _nivel_actual = 3
        _ultimo_aviso_ts = agora
        minutos = tempo_inactivo / 60
        print(f"⚠️  Watchdog: {minutos:.1f}min sem rondas — a testar internet...")
        if _testar_internet():
            print(f"   ✅ Internet OK — problema é no jogo (talvez travado).")
            print(f"   💡 Sugestão: clica no navegador e verifica se o jogo está activo.")
        else:
            print(f"   ❌ Internet INACESSÍVEL — não há conexão!")
            print(f"   💡 Verifica a tua ligação à rede.")
        return

    # ── NÍVEL 2: scroll + rato (4 min) ──────────────────────────────────
    if tempo_inactivo >= LIMIAR_NIVEL_2 and _nivel_actual < 2:
        _nivel_actual = 2
        _ultimo_aviso_ts = agora
        minutos = tempo_inactivo / 60
        print(f"⚠️  Watchdog: {minutos:.1f}min sem rondas — a fazer scroll + mexer rato.")
        _scroll_suave()
        _mexer_rato_suave()
        return

    # ── NÍVEL 1: mexer rato (2 min) ─────────────────────────────────────
    if tempo_inactivo >= LIMIAR_NIVEL_1 and _nivel_actual < 1:
        _nivel_actual = 1
        _ultimo_aviso_ts = agora
        minutos = tempo_inactivo / 60
        print(f"⚠️  Watchdog: {minutos:.1f}min sem rondas — a mexer o rato.")
        _mexer_rato_suave()
        return


def info_estado() -> str:
    """Retorna info do estado do watchdog (para debug ou dashboard)."""
    if _ultima_rodada_ts is None:
        return "Watchdog: à espera da 1ª ronda"
    tempo = _tempo_sem_rondas()
    nivel = ["NORMAL", "🟡 NÍVEL 1", "🟠 NÍVEL 2", "🔴 NÍVEL 3", "🚨 NÍVEL 4"][_nivel_actual]
    return f"Watchdog: {tempo:.0f}s desde última ronda | {nivel}"


def reset():
    """Reseta o watchdog manualmente."""
    global _ultima_rodada_ts, _nivel_actual, _ultimo_aviso_ts
    _ultima_rodada_ts = time.time()
    _nivel_actual = 0
    _ultimo_aviso_ts = None
