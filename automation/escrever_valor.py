# automation/escrever_valor.py
"""
Escreve um valor numérico no campo da aposta.

CORRECÇÃO: desactiva o pyautogui.FAILSAFE durante a operação, porque
o triplo-clique + typewrite pode mover o rato brevemente para perto
dos cantos e disparar a protecção.
"""
import time
import pyautogui
from config.configuracoes import carregar_config


def escrever_valor_aposta(valor: float) -> bool:
    """
    Escreve o novo valor no campo de aposta.
    """
    cfg = carregar_config()
    area = cfg.get("area_valor_aposta")
    if not area:
        print("❌ area_valor_aposta não configurada. Corre: python -m calibrar.calibrar_area_valor")
        return False

    # Guarda estado actual do fail-safe
    failsafe_original = pyautogui.FAILSAFE
    pause_original    = pyautogui.PAUSE

    try:
        # ── Desactiva fail-safe temporariamente ──────────────────────────
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE    = 0.05

        x, y, w, h = area
        centro_x = x + w // 2
        centro_y = y + h // 2

        valor_str = str(int(round(valor)))
        print(f"💰 A definir valor da aposta: {valor_str} AOA")

        # 1. Move primeiro o rato com segurança até ao centro do campo
        pyautogui.moveTo(centro_x, centro_y, duration=0.15)
        time.sleep(0.1)

        # 2. Triplo-clique para seleccionar tudo
        pyautogui.click(centro_x, centro_y, clicks=3, interval=0.08)
        time.sleep(0.15)

        # 3. Apaga selecção
        pyautogui.press("delete")
        time.sleep(0.10)

        # 4. Escreve novo valor
        pyautogui.typewrite(valor_str, interval=0.05)
        time.sleep(0.15)

        # 5. Tab para confirmar
        pyautogui.press("tab")
        time.sleep(0.20)

        print(f"✅ Valor {valor_str} AOA definido")
        return True

    except Exception as e:
        print(f"❌ Erro ao escrever valor: {e}")
        return False

    finally:
        # ── Restaura estado do fail-safe ─────────────────────────────────
        pyautogui.FAILSAFE = failsafe_original
        pyautogui.PAUSE    = pause_original
