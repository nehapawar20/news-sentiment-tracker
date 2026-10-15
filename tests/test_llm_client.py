import json

import pytest
import requests
import responses

from pipeline.enrichment.llm_client import LLMClient, LLMUnavailableError

BASE = "http://localhost:11434"
URL = f"{BASE}/api/chat"


def ollama_reply(text="hello"):
    return {
        "message": {"role": "assistant", "content": text},
        "prompt_eval_count": 11,
        "eval_count": 5,
    }


@responses.activate
def test_complete_returns_text_and_usage():
    responses.add(responses.POST, URL, json=ollama_reply("hello"), status=200)
    client = LLMClient(model="test-model", base_url=BASE)

    text, usage = client.complete("system prompt", "user prompt")

    assert text == "hello"
    assert usage == {"input_tokens": 11, "output_tokens": 5}


@responses.activate
def test_complete_sends_model_and_prompts():
    responses.add(responses.POST, URL, json=ollama_reply(), status=200)
    client = LLMClient(model="test-model", base_url=BASE, max_tokens=123)

    client.complete("system prompt", "user prompt")

    sent = json.loads(responses.calls[0].request.body)
    assert sent["model"] == "test-model"
    assert sent["stream"] is False
    assert sent["options"]["temperature"] == 0
    assert sent["options"]["num_predict"] == 123
    assert sent["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert "format" not in sent


@responses.activate
def test_memory_limits_are_sent():
    responses.add(responses.POST, URL, json=ollama_reply(), status=200)
    client = LLMClient(model="m", base_url=BASE)

    client.complete("s", "u")

    sent = json.loads(responses.calls[0].request.body)
    assert sent["keep_alive"] == "30s"
    assert sent["options"]["num_ctx"] == 2048


@responses.activate
def test_json_mode_asks_for_json():
    responses.add(responses.POST, URL, json=ollama_reply("{}"), status=200)
    client = LLMClient(model="m", base_url=BASE)

    client.complete("s", "u", json_mode=True)

    sent = json.loads(responses.calls[0].request.body)
    assert sent["format"] == "json"


@responses.activate
def test_connection_error_becomes_llm_unavailable():
    responses.add(responses.POST, URL, body=requests.ConnectionError("refused"))
    client = LLMClient(model="m", base_url=BASE)

    with pytest.raises(LLMUnavailableError):
        client.complete("s", "u")


@responses.activate
def test_missing_model_becomes_llm_unavailable():
    responses.add(responses.POST, URL, json={"error": "model not found"}, status=404)
    client = LLMClient(model="m", base_url=BASE)

    with pytest.raises(LLMUnavailableError):
        client.complete("s", "u")


def test_defaults_come_from_settings(settings):
    settings.LLM_MODEL = "my-model"
    settings.LLM_BASE_URL = "http://example.local:1234/"

    client = LLMClient()

    assert client.model == "my-model"
    assert client.base_url == "http://example.local:1234"

@responses.activate
def test_temperature_can_be_overridden():
    responses.add(responses.POST, URL, json=ollama_reply(), status=200)
    client = LLMClient(model="m", base_url=BASE)

    client.complete("s", "u", temperature=0.3)

    sent = json.loads(responses.calls[0].request.body)
    assert sent["options"]["temperature"] == 0.3