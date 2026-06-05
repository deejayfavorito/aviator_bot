# ocr/verificar_aviao_caiu.py
import cv2
import numpy as np
import pyautogui
from config.configuracoes import carregar_config


def _mascara_vermelha(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m1  = cv2.inRange(hsv, np.array([0,   70, 50]), np.array([10,  255, 255]))
    m2  = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
    return cv2.bitwise_or(m1, m2)


def detectar_vermelho_na_area(threshold: float = 0.03) -> bool:
    """
    Detecta se o avião caiu pela presença de vermelho no ecrã.
    threshold: proporção mínima de pixels vermelhos (3% por defeito).
    """
    config = carregar_config()
    area   = config.get("area_vermelho_final")
    if not area:
        print("⚠️ 'area_vermelho_final' não definida no config.json.")
        return False
    try:
        x, y, w, h = area
        ss   = pyautogui.screenshot(region=(x, y, w, h))
        img  = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
        mask = _mascara_vermelha(img)
        prop = cv2.countNonZero(mask) / (w * h)
        if prop >= threshold:
            print(f"🟥 Vermelho detectado: {prop * 100:.1f}%")
            return True
        return False
    except Exception as e:
        print(f"❌ Erro ao verificar vermelho: {e}")
        return False


# Alias para compatibilidade com código antigo
aviao_caiu_por_cor_vermelha = detectar_vermelho_na_area
