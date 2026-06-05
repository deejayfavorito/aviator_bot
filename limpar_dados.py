"""
Limpa os dados de sessão sem perder calibrações nem histórico de multiplicadores.

Uso: python limpar_dados.py

Apaga:
  - data/estado_estrategia.json         (contador de perdas/ganhos)
  - data/estado_aposta_composta.json    (cadeia composta)
  - Reseta o ficheiro de banca (gestor)

Preserva:
  - config/config.json                   (calibrações + parâmetros)
  - data/historico.csv                   (histórico de multiplicadores)
"""
import os
import json
from pathlib import Path

DATA_DIR = Path("data")
APAGAR = [
    DATA_DIR / "estado_estrategia.json",
    DATA_DIR / "estado_aposta_composta.json",
    DATA_DIR / "banca.json",
    DATA_DIR / "sessao.json",
]

print("🧹 Limpeza de dados de sessão\n")

apagados = 0
for ficheiro in APAGAR:
    if ficheiro.exists():
        try:
            ficheiro.unlink()
            print(f"   ✅ Apagado: {ficheiro}")
            apagados += 1
        except Exception as e:
            print(f"   ❌ Erro ao apagar {ficheiro}: {e}")
    else:
        print(f"   ⏭️  Não existe: {ficheiro}")

# Procura outros ficheiros de banca ou perdas
for f in DATA_DIR.glob("*.json"):
    if "banca" in f.name.lower() or "perda" in f.name.lower():
        try:
            f.unlink()
            print(f"   ✅ Apagado: {f}")
            apagados += 1
        except Exception:
            pass

print(f"\n✨ {apagados} ficheiros apagados. Calibrações e histórico preservados.")
print("🚀 Podes correr: python main_autonomo.py")
