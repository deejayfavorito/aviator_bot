# models/treinamento.py
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
from joblib import dump

MODELO_PATH   = "models/modelo.pkl"
HISTORICO_PATH = "data/historico.csv"


def carregar_dados_csv(caminho: str = HISTORICO_PATH) -> pd.DataFrame:
    if not os.path.exists(caminho):
        print("⚠️ Histórico não encontrado.")
        return pd.DataFrame(columns=["multiplicador"])
    try:
        df = pd.read_csv(
            caminho, header=None,
            names=["timestamp", "tipo", "valor"],
            on_bad_lines="skip"
        )
        # Aceita eventos de crash real ou registos de multiplicador
        df = df[df["tipo"].isin(["cashout_ok", "crash_perdeu", "crash_registado"])]
        df["multiplicador"] = (
            df["valor"].astype(str)
            .str.replace("x", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )
        df = df.dropna(subset=["multiplicador"]).reset_index(drop=True)
        return df[["multiplicador"]]
    except Exception as e:
        print(f"⚠️ Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=["multiplicador"])


def preparar_features(df: pd.DataFrame, n: int = 8):
    """
    Gera features com janela de N rodadas.
    lista[0] = mais recente — shift(1) é a rodada anterior.
    """
    df = df.copy()
    df["target"] = (df["multiplicador"] >= 2.0).astype(int)

    cols = []
    for i in range(1, n + 1):
        col = f"ant_{i}"
        df[col] = df["multiplicador"].shift(i)
        cols.append(col)

    df["media"]    = df[cols].mean(axis=1)
    df["desvio"]   = df[cols].std(axis=1)
    df["tendencia"]= df["ant_1"] - df["media"]
    df["max_n"]    = df[cols].max(axis=1)
    df["min_n"]    = df[cols].min(axis=1)
    df["azuis_n"]  = (df[cols] < 2.0).sum(axis=1)

    feature_cols = cols + ["media", "desvio", "tendencia", "max_n", "min_n", "azuis_n"]
    df = df.dropna()
    return df[feature_cols], df["target"], feature_cols


def treinar_modelo(n_features: int = 8) -> object:
    df = carregar_dados_csv()
    if len(df) < 20:
        print(f"⚠️ Dados insuficientes ({len(df)} linhas). Mínimo: 20.")
        return None

    X, y, feature_cols = preparar_features(df, n=n_features)
    print(f"📊 Dataset: {len(X)} amostras | {len(feature_cols)} features")
    print(f"   Distribuição: {y.value_counts().to_dict()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",  # corrige desequilíbrio de classes
            random_state=42
        ))
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("\n📈 Avaliação do modelo:")
    print(classification_report(y_test, y_pred, target_names=["Crash (<2x)", "Alto (≥2x)"]))

    os.makedirs("models", exist_ok=True)
    dump({"pipeline": pipeline, "features": feature_cols, "n": n_features}, MODELO_PATH)
    print(f"✅ Modelo guardado em {MODELO_PATH}")
    return pipeline


if __name__ == "__main__":
    treinar_modelo()
