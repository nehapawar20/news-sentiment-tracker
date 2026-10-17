import json


def valid_reply(**changes) -> str:
    """A correct model reply, as JSON text. Pass keyword arguments to change fields."""
    data = {
        "sentiment": "positive",
        "score": 0.6,
        "topic": "business",
        "entities": ["Acme"],
        "summary": "Acme grew strongly.",
    }
    data.update(changes)
    return json.dumps(data)


class FakeLLM:
    """A stand-in for LLMClient that returns canned replies and records every call.

    replies: used one by one, in order. An Exception in the list is raised.
    default: used when the list runs out. If neither is left, the test fails loudly.
    """

    model = "fake-model"

    def __init__(self, replies=None, default=None):
        self.replies = list(replies or [])
        self.default = default
        self.calls = []

    def complete(self, system, user, json_mode=False, temperature=0.0):
        self.calls.append(
            {"user": user, "json_mode": json_mode, "temperature": temperature}
        )
        reply = self.replies.pop(0) if self.replies else self.default
        if reply is None:
            raise AssertionError("FakeLLM was called but has no reply left")
        if isinstance(reply, Exception):
            raise reply
        return reply, {"input_tokens": 10, "output_tokens": 5}