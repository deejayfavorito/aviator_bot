# calibrar/calibrar_saldo.py
"""
Calibrador da AREA DO SALDO no canto superior direito do Aviator.

Como usar:
  1. Abre o Bantubet e entra no Aviator (modo Fun ou Real)
  2. Coloca a janela do Chrome na posicao habitual
  3. Corre via GUI (botao "Calibrar" na linha "Saldo do casino")
     OU directamente: python -m calibrar.calibrar_saldo
  4. A janela fullscreen abre AUTOMATICAMENTE com o ecra
  5. Clica e arrasta um rectangulo sobre o numero do saldo
     (ex: "50,000" no canto superior direito)
  6. ENTER para confirmar, ESC para cancelar

Importante:
  - Marca SO o numero (sem o "AOA")
  - Marca o rectangulo justo, sem espacos a mais nem a menos
  - Se houver virgulas/pontos, inclui-os
"""
import sys
import os
import json
import tkinter as tk
from PIL import Image, ImageTk
import pyautogui

# Garantir UTF-8 no stdout do Windows (importante para subprocess da GUI)
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
    except Exception as e:
        print(f"⚠️ Erro a carregar config: {e}")
        return {}


def salvar_area(area: tuple) -> None:
    cfg = carregar_config_actual()
    cfg["area_saldo"] = list(area)

    os.makedirs(os.path.dirname(CAMINHO_CONFIG), exist_ok=True)
    with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

    print(f"✅ Área salva no config: area_saldo = {list(area)}")


class SeletorArea:
    """
    Tk overlay fullscreen onde o utilizador desenha um rectangulo
    sobre o ecra para definir a area de captura.
    """
    def __init__(self):
        # Capturar ecra inteiro PRIMEIRO (antes de criar janela)
        print("📸 A capturar ecrã...")
        self.screenshot = pyautogui.screenshot()
        self.largura, self.altura = self.screenshot.size
        print(f"   Resolução: {self.largura}x{self.altura}")

        # Janela fullscreen sem decoracoes
        self.root = tk.Tk()
        self.root.title("Calibrar SALDO — clica e arrasta sobre o número")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)

        # Canvas com o screenshot
        self.canvas = tk.Canvas(self.root, cursor="cross",
                                  width=self.largura, height=self.altura,
                                  highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.foto = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.foto)

        # Instrucoes (texto grande, amarelo, no topo do ecra)
        self.canvas.create_rectangle(
            self.largura // 2 - 400, 20,
            self.largura // 2 + 400, 130,
            fill="black", outline="yellow", width=2
        )
        self.canvas.create_text(
            self.largura // 2, 75,
            text="🎯 Clica e ARRASTA um rectângulo sobre o NÚMERO DO SALDO\n"
                 "(canto superior direito do Aviator — ex: '50,000')\n"
                 "ESC = cancelar  |  ENTER = confirmar após desenhar",
            fill="yellow",
            font=("Arial", 14, "bold"),
            justify="center"
        )

        # Estado do desenho
        self.start_x = self.start_y = None
        self.rect_id = None
        self.area_final = None

        # Eventos
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.root.bind("<Escape>", lambda e: self.cancelar())
        self.root.bind("<Return>", lambda e: self.confirmar())

        # Foco na janela para receber teclas
        self.root.focus_force()

    def on_mouse_down(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="lime", width=2
        )

    def on_mouse_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id,
                                self.start_x, self.start_y,
                                event.x, event.y)

    def on_mouse_up(self, event):
        if self.start_x is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        w = x2 - x1
        h = y2 - y1

        if w < 10 or h < 5:
            print("⚠️ Rectângulo muito pequeno. Desenha de novo.")
            return

        self.area_final = (x1, y1, w, h)
        print(f"📐 Área desenhada: x={x1}, y={y1}, w={w}, h={h}")
        print("   Carrega ENTER para confirmar, ou desenha outro rectângulo, ou ESC para cancelar.")

    def confirmar(self):
        if self.area_final is None:
            print("⚠️ Desenha primeiro um rectângulo (clica e arrasta).")
            return
        self.root.quit()
        try:
            self.root.destroy()
        except Exception:
            pass

    def cancelar(self):
        print("❌ Cancelado pelo utilizador.")
        self.area_final = None
        self.root.quit()
        try:
            self.root.destroy()
        except Exception:
            pass

    def correr(self) -> tuple:
        self.root.mainloop()
        return self.area_final


def main():
    print("=" * 60)
    print("🎯 CALIBRADOR DA ÁREA DO SALDO")
    print("=" * 60)
    print()
    print("Janela fullscreen vai abrir AGORA.")
    print("Clica e arrasta sobre o NÚMERO do saldo no Aviator.")
    print("ENTER para confirmar, ESC para cancelar.")
    print()

    seletor = SeletorArea()
    area = seletor.correr()

    if area is None:
        print("\n❌ Nenhuma área selecionada.")
        sys.exit(1)

    salvar_area(area)

    print()
    print("=" * 60)
    print("🧪 TESTE AUTOMÁTICO DO OCR")
    print("=" * 60)

    try:
        from ocr.leitura_saldo import ler_saldo
        for i in range(3):
            valor = ler_saldo(area, debug=False)
            print(f"   Tentativa {i+1}: saldo lido = {valor}")
            if valor is not None:
                print()
                print(f"✅ OCR FUNCIONOU! Saldo detectado: {valor:.0f} AOA")
                print()
                print("Se este valor bate com o saldo real, está calibrado.")
                print("Se não bate, corre de novo com rectângulo mais justo.")
                return
    except ImportError as e:
        print(f"⚠️ Não consegui importar ocr.leitura_saldo: {e}")
        print(f"   Mas a área foi salva: {area}")
        print("   Verifica que tens ocr/leitura_saldo.py")
        return
    except Exception as e:
        print(f"⚠️ Erro no teste: {e}")
        return

    print()
    print("⚠️ OCR não conseguiu ler.")
    print("   Tenta calibrar de novo, marcando o rectângulo MAIS JUSTO")
    print("   sobre o número (sem espaço a mais nem a menos em volta).")


if __name__ == "__main__":
    main()
