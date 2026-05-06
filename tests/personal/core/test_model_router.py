"""Tests for SmartModelRouter."""
import pytest

from cuga.personal.core.model_router import SmartModelRouter


class TestSmartModelRouter:
    @pytest.fixture
    def router(self):
        return SmartModelRouter(cheap_model="cheap-llm", expensive_model="expensive-llm")

    def test_short_simple_is_cheap(self, router):
        assert router.classify("Hi") == "cheap"
        assert router.classify("What time is it?") == "cheap"

    def test_long_message_is_expensive(self, router):
        long_msg = " ".join(["word"] * 40)
        assert router.classify(long_msg) == "expensive"

    def test_complex_keyword_is_expensive(self, router):
        for msg in [
            "analyze the sales figures",
            "compare these two options",
            "implement a new workflow",
            "generate a detailed report",
        ]:
            assert router.classify(msg) == "expensive", f"Expected expensive for: {msg}"

    def test_simple_keyword_is_cheap(self, router):
        assert router.classify("yes") == "cheap"
        assert router.classify("ok thanks") == "cheap"
        assert router.classify("list skills") == "cheap"

    def test_message_with_url_is_expensive(self, router):
        assert router.classify("check https://example.com for me") == "expensive"

    def test_get_model_config_cheap(self, router):
        config = router.get_model_config("cheap")
        assert config["model"] == "cheap-llm"

    def test_get_model_config_expensive(self, router):
        config = router.get_model_config("expensive")
        assert config["model"] == "expensive-llm"

    def test_disabled_router_always_returns_expensive(self):
        router = SmartModelRouter(enabled=False, cheap_model="c", expensive_model="e")
        assert router.classify("Hi") == "expensive"
