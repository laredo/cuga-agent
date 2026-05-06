"""SmartModelRouter — routes messages to cheap or expensive LLM."""
import re
from typing import Dict


_COMPLEX_KEYWORDS = {
    "analyze", "analyse", "compare", "implement", "generate", "create",
    "design", "architect", "refactor", "migrate", "integrate", "explain",
    "summarize", "summarise", "evaluate", "investigate", "diagnose",
    "optimize", "optimise", "plan", "strategy",
}

_URL_RE = re.compile(r"https?://\S+")


class SmartModelRouter:
    """
    Heuristic complexity classifier.

    Inspired by Hermes smart_model_routing.py:
    - Short messages with no complex keywords → cheap model
    - Long messages, complex keywords, or URLs → expensive model
    """

    CHEAP_CHAR_LIMIT = 160
    CHEAP_WORD_LIMIT = 28

    def __init__(
        self,
        cheap_model: str = "",
        expensive_model: str = "",
        enabled: bool = True,
    ):
        self._cheap = cheap_model
        self._expensive = expensive_model
        self._enabled = enabled

    def classify(self, message: str) -> str:
        """Returns 'cheap' or 'expensive'."""
        if not self._enabled:
            return "expensive"

        if len(message) > self.CHEAP_CHAR_LIMIT:
            return "expensive"

        words = message.split()
        if len(words) > self.CHEAP_WORD_LIMIT:
            return "expensive"

        if _URL_RE.search(message):
            return "expensive"

        msg_words = {w.lower().rstrip(".,!?;:") for w in words}
        if msg_words & _COMPLEX_KEYWORDS:
            return "expensive"

        return "cheap"

    def get_model_config(self, classification: str) -> Dict[str, str]:
        """Return LLM config dict for the given classification."""
        model = self._cheap if classification == "cheap" else self._expensive
        return {"model": model}
