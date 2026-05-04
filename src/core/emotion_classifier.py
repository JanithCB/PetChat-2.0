from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import torch
except Exception:  # noqa: BLE001
    torch = None  # type: ignore[assignment]

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except Exception:  # noqa: BLE001
    AutoModelForSequenceClassification = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]


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


_LABEL_ALIASES = {
    "fear": "anxious",
    "fearful": "anxious",
    "anxiety": "anxious",
    "anger": "angry",
    "frustrated": "angry",
    "frustration": "angry",
    "stress": "stressed",
    "confusion": "confused",
    "joy": "happy",
    "neutral": "calm",
    "content": "calm",
    "relaxed": "calm",
}


_MIN_TEXT_CHARS = 4
_MIN_TEXT_WORDS = 1
_SHORT_TEXT_WORD_LIMIT = 2
_DEFAULT_MAX_LENGTH = 128
_DEFAULT_MIN_CONFIDENCE = 0.48
_DEFAULT_MIN_MARGIN = 0.08


class EmotionClassifier:
    """
    Thin wrapper around a Hugging Face sequence-classification model
    stored in src/core/emotion_model/.
    """

    def __init__(self, model_path: str | Path):
        if torch is None or AutoTokenizer is None or AutoModelForSequenceClassification is None:
            raise RuntimeError("emotion_classifier_dependencies_unavailable")

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
        clean_text = _clean_text(text)
        if not clean_text:
            return _result("unknown", 0.0, False, "empty_text")

        if _should_skip_classification(clean_text):
            return _result("unknown", 0.0, False, "text_too_short")

        inputs = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=_max_length(),
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)

        top_probs, top_ids = torch.topk(probs, k=min(2, probs.shape[-1]), dim=-1)
        pred_id = int(top_ids[0][0].item())
        confidence = float(top_probs[0][0].item())
        second_confidence = float(top_probs[0][1].item()) if top_probs.shape[-1] > 1 else 0.0
        margin = confidence - second_confidence

        label = self._label_from_id(pred_id)

        if label not in _ALLOWED_LABELS:
            logger.warning("Unexpected emotion label from model: %s", label)
            return _result("unknown", confidence, False, "invalid_label")

        if confidence < _min_confidence():
            return _result("unknown", confidence, False, "low_confidence")

        if margin < _min_margin():
            return _result("unknown", confidence, False, "ambiguous_prediction")

        return _result(label, confidence, True, None)

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
        normalized = normalized.replace("-", "_").replace(" ", "_")
        normalized = normalized.removeprefix("label_")
        normalized = _LABEL_ALIASES.get(normalized, normalized)

        return normalized if normalized else "unknown"


_classifier: Optional[EmotionClassifier] = None


def _result(label: str, confidence: float, ok: bool, reason: Any) -> Dict[str, Any]:
    safe_label = str(label or "unknown").strip().lower() or "unknown"
    safe_confidence = max(0.0, min(float(confidence or 0.0), 1.0))
    return {
        "label": safe_label,
        "confidence": safe_confidence,
        "ok": bool(ok),
        "reason": reason,
    }


def _clean_text(text: str | None) -> str:
    return " ".join(str(text or "").strip().split())


def _word_count(text: str) -> int:
    return len([part for part in text.split(" ") if part.strip()])


def _should_skip_classification(text: str) -> bool:
    clean_text = _clean_text(text)
    if not clean_text:
        return True

    if len(clean_text) < _MIN_TEXT_CHARS:
        return True

    words = _word_count(clean_text)
    if words < _MIN_TEXT_WORDS:
        return True

    short_casual = {
        "hi",
        "hello",
        "hey",
        "yo",
        "ok",
        "okay",
        "kk",
        "k",
        "cool",
        "nice",
        "thanks",
        "thank you",
        "thx",
        "sup",
        "hru",
        "how are you",
    }
    if clean_text.lower() in short_casual:
        return True

    if words <= _SHORT_TEXT_WORD_LIMIT and not any(ch in clean_text for ch in ".!?"):
        return True

    return False


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


def _min_confidence() -> float:
    try:
        from src.config import EMOTION_MIN_CONFIDENCE  # noqa: PLC0415

        value = float(EMOTION_MIN_CONFIDENCE)
        return max(0.0, min(value, 1.0))
    except Exception:
        return _DEFAULT_MIN_CONFIDENCE


def _min_margin() -> float:
    try:
        from src.config import EMOTION_MIN_MARGIN  # noqa: PLC0415

        value = float(EMOTION_MIN_MARGIN)
        return max(0.0, min(value, 1.0))
    except Exception:
        return _DEFAULT_MIN_MARGIN


def _max_length() -> int:
    try:
        from src.config import EMOTION_MAX_LENGTH  # noqa: PLC0415

        value = int(EMOTION_MAX_LENGTH)
        return value if value > 8 else _DEFAULT_MAX_LENGTH
    except Exception:
        return _DEFAULT_MAX_LENGTH


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

    if torch is None or AutoTokenizer is None or AutoModelForSequenceClassification is None:
        logger.warning("Emotion classifier dependencies are unavailable.")
        return None

    model_dir = model_dir or _default_model_dir()

    if not os.path.isdir(model_dir):
        logger.warning("Emotion model directory not found: %s", model_dir)
        return None

    required_files = [
        os.path.join(model_dir, "config.json"),
    ]
    if not all(os.path.exists(path) for path in required_files):
        logger.warning("Emotion model directory is missing required files: %s", model_dir)
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
    clean_text = _clean_text(text)
    if not clean_text:
        return _result("unknown", 0.0, False, "empty_text")

    if not _classifier_enabled():
        return _result("unknown", 0.0, False, "disabled")

    if _should_skip_classification(clean_text):
        return _result("unknown", 0.0, False, "text_too_short")

    try:
        clf = get_classifier(model_dir)
        if clf is None:
            return _result("unknown", 0.0, False, "model_unavailable")

        result = clf.predict(clean_text)

        if not isinstance(result, dict):
            return _result("unknown", 0.0, False, "invalid_result")

        label = str(result.get("label", "unknown")).strip().lower()
        confidence = float(result.get("confidence", 0.0) or 0.0)
        ok = bool(result.get("ok", False))
        reason = result.get("reason")

        if label not in _ALLOWED_LABELS and label != "unknown":
            return _result("unknown", confidence, False, "invalid_label")

        return _result(label, confidence, ok, reason)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Emotion prediction error: %s", exc)
        return _result("unknown", 0.0, False, "prediction_error")


def get_emotion_label(text: str, model_dir: Optional[str] = None) -> str:
    """
    Backward-compatible helper for code that only wants the label string.
    """
    result = classify_emotion(text, model_dir=model_dir)
    return str(result.get("label", "unknown")).strip().lower()