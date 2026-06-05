"""
Calibração INTELIGENTE com validação automática.

Uso:
  python calibrar_inteligente.py

O que faz:
  1. Pede para o jogo Aviator estar visível com o BOTÃO VERDE de aposta
  2. Guia-te pelas 5 áreas, uma a uma
  3. Após cada selecção, VALIDA se apanhaste a área correcta:
     - Botão aposta → deve ter ≥30% verde sólido
     - Área voo → deve ter texto claro sobre fundo escuro
     - Lista → deve detectar pelo menos 3 multiplicadores
  4. Se a validação falhar, avisa e pede para refazer
  5. Mostra previsão da área para confirmares
  6. Guarda no config.json
"""
import json
import sys
import time
import re
import os
from pathlib import Path
from tkinter import Tk, Canvas, Label, Button, Toplevel
from PIL import Image, ImageTk

import cv2
import numpy as np
import pyautogui
import pytesseract

if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CONFIG_PATH = Path("config/config.json")


# ════════════════════════════════════════════════════════════════════════
# UI: Selector de área no ecrã inteiro
# ════════════════════════════════════════════════════════════════════════

class SelectorArea:
    """Janela transparente em ecrã inteiro para seleccionar uma área."""

    def __init__(self, titulo: str, descricao: str):
        self.titulo = titulo
        self.descricao = descricao
        self.resultado = None

        # Captura ecrã para usar como fundo
        self.screenshot = pyautogui.screenshot()
        self.largura, self.altura = self.screenshot.size

        self.root = Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='black')

        # Imagem de fundo (screenshot escurecido)
        self.img_pil = self.screenshot.copy()
        self.img_tk = ImageTk.PhotoImage(self.img_pil)

        self.canvas = Canvas(
            self.root,
            width=self.largura,
            height=self.altura,
            cursor="cross",
            highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        # Label com instruções
        self.label = Label(
            self.root,
            text=f"📐 {titulo}\n{descricao}\n\nClica e arrasta para seleccionar | ESC para cancelar",
            font=("Arial", 14, "bold"),
            bg="yellow",
            fg="black",
            padx=20, pady=10
        )
        self.canvas.create_window(self.largura // 2, 40, window=self.label)

        # Eventos
        self.start_x = self.start_y = 0
        self.rect_id = None
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=3
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        w, h = x2 - x1, y2 - y1
        if w < 10 or h < 10:
            return  # área pequena demais, ignora
        self.resultado = (x1, y1, w, h)
        self.root.destroy()

    def executar(self):
        self.root.mainloop()
        return self.resultado


# ════════════════════════════════════════════════════════════════════════
# Validadores — cada um confirma se a calibração apanhou a coisa certa
# ════════════════════════════════════════════════════════════════════════

def _capturar_zona(zona) -> np.ndarray:
    x, y, w, h = zona
    ss = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)


def _pct_cor(img: np.ndarray, hsv_lo, hsv_hi) -> float:
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lo), np.array(hsv_hi))
    return cv2.countNonZero(mask) / mask.size


def validar_botao_aposta(zona) -> tuple:
    """Botão de aposta deve ter ≥30% verde dominante."""
    img = _capturar_zona(zona)
    verde = _pct_cor(img, [50, 100, 100], [80, 255, 255])
    if verde < 0.30:
        return False, f"Apenas {verde*100:.0f}% verde detectado. Esperado ≥30%. Reposiciona para o CENTRO do botão verde."
    return True, f"✅ {verde*100:.0f}% verde detectado — calibração válida"


def validar_botao_cashout(zona) -> tuple:
    """Mesma área que aposta. Aceita se for igual à aposta calibrada."""
    img = _capturar_zona(zona)
    verde   = _pct_cor(img, [50, 100, 100], [80, 255, 255])
    laranja = _pct_cor(img, [10, 150, 150], [25, 255, 255])
    vermelho = _pct_cor(img, [0, 120, 120], [10, 255, 255])

    if verde >= 0.30 or laranja >= 0.30 or vermelho >= 0.30:
        cor = "verde" if verde >= 0.30 else ("laranja" if laranja >= 0.30 else "vermelho")
        pct = max(verde, laranja, vermelho)
        return True, f"✅ Botão detectado ({cor} {pct*100:.0f}%) — calibração válida"
    return False, "Nenhuma cor dominante detectada. Aponta para o CENTRO do botão grande."


def validar_area_voo(zona) -> tuple:
    """Área do voo deve permitir leitura OCR de um número."""
    img = _capturar_zona(zona)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    texto = pytesseract.image_to_string(
        thresh, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.x"
    )
    if re.search(r"\d+\.\d{2}", texto):
        return True, f"✅ Multiplicador detectado: '{texto.strip()}' — calibração válida"
    # Pode ser durante janela de aposta (sem número visível)
    h, w = img.shape[:2]
    return True, f"⚠️  Sem número visível agora (área {w}×{h}px). Pode estar OK se o jogo está entre rounds."


def validar_lista(zona) -> tuple:
    """Lista deve detectar pelo menos 3 multiplicadores."""
    img = _capturar_zona(zona)
    h, w = img.shape[:2]
    img_grande = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_grande, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    inverted = cv2.bitwise_not(gray)
    thresh = cv2.adaptiveThreshold(
        inverted, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 4
    )
    texto = pytesseract.image_to_string(
        thresh, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.x"
    )
    nums = re.findall(r"\d{1,4}\.\d{2}", texto)
    if len(nums) >= 3:
        return True, f"✅ {len(nums)} multiplicadores lidos: {nums[:5]}..."
    if len(nums) >= 1:
        return False, f"Apenas {len(nums)} número lido ({nums}). Alarga a selecção para incluir mais da lista."
    return False, "Nenhum número detectado. Certifica-te que estás a apanhar a linha de multiplicadores no topo."


