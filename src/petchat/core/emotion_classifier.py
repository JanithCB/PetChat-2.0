"""
core/emotion_classifier.py — Optional ML emotion classifier for PetChat-2.0.

This module is intentionally thin.  It wraps an optional transformer-based
classifier (e.g. a GoEmotions fine-tuned BERT) and exposes a single public
function:

    predict_emotions(text) -> dict

If the required dependencies (transformers, torch, or the model weights) are
not installed, the function returns {} so that esc_support.py falls back to
its regex-based detection without any error.

Upgrade path
------------
1. Install the model:
       pip install transformers torch
       # model is downloaded on first use to ~/.cache/huggingface/

2. Set the environment variable (or update _MODEL_NAME below):
       EMOTION_CLASSIFIER_MODEL=SamLowe/roberta-base-go_emotions

3. Restart the app — predict_emotions() will use the real model automatically.

Public API
----------
predict_emotions(text: str) -> dict
    Returns {} when the classifier is unavailable.
    Returns {"primary": str, "scores": dict[str, float]} when it works.

is_available() -> bool
    True when the transformer backend loaded successfully.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MODEL_NAME: str = os.environ.get(
    "EMOTION_CLASSIFIER_MODEL",
    "SamLowe/roberta-base-go_emotions",
)

# Map GoEmotions 28-class labels to the 10 emotions esc_support understands.
# Keys are GoEmotions label strings; values are esc_support emotion names.
_LABEL_MAP: dict[str, str] = {
    # sadness family
    "sadness":        "sadness",
    "grief":          "grief",
    "disappointment": "sadness",
    "remorse":        "guilt",
    # anxiety / fear family
    "fear":           "anxiety",
    "nervousness":    "anxiety",
    # anger family
    "anger":          "anger",
    "annoyance":      "anger",
    "disgust":        "anger",
    # shame / guilt
    "embarrassment":  "shame",
    "guilt":          "guilt",
    # overwhelm / stress
    "confusion":      "confusion",
    # positive / neutral (not used by planner but keep for score export)
    "joy":            "joy",
    "excitement":     "joy",
    "amusement":      "joy",
    "admiration":     "joy",
    "gratitude":      "joy",
    "love":           "joy",
    "caring":         "joy",
    "optimism":       "hope",
    "pride":          "hope",
    "relief":         "relief",
    "surprise":       "surprise",
    "curiosity":      "curiosity",
    "realization":    "curiosity",
    "approval":       "joy",
    "desire":         "longing",
    "disapproval":    "anger",
    "neutral":        "neutral",
}

# ---------------------------------------------------------------------------
# Lazy-load state
# ---------------------------------------------------------------------------

_pipeline: Any = None          # transformers pipeline object
_load_attempted: bool = False  # avoid repeated failed loads


def _try_load() -> None:
    """Attempt to load the classifier once; swallow all errors."""
    global _pipeline, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True
    try:
        from transformers import pipeline as hf_pipeline  # noqa: PLC0415

        logger.info("Loading emotion classifier: %s", _MODEL_NAME)
        _pipeline = hf_pipeline(
            task="text-classification",
            model=_MODEL_NAME,
            top_k=None,                  # return scores for ALL labels
            truncation=True,
            max_length=512,
        )
        logger.info("Emotion classifier loaded successfully.")
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Emotion classifier unavailable (%s). "
            "esc_support will use regex fallback.",
            exc,
        )
        _pipeline = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True when the transformer backend is ready."""
    _try_load()
    return _pipeline is not None


def predict_emotions(text: str) -> dict[str, Any]:
    """
    Predict emotions for text using the loaded transformer model.

    Returns
    -------
    {} when the classifier is unavailable or the input is empty.

    {"primary": str, "scores": dict[str, float]}
        primary : The single highest-confidence esc_support emotion label.
        scores  : Mapping of every esc_support emotion label to its
                  aggregated probability (labels collapsed via _LABEL_MAP).

    The caller (esc_support.detect_emotions) should treat {} as a signal
    to fall back to regex detection.
    """
    if not text or not text.strip():
        return {}

    _try_load()
    if _pipeline is None:
        return {}

    try:
        raw: list[dict[str, Any]] = _pipeline(text[:512])[0]
        # raw is a list of {"label": str, "score": float}
        return _aggregate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("predict_emotions failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _aggregate(raw: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Collapse the 28 GoEmotions labels into esc_support emotion names.

    Scores for the same target label are summed (not averaged) so that
    multiple GoEmotions labels mapping to "sadness" contribute together.
    """
    aggregated: dict[str, float] = {}

    for item in raw:
        go_label = item.get("label", "")
        score    = float(item.get("score", 0.0))
        target   = _LABEL_MAP.get(go_label, "neutral")
        aggregated[target] = aggregated.get(target, 0.0) + score

    if not aggregated:
        return {}

    # Normalise to [0, 1] so scores stay comparable regardless of label-map fan-out.
    total = sum(aggregated.values())
    if total > 0:
        aggregated = {k: round(v / total, 4) for k, v in aggregated.items()}

    primary = max(aggregated, key=lambda k: aggregated[k])

    return {
        "primary": primary,
        "scores":  aggregated,
    }
