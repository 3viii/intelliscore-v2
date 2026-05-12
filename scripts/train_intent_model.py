"""
Train Intent Classifier — TF-IDF + Logistic Regression
=======================================================
Lightweight ML model for classifying debt-collection call utterances into:
    PTP | Partial Payment | Refusal | Already Paid | Ambiguous

Usage:
    python scripts/train_intent_model.py

Outputs:
    models/intent_classifier.pkl   - trained sklearn Pipeline (vectorizer + LR)
    models/intent_metrics.json     - classification report + confusion matrix
    models/confusion_matrix.png    - visual confusion matrix
    models/classification_report.txt - text classification report
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_PATH = "data/intent_training_data.csv"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "intent_classifier.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "intent_metrics.json")
CM_PLOT_PATH = os.path.join(MODEL_DIR, "confusion_matrix.png")
REPORT_PATH = os.path.join(MODEL_DIR, "classification_report.txt")

LABEL_ORDER = ["PTP", "Partial Payment", "Refusal", "Already Paid", "Ambiguous"]
RANDOM_STATE = 42


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)

    # -----------------------------------------------------------------------
    # 1. Load dataset
    # -----------------------------------------------------------------------
    print(f"[TRAIN] Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["text", "label"]).reset_index(drop=True)
    print(f"[TRAIN] Total samples: {len(df)}")
    print(f"[TRAIN] Class distribution:\n{df['label'].value_counts().to_string()}\n")

    X = df["text"].astype(str).values
    y = df["label"].astype(str).values

    # -----------------------------------------------------------------------
    # 2. Train/test split (stratified)
    # -----------------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[TRAIN] Train: {len(X_train)} | Test: {len(X_test)}")

    # -----------------------------------------------------------------------
    # 3. Build pipeline (TF-IDF + Logistic Regression)
    # -----------------------------------------------------------------------
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
            lowercase=True,
            strip_accents="unicode",
        )),
        ("clf", LogisticRegression(
            max_iter=2000,
            C=1.5,
            class_weight="balanced",
            solver="lbfgs",
            random_state=RANDOM_STATE,
        )),
    ])

    print("[TRAIN] Training pipeline (TF-IDF + Logistic Regression)...")
    pipeline.fit(X_train, y_train)

    # -----------------------------------------------------------------------
    # 4. Cross-validation
    # -----------------------------------------------------------------------
    cv_scores = cross_val_score(pipeline, X, y, cv=5, scoring="f1_macro")
    print(f"[TRAIN] 5-fold CV f1_macro: "
          f"mean={cv_scores.mean():.3f}  std={cv_scores.std():.3f}")

    # -----------------------------------------------------------------------
    # 5. Test-set evaluation
    # -----------------------------------------------------------------------
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="macro")

    print(f"\n[TRAIN] Test accuracy:  {acc:.3f}")
    print(f"[TRAIN] Test f1_macro:  {f1:.3f}\n")

    report_text = classification_report(
        y_test, y_pred, labels=LABEL_ORDER, digits=3, zero_division=0
    )
    print(report_text)

    cm = confusion_matrix(y_test, y_pred, labels=LABEL_ORDER)

    # -----------------------------------------------------------------------
    # 6. Save plot
    # -----------------------------------------------------------------------
    plt.figure(figsize=(7, 5.5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=LABEL_ORDER, yticklabels=LABEL_ORDER,
        cbar=False, linewidths=0.5, linecolor="white",
    )
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title(f"Intent Classifier — Confusion Matrix\nAcc={acc:.2f}  F1={f1:.2f}")
    plt.xticks(rotation=20, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(CM_PLOT_PATH, dpi=120)
    plt.close()
    print(f"[TRAIN] Confusion matrix plot -> {CM_PLOT_PATH}")

    # -----------------------------------------------------------------------
    # 7. Save artifacts
    # -----------------------------------------------------------------------
    joblib.dump(pipeline, MODEL_PATH)
    print(f"[TRAIN] Model saved        -> {MODEL_PATH}")

    metrics = {
        "model_type": "TF-IDF + Logistic Regression",
        "classes": LABEL_ORDER,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "accuracy": float(acc),
        "f1_macro": float(f1),
        "cv_f1_macro_mean": float(cv_scores.mean()),
        "cv_f1_macro_std": float(cv_scores.std()),
        "confusion_matrix": cm.tolist(),
        "labels_order": LABEL_ORDER,
        "classification_report": classification_report(
            y_test, y_pred, labels=LABEL_ORDER, digits=3,
            output_dict=True, zero_division=0,
        ),
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[TRAIN] Metrics saved      -> {METRICS_PATH}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("Intent Classifier — Classification Report\n")
        f.write("==========================================\n\n")
        f.write(f"Model: TF-IDF (1-2 grams) + Logistic Regression\n")
        f.write(f"Train: {len(X_train)} samples | Test: {len(X_test)} samples\n\n")
        f.write(f"Test accuracy: {acc:.3f}\n")
        f.write(f"Test f1_macro: {f1:.3f}\n")
        f.write(f"5-fold CV f1_macro: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})\n\n")
        f.write(report_text)
        f.write("\n\nConfusion matrix (rows=actual, cols=predicted)\n")
        f.write("Labels: " + ", ".join(LABEL_ORDER) + "\n")
        f.write(str(cm))
    print(f"[TRAIN] Report saved       -> {REPORT_PATH}")

    # -----------------------------------------------------------------------
    # 8. Sanity-check predictions
    # -----------------------------------------------------------------------
    print("\n[TRAIN] Sample predictions:")
    samples = [
        "I will pay the full amount tomorrow",
        "I can pay only half now",
        "I will not pay anything",
        "I already paid last week",
        "Call me later I am busy",
    ]
    probs = pipeline.predict_proba(samples)
    preds = pipeline.predict(samples)
    for s, p, pr in zip(samples, preds, probs):
        conf = float(np.max(pr))
        print(f"  '{s[:40]}...'  ->  {p:<16}  (conf={conf:.2f})")

    print("\n[TRAIN] Done.")


if __name__ == "__main__":
    main()
