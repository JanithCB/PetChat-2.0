from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

UNKNOWN_RESULT: Dict[str, Any] = {
    "label": "unknown",
    "confidence": 0.0,
    "ok": False,
    "reason": "unknown",
}

_ALLOWED_LABELS = {
    "happy",
    "calm",
    "sad",
    "angry",
    "anxious",
    "stressed",
    "confused",
}


class EmotionClassifier:
    """
    Thin wrapper around a Hugging Face sequence-classification model
    stored in src/core/emotion_model/.
    """

    def __init__(self, model_path: str | Path):
        self.model_path = str(model_path)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        logger.info("Loading emotion model from: %s", self.model_path)
        logger.info("Emotion classifier device: %s", self.device)

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        self.model.to(self.device)
        self.model.eval()

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Predict emotion for a given text string.

        Returns:
            {
                "label": "sad",
                "confidence": 0.91,
                "ok": True,
                "reason": None,
            }
        """
        clean_text = str(text or "").strip()
        if not clean_text:
            return {
                "label": "unknown",
                "confidence": 0.0,
                "ok": False,
                "reason": "empty_text",
            }

        inputs = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)

        pred_id = int(torch.argmax(probs, dim=-1).item())
        confidence = float(probs[0][pred_id].item())
        label = self._label_from_id(pred_id)

        if label not in _ALLOWED_LABELS:
            logger.warning("Unexpected emotion label from model: %s", label)
            return {
                "label": "unknown",
                "confidence": confidence,
                "ok": False,
                "reason": "invalid_label",
            }

        return {
            "label": label,
            "confidence": confidence,
            "ok": True,
            "reason": None,
        }

    def _label_from_id(self, pred_id: int) -> str:
        """
        Safely map prediction id back to a label from model config.
        """
        id2label = getattr(self.model.config, "id2label", None)

        if isinstance(id2label, dict):
            if pred_id in id2label:
                return self._normalize_label(id2label[pred_id])
            if str(pred_id) in id2label:
                return self._normalize_label(id2label[str(pred_id)])

        return "unknown"

    @staticmethod
    def _normalize_label(label: Any) -> str:
        """
        Normalize label strings from model config into a clean lowercase form.
        """
        if label is None:
            return "unknown"

        normalized = str(label).strip().lower()
        normalized = normalized.replace("fear", "anxious")
        normalized = normalized.replace("anger", "angry")

        return normalized if normalized else "unknown"


_classifier: Optional[EmotionClassifier] = None


def _default_model_dir() -> str:
    """
    Default model folder:
    src/core/emotion_model/
    """
    return str(Path(__file__).resolve().parent / "emotion_model")


def _classifier_enabled() -> bool:
    """
    Read the config flag lazily to avoid hard dependency issues during import.
    """
    try:
        from src.config import USE_EMOTION_CLASSIFIER  # noqa: PLC0415

        return bool(USE_EMOTION_CLASSIFIER)
    except Exception:
        return True


def get_classifier(model_dir: Optional[str] = None) -> Optional[EmotionClassifier]:
    """
    Return the singleton classifier instance.
    Load it only once.
    Return None if the model cannot be loaded.
    """
    global _classifier

    if not _classifier_enabled():
        logger.info("Emotion classifier disabled by config.")
        return None

    if _classifier is not None:
        return _classifier

    model_dir = model_dir or _default_model_dir()

    if not os.path.isdir(model_dir):
        logger.warning("Emotion model directory not found: %s", model_dir)
        return None

    try:
        _classifier = EmotionClassifier(model_dir)
        return _classifier
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load emotion classifier: %s", exc)
        return None


def classify_emotion(text: str, model_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Safe helper for the PetChat pipeline.

    This function must never raise exceptions to callers.
    If the model is unavailable or prediction fails, it returns
    an 'unknown' result so the rest of the pipeline can continue.
    """
    clean_text = str(text or "").strip()
    if not clean_text:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "ok": False,
            "reason": "empty_text",
        }

    if not _classifier_enabled():
        return {
            "label": "unknown",
            "confidence": 0.0,
            "ok": False,
            "reason": "disabled",
        }

    try:
        clf = get_classifier(model_dir)
        if clf is None:
            return {
                "label": "unknown",
                "confidence": 0.0,
                "ok": False,
                "reason": "model_unavailable",
            }

        result = clf.predict(clean_text)

        if not isinstance(result, dict):
            return {
                "label": "unknown",
                "confidence": 0.0,
                "ok": False,
                "reason": "invalid_result",
            }

        label = str(result.get("label", "unknown")).strip().lower()
        confidence = float(result.get("confidence", 0.0) or 0.0)
        ok = bool(result.get("ok", False))
        reason = result.get("reason")

        if label not in _ALLOWED_LABELS and label != "unknown":
            return {
                "label": "unknown",
                "confidence": confidence,
                "ok": False,
                "reason": "invalid_label",
            }

        return {
            "label": label,
            "confidence": max(0.0, min(confidence, 1.0)),
            "ok": ok,
            "reason": reason,
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning("Emotion prediction error: %s", exc)
        return {
            "label": "unknown",
            "confidence": 0.0,
            "ok": False,
            "reason": "prediction_error",
        }


def get_emotion_label(text: str, model_dir: Optional[str] = None) -> str:
    """
    Backward-compatible helper for code that only wants the label string.
    """
    result = classify_emotion(text, model_dir=model_dir)
    return str(result.get("label", "unknown")).strip().lower()