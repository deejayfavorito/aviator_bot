"""
testar_ocr.py — Testa se o OCR está a ler a lista correctamente.
Uso: python testar_ocr.py
Mostra o que o bot está a ver SEM apostar nada.
"""
import time
import sys
import cv2
import numpy as np
import pyautogui
import pytesseract

if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from config.configuracoes import carregar_config
from ocr.leitura_lista import ler_lista_multiplicadores_atuais

print("=" * 50)
print("  TESTE OCR — Aviator Bot")
print("=" * 50)
print("Certifica-te que o jogo está visível no ecrã.")
print("A testar durante 30 segundos (10 leituras)...")
print()

config = carregar_config()
area = config.get("regiao_lista_multiplicadores")
print(f"📐 Região configurada: {area}")
print()

sucessos = 0
for i in range(10):
    print(f"--- Leitura {i+1}/10 ---")
    lista = ler_lista_multiplicadores_atuais()
    if lista:
        sucessos += 1
        print(f"✅ Encontrou {len(lista)} multiplicadores: {lista}")
    else:
        print("❌ Lista vazia")

        # Guarda screenshot para diagnóstico
        if area:
            x, y, w, h = area
            ss = pyautogui.screenshot(region=(x, y, w, h))
            img = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
            cv2.imwrite(f"data/debug_ocr_{i+1}.png", img)
            print(f"   💾 Screenshot guardado: data/debug_ocr_{i+1}.png")
    time.sleep(3)

print()
print("=" * 50)
print(f"RESULTADO: {sucessos}/10 leituras com sucesso")
if sucessos >= 5:
    print("✅ OCR funcionando! Podes correr o bot.")
elif sucessos > 0:
    print("⚠️ OCR parcial — recalibra a área da lista.")
else:
    print("❌ OCR falhou — verifica a calibração e o Tesseract.")
    print("   Abre as imagens data/debug_ocr_*.png para ver o que o bot captura.")
print("=" * 50)
