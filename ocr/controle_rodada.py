# ocr/controle_rodada.py
import time
from typing import Optional
from ocr.leitura_lista import ler_lista_multiplicadores_atuais


def aguardar_nova_rodada(ultimo: Optional[float] = None,
                          timeout: float = 60.0) -> bool:
    """
    Aguarda até que a lista lateral seja actualizada com um novo crash.
    Retorna True se detectou nova rodada, False em timeout.
    """
    if ultimo is None:
        print("🔄 Primeira execução: sem sincronização por lista.")
        return True

    print(f"🔄 Aguardando nova rodada (≠ {ultimo:.2f}x)...")
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            lista = ler_lista_multiplicadores_atuais()
            if lista and lista[0] != ultimo:
                print(f"✅ Nova rodada detectada: {lista[0]:.2f}x")
                return True
        except Exception:
            pass
        time.sleep(0.5)

    print("⚠️ Timeout aguardando nova rodada.")
    return False
