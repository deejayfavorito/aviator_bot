# calibrar/calibrar_historico.py
"""
Calibrador da AREA DO HISTORICO EXPANDIDO do Aviator.

Workflow:
  1. No Aviator, clica no icone do historico (popup com 5-6 linhas de crashes)
  2. Mantem o popup aberto
  3. Corre este calibrador (via GUI ou directo)
  4. Desenha rectangulo sobre TODA a area dos numeros (5-6 linhas, ~80 crashes)
  5. ENTER confirma, salva em config/config.json como area_historico
"""
import sys
import os
import json
import tkinter as tk
from PIL import Image, ImageTk
import pyautogui

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

CAMINHO_CONFIG = "config/config.json"


def carregar_config_actual() -> dict:
    if not os.path.exists(CAMINHO_CONFIG):
        return {}
    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_area(area: tuple) -> None:
    cfg = carregar_config_actual()
    cfg["area_historico"] = list(area)
    os.makedirs(os.path.dirname(CAMINHO_CONFIG), exist_ok=True)
    with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    print(f"OK Area salva: area_historico = {list(area)}")


class SeletorArea:
    def __init__(self):
        print("A capturar ecra...")
        self.screenshot = pyautogui.screenshot()
        self.largura, self.altura = self.screenshot.size

        self.root = tk.Tk()
        self.root.title("Calibrar HISTORICO — clica e arrasta sobre os numeros")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.root, cursor="cross",
                                  width=self.largura, height=self.altura,
                                  highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.foto = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.foto)

        # Instrucoes
        self.canvas.create_rectangle(
            self.largura // 2 - 450, 20,
            self.largura // 2 + 450, 130,
            fill="black", outline="yellow", width=2)
        self.canvas.create_text(
            self.largura // 2, 75,
            text="📐 Desenha um rectângulo sobre TODA a área dos números do histórico\n"
                 "(as 5-6 linhas com ~80 multiplicadores)\n"
                 "ESC = cancelar  |  ENTER = confirmar",
            fill="yellow", font=("Arial", 14, "bold"), justify="center")

        self.start_x = self.start_y = None
        self.rect_id = None
        self.area_final = None

        self.canvas.bind("<ButtonPress-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)
        self.root.bind("<Escape>", lambda e: self.cancelar())
        self.root.bind("<Return>", lambda e: self.confirmar())
        self.root.focus_force()

    def on_down(self, e):
        self.start_x, self.start_y = e.x, e.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="lime", width=2)

    def on_drag(self, e):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, e.x, e.y)

    def on_up(self, e):
        if self.start_x is None:
            return
        x1, y1 = min(self.start_x, e.x), min(self.start_y, e.y)
        x2, y2 = max(self.start_x, e.x), max(self.start_y, e.y)
        w, h = x2 - x1, y2 - y1
        if w < 50 or h < 30:
            print("Rectangulo muito pequeno. Tenta de novo.")
            return
        self.area_final = (x1, y1, w, h)
        print(f"Area desenhada: x={x1}, y={y1}, w={w}, h={h}")
        print("Carrega ENTER para confirmar.")

    def confirmar(self):
        if self.area_final is None:
            print("Desenha primeiro um rectangulo.")
            return
        self.root.quit()
        try: self.root.destroy()
        except: pass

    def cancelar(self):
        print("Cancelado.")
        self.area_final = None
        self.root.quit()
        try: self.root.destroy()
        except: pass

    def correr(self):
        self.root.mainloop()
        return self.area_final


def main():
    print("=" * 60)
    print("CALIBRADOR DA AREA DO HISTORICO EXPANDIDO")
    print("=" * 60)
    print()
    print("Vai abrir janela fullscreen. Desenha sobre os ~80 numeros.")
    print()

    seletor = SeletorArea()
    area = seletor.correr()

    if area is None:
        print("Nenhuma area selecionada.")
        sys.exit(1)

    salvar_area(area)

    print()
    print("Teste OCR...")
    try:
        from ocr.leitura_historico import ler_historico
        crashes = ler_historico(area, debug=False)
        if crashes:
            print(f"OK Detectados {len(crashes)} crashes!")
            print(f"   Primeiros 10: {crashes[:10]}")
            if 20 <= len(crashes) <= 100:
                print("✅ Numero razoavel — calibracao OK")
            else:
                print(f"⚠️ Esperavam-se 30-80 crashes, obtive {len(crashes)}")
                print("   Tenta recalibrar com rectangulo mais ajustado.")
        else:
            print("❌ Nenhum crash detectado. Recalibra.")
    except ImportError as e:
        print(f"Nao importou leitura_historico: {e}")
        print(f"Mas area salva: {area}")


if __name__ == "__main__":
    main()
