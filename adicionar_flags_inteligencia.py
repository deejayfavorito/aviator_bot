"""
Adiciona as flags da Inteligência Adaptativa ao config.json
SEM tocar nas calibrações nem nos outros parâmetros.

Uso: python adicionar_flags_inteligencia.py
"""
import json
from pathlib import Path

CONFIG = Path("config/config.json")

NOVAS_FLAGS = {
    "kelly_modo": "off",
    "adaptive_strategy": False,
    "hot_cold_detection": False,
    "preservar_banca": False,
    "preservar_banca_limiar": 1000.0,
}

if not CONFIG.exists():
    print("❌ config/config.json não encontrado.")
    print("   Vais ter que recalibrar todas as áreas.")
    exit(1)

# Lê config actual
with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

# Mostra calibrações que vamos preservar
areas = [k for k in cfg if "area" in k or "regiao" in k]
print(f"📐 Calibrações encontradas (preservadas): {len(areas)}")
for a in areas:
    print(f"   ✓ {a}")
print()

# Adiciona apenas as flags que ainda não existem
adicionadas = 0
ja_existiam = 0
for chave, valor in NOVAS_FLAGS.items():
    if chave not in cfg:
        cfg[chave] = valor
        adicionadas += 1
        print(f"➕ Adicionado: {chave} = {valor}")
    else:
        ja_existiam += 1
        print(f"✓  Já existe:  {chave} = {cfg[chave]}")

# Grava
with open(CONFIG, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=4)

print()
print(f"✅ {adicionadas} flags novas adicionadas | {ja_existiam} já existiam")
print(f"   Calibrações preservadas. Podes correr o bot!")
print()
print(f"💡 Para activar a inteligência, edita {CONFIG} e muda:")
print(f"   'hot_cold_detection': false → true")
