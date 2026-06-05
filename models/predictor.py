# models/predictor.py
import pandas as pd
from joblib import load
import os
from typing import Tuple, Optional

MODELO_PATH = "models/modelo.pkl"
_cache: dict = {}


def carregar_modelo() -> Optional[dict]:
    if "pacote" not in _cache:
        if not os.path.exists(MODELO_PATH):
            print(f"❌ Modelo não encontrado: {MODELO_PATH}")
            return None
        _cache["pacote"] = load(MODELO_PATH)
        print("✅ Modelo carregado do disco.")
    return _cache["pacote"]


def prever(lista_multiplicadores: list) -> Tuple[int, float]:
    """
    lista_multiplicadores[0] = mais recente (padrão Aviator).
    Retorna (previsao, confianca).
    """
    pacote = carregar_modelo()
    if pacote is None:
        return 0, 0.0

    pipeline     = pacote["pipeline"]
    feature_cols = pacote["features"]
    n            = pacote["n"]

    # Precisa de n+1 valores (índice 0 = actual, 1..n = histórico)
    if len(lista_multiplicadores) < n + 1:
        print(f"⚠️ Lista insuficiente: {len(lista_multiplicadores)} < {n + 1} necessários.")
        return 0, 0.0

    # lista[0] = mais recente → lista[1] = rodada anterior, lista[2] = 2 atrás, etc.
    row = {}
    serie_vals = []
    for i in range(1, n + 1):
        row[f"ant_{i}"] = lista_multiplicadores[i]
        serie_vals.append(lista_multiplicadores[i])

    serie = pd.Series(serie_vals)
    row["media"]    = serie.mean()
    row["desvio"]   = serie.std()
    row["tendencia"]= lista_multiplicadores[1] - row["media"]
    row["max_n"]    = serie.max()
    row["min_n"]    = serie.min()
    row["azuis_n"]  = (serie < 2.0).sum()

    X       = pd.DataFrame([row])[feature_cols]
    probas  = pipeline.predict_proba(X)[0]
    previsao = int(probas[1] >= 0.5)
    return previsao, float(probas[1])
