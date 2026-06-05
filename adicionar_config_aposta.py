"""
Adiciona os 3 novos parâmetros ao config.json sem mexer nas calibrações.
Uso: python adicionar_config_aposta.py
"""
import json
from pathlib import Path

CONFIG = Path("config/config.json")

NOVOS = {
    "aposta_base": 50.0,
    "aposta_limite_max": 500.0,
    "reset_apos_vitorias": 6,
}

if not CONFIG.exists():
    print("❌ config/config.json não encontrado.")
    print("   Vais ter que recalibrar todas as áreas.")
    exit(1)

with open(CONFIG) as f:
    cfg = json.load(f)

# Mostra calibrações que vamos preservar
areas = [k for k in cfg if "area" in k or "regiao" in k]
print(f"📐 Calibrações encontradas (preservadas): {len(areas)}")
for a in areas:
    print(f"   {a} = {cfg[a]}")

# Adiciona apenas os novos sem sobrescrever
adicionados = 0
for chave, valor in NOVOS.items():
    if chave not in cfg:
        cfg[chave] = valor
        adicionados += 1
        print(f"➕ Adicionado: {chave} = {valor}")
    else:
        print(f"✓  Já existe: {chave} = {cfg[chave]}")

# Garante limite de perda alto o suficiente para testes
if cfg.get("limite_perda", 0) < 3000:
    cfg["limite_perda"] = 3000.0
    print(f"⚙️  Atualizado: limite_perda = 3000.0")

with open(CONFIG, "w") as f:
    json.dump(cfg, f, indent=4)

print(f"\n✅ {adicionados} parâmetros adicionados ao config.json")
print(f"   Calibrações preservadas. Podes correr o bot!")
