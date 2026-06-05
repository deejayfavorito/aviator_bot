# calibrar/_base.py
import tkinter as tk
from tkinter import messagebox
from typing import Optional, List
from config.configuracoes import salvar_config, recarregar_config


def selecionar_area(titulo: str, chave_config: str) -> Optional[List[int]]:
    """
    UI de calibração reutilizável para qualquer área do ecrã.
    - Abre janela fullscreen semitransparente
    - Captura drag do rato com feedback visual (rectângulo vermelho)
    - Salva coordenadas [x, y, w, h] no config.json
    - ESC para cancelar
    """
    root = tk.Tk()
    root.title(titulo)
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.35)
    root.configure(background="black")

    canvas = tk.Canvas(root, cursor="cross", bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    # Instrução no topo
    larg = root.winfo_screenwidth()
    canvas.create_text(
        larg // 2, 40,
        text=f"📐  {titulo}  —  Clique e arraste para seleccionar  |  ESC para cancelar",
        fill="white", font=("Arial", 14, "bold")
    )

    pontos  = {}
    rect_id = None

    def on_press(event):
        nonlocal rect_id
        pontos["x0"], pontos["y0"] = event.x, event.y
        if rect_id:
            canvas.delete(rect_id)

    def on_drag(event):
        nonlocal rect_id
        if rect_id:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            pontos.get("x0", 0), pontos.get("y0", 0),
            event.x, event.y,
            outline="red", width=2
        )

    def on_release(event):
        pontos["x1"], pontos["y1"] = event.x, event.y
        root.destroy()

    def on_escape(event):
        pontos.clear()
        root.destroy()

    canvas.bind("<Button-1>",        on_press)
    canvas.bind("<B1-Motion>",       on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>",            on_escape)
    root.mainloop()

    if not pontos or "x1" not in pontos:
        print(f"❌ Calibração de '{chave_config}' cancelada.")
        return None

    x = min(pontos["x0"], pontos["x1"])
    y = min(pontos["y0"], pontos["y1"])
    w = abs(pontos["x1"] - pontos["x0"])
    h = abs(pontos["y1"] - pontos["y0"])

    if w < 10 or h < 10:
        messagebox.showwarning("Área inválida", "Selecção muito pequena. Tente novamente.")
        return None

    area = [x, y, w, h]
    if salvar_config({chave_config: area}):
        recarregar_config()
        print(f"✅ '{chave_config}' guardado: {area}")
    return area
