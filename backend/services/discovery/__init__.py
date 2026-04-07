from .classifier_validation import (
    LabeledDiscoveryCandidate,
    EvaluationMetrics,
    ClassifierAcceptanceGate,
    ClassifierResponse,
)

try:
    from .service import AutoDiscoveryService, DiscoveryResponse
except ModuleNotFoundError:  # pragma: no cover - local test env may not install optional deps
    AutoDiscoveryService = None
    DiscoveryResponse = None

__all__ = [
    "AutoDiscoveryService",
    "DiscoveryResponse",
    "LabeledDiscoveryCandidate",
    "EvaluationMetrics",
    "ClassifierAcceptanceGate",
    "ClassifierResponse",
]
