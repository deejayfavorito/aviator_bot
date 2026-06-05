# calibrar/calibrar_area_valor.py
"""
Calibração standalone da área do CAMPO DE VALOR da aposta.

Uso: python -m calibrar.calibrar_area_valor

NÃO depende do _base.py — funciona sozinho.
"""
import json
from pathlib import Path
from tkinter import Tk, Canvas, Label
from PIL import ImageTk
import pyautogui

CONFIG_PATH = Path("config/config.json")
NOME_CHAVE  = "area_valor_aposta"
DESCRICAO   = "Selecciona APENAS a caixa central do número (ex: '65').\nSem incluir os botões '-' e '+'."


class SelectorArea:
    def __init__(self, descricao: str):
        self.resultado = None

        self.screenshot = pyautogui.screenshot()
        self.largura, self.altura = self.screenshot.size

        self.root = Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='black')

        self.img_tk = ImageTk.PhotoImage(self.screenshot)

        self.canvas = Canvas(
            self.root,
            width=self.largura,
            height=self.altura,
            cursor="cross",
            highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        self.label = Label(
            self.root,
            text=f"📐 Calibrar {NOME_CHAVE}\n{descricao}\n\nClica e arrasta | ESC para cancelar",
            font=("Arial", 14, "bold"),
            bg="yellow",
            fg="black",
            padx=20, pady=10
        )
        self.canvas.create_window(self.largura // 2, 40, window=self.label)

        self.start_x = self.start_y = 0
        self.rect_id = None
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
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
            return
        self.resultado = (x1, y1, w, h)
        self.root.destroy()

    def executar(self):
        self.root.mainloop()
        return self.resultado


def main():
    print(f"📐 Calibrando: {NOME_CHAVE}")
    print(f"   {DESCRICAO}")

    selector = SelectorArea(DESCRICAO)
    zona = selector.executar()

    if zona is None:
        print("❌ Calibração cancelada.")
        return

    x, y, w, h = zona

    # Carrega config existente
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    else:
        cfg = {}

    cfg[NOME_CHAVE] = [x, y, w, h]

    CONFIG_PATH.parent.mkdir(exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

    print(f"✅ '{NOME_CHAVE}' guardado: [{x}, {y}, {w}, {h}]")


if __name__ == "__main__":
    main()
