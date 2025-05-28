import unittest
from unittest.mock import MagicMock, AsyncMock
import json
import asyncio # Required for async generator testing

# Functions/Classes to test
from webscout.Provider.OPENAI.api import handle_streaming_response, handle_non_streaming_response, APIError, clean_text
# Utility classes for constructing mock provider responses
from webscout.Provider.OPENAI.utils import (
    ChatCompletion, ChatCompletionMessage, Choice, CompletionUsage,
    ChatCompletionChunk, ChoiceDelta
)

# A helper function to consume an async generator (like StreamingResponse's content)
async def consume_async_generator(agen):
    return [item async for item in agen]

class TestApiResponseHandlers(unittest.TestCase):

    def setUp(self):
        self.provider_mock = MagicMock()
        self.params = {
            "model": "test_model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True # Default to stream, override for non-streaming
        }
        self.request_id = "test-req-id"
        self.start_time = 0.0 # For non-streaming

    async def test_handle_streaming_response_success(self):
        # Mock provider's streaming response
        async def mock_stream():
            yield ChatCompletionChunk(
                id=self.request_id,
                choices=[Choice(index=0, delta=ChoiceDelta(role="assistant", content="Hello "), finish_reason=None)],
                model=self.params["model"], created=123
            )
            yield ChatCompletionChunk(
                id=self.request_id,
                choices=[Choice(index=0, delta=ChoiceDelta(content="World!"), finish_reason=None)],
                model=self.params["model"], created=123
            )
        
        self.provider_mock.chat.completions.create = MagicMock(return_value=mock_stream())
        
        response = await handle_streaming_response(self.provider_mock, self.params, self.request_id)
        
        # Consume the streaming response
        # The response object from handle_streaming_response is a StreamingResponse
        # Its content is an async generator.
        content_items = await consume_async_generator(response.body_iterator)
        
        # Decode from bytes to string and then parse JSON
        results = []
        for item_bytes in content_items:
            item_str = item_bytes.decode('utf-8').strip()
            if item_str.startswith("data: "):
                data_part = item_str[len("data: "):]
                if data_part == "[DONE]":
                    results.append(data_part)
                else:
                    results.append(json.loads(data_part))
            # Handle potential empty strings if any yielded by stream processing
            elif not item_str: 
                continue
            else: # Should not happen with correct SSE formatting
                results.append(item_str)


        self.assertEqual(len(results), 3) # Two data chunks + [DONE]
        self.assertEqual(results[0]['choices'][0]['delta']['content'], "Hello ")
        self.assertEqual(results[1]['choices'][0]['delta']['content'], "World!")
        self.assertEqual(results[2], "[DONE]")

    async def test_handle_streaming_response_provider_error_chunk(self):
        # Mock provider yielding an error chunk
        async def mock_error_stream():
            yield ChatCompletionChunk(
                id=self.request_id,
                choices=[Choice(index=0, delta=ChoiceDelta(content="Provider error from stream"), finish_reason="error")],
                model=self.params["model"], created=123, system_fingerprint="provider_error"
            )

        self.provider_mock.chat.completions.create = MagicMock(return_value=mock_error_stream())

        response = await handle_streaming_response(self.provider_mock, self.params, self.request_id)
        content_items = await consume_async_generator(response.body_iterator)

        results = []
        for item_bytes in content_items:
            item_str = item_bytes.decode('utf-8').strip()
            if item_str.startswith("data: "):
                data_part = item_str[len("data: "):]
                if data_part == "[DONE]":
                    results.append(data_part)
                else:
                    results.append(json.loads(data_part))
            elif not item_str:
                continue
            else:
                results.append(item_str)

        self.assertEqual(len(results), 2) # Error chunk + [DONE]
        self.assertIn("error", results[0])
        self.assertEqual(results[0]["error"]["message"], "Provider error from stream")
        self.assertEqual(results[0]["error"]["type"], "provider_error")
        self.assertEqual(results[0]["error"]["code"], "streaming_provider_error")
        self.assertEqual(results[1], "[DONE]")

    async def test_handle_non_streaming_response_success(self):
        self.params["stream"] = False
        mock_completion = ChatCompletion(
            id=self.request_id,
            choices=[Choice(index=0, message=ChatCompletionMessage(role="assistant", content="Non-streaming success."), finish_reason="stop")],
            model=self.params["model"], created=123,
            usage=CompletionUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        )
        self.provider_mock.chat.completions.create = MagicMock(return_value=mock_completion)

        result = await handle_non_streaming_response(self.provider_mock, self.params, self.request_id, self.start_time)

        self.assertIsInstance(result, dict) # handle_non_streaming_response returns a dict (model_dump)
        self.assertEqual(result['choices'][0]['message']['content'], "Non-streaming success.")
        self.assertEqual(result['id'], self.request_id)

    async def test_handle_non_streaming_response_provider_ioerror(self):
        self.params["stream"] = False
        # Mock the provider to raise IOError, as BLACKBOXAI.py does
        self.provider_mock.chat.completions.create = MagicMock(side_effect=IOError("Test provider IOError from non-stream"))

        with self.assertRaises(APIError) as context:
            await handle_non_streaming_response(self.provider_mock, self.params, self.request_id, self.start_time)
        
        self.assertIn("Provider error: Test provider IOError from non-stream", context.exception.message)
        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.error_type, "provider_error")

    async def test_handle_streaming_response_api_internal_error(self):
        # Test an error happening inside handle_streaming_response's own logic, not from provider stream
        self.provider_mock.chat.completions.create = MagicMock(side_effect=Exception("Internal API error during stream setup"))

        response = await handle_streaming_response(self.provider_mock, self.params, self.request_id)
        content_items = await consume_async_generator(response.body_iterator)
        
        results = []
        for item_bytes in content_items:
            item_str = item_bytes.decode('utf-8').strip()
            if item_str.startswith("data: "):
                data_part = item_str[len("data: "):]
                if data_part == "[DONE]":
                    results.append(data_part)
                else:
                    results.append(json.loads(data_part))
            elif not item_str:
                continue
            else:
                results.append(item_str)

        self.assertEqual(len(results), 2) # Error data + [DONE]
        self.assertIn("error", results[0])
        self.assertEqual(results[0]["error"]["message"], "Internal API error during stream setup")
        self.assertEqual(results[0]["error"]["type"], "server_error")
        self.assertEqual(results[0]["error"]["code"], "streaming_error")
        self.assertEqual(results[1], "[DONE]")

    def test_clean_text_api_usage(self):
        # Example of how clean_text might be used, though it's tested more thoroughly in test_blackboxai.py
        raw_error = "Error with \x00null byte and \x01control char."
        cleaned_error = clean_text(raw_error)
        self.assertEqual(cleaned_error, "Error with null byte and control char.")


# This allows running the async tests with unittest
if __name__ == '__main__':
    # For running async tests, unittest.main() works directly in Python 3.8+
    # For older versions or specific runners, you might need an async test runner.
    # However, the standard library's unittest TestLoader and TextTestRunner
    # can discover and run coroutine test methods defined with `async def`.
    unittest.main()
