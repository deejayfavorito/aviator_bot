# ocr/monitoramento_aposta.py
"""
Aposta com DETECTOR DE FASE — só clica se está realmente em APOSTA_DISPONIVEL.
Zero ambiguidade entre botão de aposta e cashout.
"""
import sys
import time
import cv2
import numpy as np
import pyautogui
from config.configuracoes import carregar_config
from automation.clique import clicar_com_segurança
from ocr.detector_fase import detectar_fase, Fase, descricao_fase

if sys.platform == "win32":
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _obter_regiao_aposta() -> tuple:
    cfg  = carregar_config()
    area = cfg.get("area_apostar") or cfg.get("area_aposta")
    if not area:
        raise RuntimeError("area_apostar não configurada")
    return tuple(area)


def apostar_agora(timeout: float = 5.0) -> bool:
    """
    Aguarda fase APOSTA_DISPONIVEL e clica.
    Se detectar outra fase (voo a decorrer, aposta já colocada, crash),
    aguarda ou aborta consoante o caso.
    """
    print(f"⏳ A aguardar fase APOSTA_DISPONIVEL (até {timeout:.0f}s)...")
    deadline = time.time() + timeout
    fase_anterior = None

    while time.time() < deadline:
        fase, info = detectar_fase()

        # Log apenas quando muda
        if fase != fase_anterior:
            print(f"   {descricao_fase(fase)} | {info}")
            fase_anterior = fase

        if fase == Fase.APOSTA_DISPONIVEL:
            # Confirmado: pode clicar
            regiao = _obter_regiao_aposta()
            x, y, w, h = regiao
            centro = (x + w // 2, y + h // 2)

            print(f"✅ A clicar APOSTA em {centro}")
            clicar_com_segurança(centro)
            time.sleep(0.30)

            # Confirma: fase deve agora ser APOSTA_COLOCADA
            fase_apos, _ = detectar_fase()
            if fase_apos == Fase.APOSTA_COLOCADA:
                print("✅ Aposta CONFIRMADA (botão Cancelar visível)")
                return True
            if fase_apos != Fase.APOSTA_DISPONIVEL:
                print(f"✅ Aposta provavelmente OK (fase agora: {fase_apos.value})")
                return True

            print("⚠️ Clique não registou — botão ainda verde")
            return False

        elif fase in (Fase.VOO_COM_APOSTA, Fase.VOO_SEM_APOSTA):
            # Voo em decurso — espera
            time.sleep(0.3)
            continue

        elif fase == Fase.APOSTA_COLOCADA:
            # Já temos aposta colocada (de algum clique anterior)
            print("ℹ️  Aposta já estava colocada — a continuar para cashout")
            return True

        else:
            # Outros estados (CRASH, INDEFINIDA, etc) — espera pouco e tenta de novo
            time.sleep(0.2)

    print(f"❌ Timeout {timeout:.0f}s — não detectada fase APOSTA_DISPONIVEL")
    return False


def cancelar_aposta_real() -> bool:
    """Cancela uma aposta já colocada (clica no botão vermelho 'Cancelar')."""
    fase, _ = detectar_fase()
    if fase == Fase.APOSTA_COLOCADA:
        regiao = _obter_regiao_aposta()
        x, y, w, h = regiao
        clicar_com_segurança((x + w // 2, y + h // 2))
        print("🚫 Aposta cancelada")
        return True
    return False


# Aliases retrocompatíveis
monitorar_aposta_precisa = apostar_agora
def marcar_fim_round(): pass
def aguardar_janela_de_aposta(timeout: float = 14.0) -> bool: return True
def esperar_fim_da_rodada(timeout: float = 30.0) -> bool: return True


def capturar_area_aposta():
    """Compatibilidade — usado por outros módulos."""
    x, y, w, h = _obter_regiao_aposta()
    ss = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
