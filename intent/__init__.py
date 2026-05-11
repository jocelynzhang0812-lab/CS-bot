"""意图模块 —— 分类器 + 槽位提取器"""
from .classifier import IntentClassifier, INTENT_LABELS
from .slot_extractor import SlotExtractor

__all__ = [
    "IntentClassifier",
    "INTENT_LABELS",
    "SlotExtractor",
]