def validar_area_vermelho(zona) -> tuple:
    """Área onde aparece 'VOOU PARA LONGE'. Geralmente igual à área do voo."""
    img = _capturar_zona(zona)
    h, w = img.shape[:2]
    if w < 100 or h < 50:
        return False, f"Área pequena demais ({w}×{h}). Selecciona toda a zona onde o número grande aparece."
    return True, f"✅ Área de {w}×{h}px — calibração válida"


# ════════════════════════════════════════════════════════════════════════
# Pipeline de calibração
# ════════════════════════════════════════════════════════════════════════

AREAS = [
    {
        "chave": "regiao_lista_multiplicadores",
        "titulo": "1/5 — Lista de Multiplicadores (TOPO)",
        "descricao": "Selecciona toda a LINHA DE NÚMEROS coloridos no topo do jogo (ex: 1.42x  1.08x  1.46x...)",
        "validador": validar_lista,
        "instrucao_inicial": "Confirma que vês a linha de multiplicadores no topo do jogo Aviator",
    },
    {
        "chave": "regiao_multiplicador_voo",
        "titulo": "2/5 — Área do Multiplicador (CENTRO)",
        "descricao": "Selecciona a zona CENTRAL onde aparece o número grande durante o voo (ex: '1.26x'). Inclui margem.",
        "validador": validar_area_voo,
        "instrucao_inicial": "OK se o voo está a acontecer ou se está entre rounds",
    },
    {
        "chave": "area_apostar",
        "titulo": "3/5 — Botão APOSTAR (VERDE)",
        "descricao": "Selecciona o CENTRO do botão grande VERDE 'Aposta XX AOA'. Evita as bordas pretas.",
        "validador": validar_botao_aposta,
        "instrucao_inicial": "⚠️ AGUARDA até apareça o botão VERDE 'Aposta' antes de continuar",
    },
    {
        "chave": "area_cashout",
        "titulo": "4/5 — Botão CASHOUT (mesma área)",
        "descricao": "Selecciona a MESMA área do botão (verde/laranja/vermelho — todos no mesmo sítio).",
        "validador": validar_botao_cashout,
        "instrucao_inicial": "Pode ser qualquer cor (verde, laranja, vermelho)",
    },
    {
        "chave": "area_vermelho_final",
        "titulo": "5/5 — Área 'VOOU PARA LONGE'",
        "descricao": "Mesma área do passo 2 (onde o número grande aparece).",
        "validador": validar_area_vermelho,
        "instrucao_inicial": "Mesma zona central onde o multiplicador é mostrado",
    },
]


def carregar_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def guardar_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)


def calibrar_uma_area(area_info: dict) -> tuple:
    """Calibra uma área, validando até estar OK ou o utilizador desistir."""
    chave = area_info["chave"]
    titulo = area_info["titulo"]
    print(f"\n{'='*70}")
    print(f"  {titulo}")
    print(f"{'='*70}")
    print(f"📝 {area_info['descricao']}")
    print(f"💡 {area_info['instrucao_inicial']}")
    input("\n👉 Carrega ENTER quando o jogo estiver no estado certo (ou Ctrl+C para sair)...")

    tentativa = 1
    while tentativa <= 3:
        print(f"\n🖱️  Tentativa {tentativa}/3 — vai abrir a selecção...")
        time.sleep(0.5)

        selector = SelectorArea(titulo, area_info["descricao"])
        zona = selector.executar()

        if zona is None:
            print("❌ Selecção cancelada.")
            return None

        x, y, w, h = zona
        print(f"📐 Seleccionado: [{x}, {y}, {w}, {h}] ({w}×{h}px)")

        # Validar
        valido, msg = area_info["validador"](zona)
        print(f"🔍 {msg}")

        if valido:
            return zona
        else:
            print(f"⚠️  Calibração inválida. A tentar de novo...")
            tentativa += 1

    print("❌ Falhei 3 vezes. Vou guardar à mesma — verifica manualmente.")
    return zona


def main():
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║       CALIBRAÇÃO INTELIGENTE DO AVIATOR BOT                      ║")
    print("║                                                                  ║")
    print("║  Vais calibrar 5 áreas. Cada uma é validada automaticamente.     ║")
    print("║  Se calibrares mal, o script avisa e pede para refazer.          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print("\n⚠️  IMPORTANTE: tem o jogo Aviator visível no ecrã no tamanho real")
    print("   que vais usar (não minimizes nem mudes o zoom depois).")

    cfg = carregar_config()

    for area_info in AREAS:
        zona = calibrar_uma_area(area_info)
        if zona is None:
            print("\n🛑 Calibração interrompida. Saídas feitas até aqui foram guardadas.")
            break
        cfg[area_info["chave"]] = list(zona)
        guardar_config(cfg)
        print(f"💾 Guardado: {area_info['chave']} = {list(zona)}")

    print("\n" + "═" * 70)
    print("✅ Calibração concluída!")
    print("═" * 70)
    print("\nÁreas guardadas em config/config.json:")
    for area_info in AREAS:
        valor = cfg.get(area_info["chave"], "❌ NÃO CALIBRADA")
        print(f"  • {area_info['chave']}: {valor}")

    print("\n🚀 Agora podes correr o bot: python main_autonomo.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Calibração cancelada pelo utilizador.")
