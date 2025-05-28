import unittest
from unittest.mock import patch, MagicMock
import requests # Import requests for exceptions
import codecs

# Classes to test
from webscout.Provider.OPENAI.BLACKBOXAI import BLACKBOXAI, Completions, clean_text
# Utility classes for constructing expected responses
from webscout.Provider.OPENAI.utils import (
    ChatCompletion, ChatCompletionMessage, Choice, CompletionUsage,
    ChatCompletionChunk, ChoiceDelta
)

class TestBlackboxAICompletions(unittest.TestCase):

    def setUp(self):
        self.client = BLACKBOXAI()
        self.completions = Completions(self.client)
        self.test_messages = [{"role": "user", "content": "Hello"}]
        self.model = "GPT-4.1" # Default model

    @patch('requests.Session.post')
    def test_create_non_streaming_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Noisy content
        noisy_content = "k(Hello!@ This is H a test8 with@ noise.\x00"
        cleaned_content = "Hello! This is a test with noise."
        mock_response.content = noisy_content.encode('utf-8')
        mock_post.return_value = mock_response

        result = self.completions.create(
            model=self.model,
            messages=self.test_messages,
            stream=False
        )

        self.assertIsInstance(result, ChatCompletion)
        self.assertEqual(len(result.choices), 1)
        self.assertEqual(result.choices[0].message.content, cleaned_content) # Assert cleaned content
        self.assertEqual(result.choices[0].finish_reason, "stop")
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_create_streaming_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Simulate iter_content for streaming with noisy chunks
        noisy_chunks_bytes = [
            b"k(Hello!@ ",      # Chunk 1: k( prefix and trailing @
            b"This is ",        # Chunk 2: Normal content
            b"H a test8 ",      # Chunk 3: H prefix, 8 prefix (note: 8 prefix needs space)
            b"with@ noise.\x01"  # Chunk 4: Trailing @ and a control character
        ]
        cleaned_full_content = "Hello! This is a test with noise."

        mock_response.iter_content.return_value = noisy_chunks_bytes
        mock_response.raise_for_status = MagicMock() 
        mock_post.return_value = mock_response

        stream = self.completions.create(
            model=self.model,
            messages=self.test_messages,
            stream=True
        )

        full_content_from_stream = ""
        chunk_count = 0
        for chunk in stream:
            self.assertIsInstance(chunk, ChatCompletionChunk)
            self.assertEqual(len(chunk.choices), 1)
            self.assertEqual(chunk.choices[0].delta.role, "assistant")
            if chunk.choices[0].delta.content:
                full_content_from_stream += chunk.choices[0].delta.content
            chunk_count += 1
        
        self.assertGreater(chunk_count, 0, "Should have received at least one chunk")
        self.assertEqual(full_content_from_stream, cleaned_full_content) # Assert cleaned content
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_create_non_streaming_provider_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200 # Provider error can occur even with 200 OK
        error_message = "you have reached your request limit"
        mock_response.content = error_message.encode('utf-8')
        mock_post.return_value = mock_response

        with self.assertRaises(IOError) as context:
            self.completions.create(
                model=self.model,
                messages=self.test_messages,
                stream=False
            )
        self.assertIn("BlackboxAI provider error: you have reached your request limit", str(context.exception))
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_create_streaming_provider_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        error_message = "api request failed"
        # Simulate iter_content yielding the error message
        mock_response.iter_content.return_value = [error_message.encode('utf-8')]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        stream = self.completions.create(
            model=self.model,
            messages=self.test_messages,
            stream=True
        )

        error_chunk_received = False
        for chunk in stream:
            self.assertIsInstance(chunk, ChatCompletionChunk)
            self.assertEqual(chunk.choices[0].finish_reason, "error")
            self.assertIn("BlackboxAI provider error: api request failed", chunk.choices[0].delta.content)
            error_chunk_received = True
            break # Should be the only chunk
        
        self.assertTrue(error_chunk_received, "Error chunk not received")
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_create_non_streaming_network_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Test connection error")

        with self.assertRaises(IOError) as context:
            self.completions.create(
                model=self.model,
                messages=self.test_messages,
                stream=False
            )
        self.assertIn("BlackboxAI request failed due to a network error: Test connection error", str(context.exception))
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_create_streaming_network_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("Test network exception")

        stream = self.completions.create(
            model=self.model,
            messages=self.test_messages,
            stream=True
        )

        error_chunk_received = False
        for chunk in stream:
            self.assertIsInstance(chunk, ChatCompletionChunk)
            self.assertEqual(chunk.choices[0].finish_reason, "error")
            self.assertIn("BlackboxAI request failed due to a network error: Test network exception", chunk.choices[0].delta.content)
            self.assertEqual(chunk.system_fingerprint, "network_error")
            error_chunk_received = True
            break 
        
        self.assertTrue(error_chunk_received, "Network error chunk not received")
        mock_post.assert_called_once()

    def test_clean_text_removes_null_bytes(self):
        text = "Hello\x00World"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "HelloWorld")

    def test_clean_text_removes_control_chars(self):
        text = "Hello\x01\x02\x0bWorld" # SOH, STX, VT
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "HelloWorld")

    def test_clean_text_keeps_newlines_and_tabs(self):
        text = "Hello\nWorld\tTest"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Hello\nWorld\tTest")
        
    def test_clean_text_non_string_input(self):
        self.assertEqual(clean_text(123), 123)
        self.assertIsNone(clean_text(None))

    def test_clean_text_new_noise_patterns(self):
        # Test cases for the new noise patterns
        self.assertEqual(clean_text("k(Hello"), "Hello", "Should remove 'k(' prefix")
        self.assertEqual(clean_text("@ Test"), "Test", "Should remove '@ ' prefix")
        self.assertEqual(clean_text("H Test"), "Test", "Should remove 'H ' prefix")
        self.assertEqual(clean_text("8 Test"), "Test", "Should remove '8 ' prefix")
        self.assertEqual(clean_text("Word@"), "Word", "Should remove trailing '@'")
        self.assertEqual(clean_text("Word!@"), "Word!", "Should remove trailing '@' after '!'")
        
        # Combinations
        self.assertEqual(clean_text("k(Word@"), "Word", "Should handle prefix and trailing noise")
        self.assertEqual(clean_text("@ Another Test@"), "Another Test", "Should handle prefix and trailing noise")
        self.assertEqual(clean_text("k(Hello\x00@ World\x01"), "Hello World", "Should handle all types of noise")
        
        # Prefixes only at the start
        self.assertEqual(clean_text("Text with k(internal prefix"), "Text with k(internal prefix", "Should not remove internal 'k('")
        self.assertEqual(clean_text("Text with @ internal"), "Text with @ internal", "Should not remove internal '@ '")

        # Edge cases
        self.assertEqual(clean_text("k("), "", "Should handle prefix only")
        self.assertEqual(clean_text("@ "), "", "Should handle prefix only")
        self.assertEqual(clean_text("H "), "", "Should handle prefix only")
        self.assertEqual(clean_text("8 "), "", "Should handle prefix only")
        self.assertEqual(clean_text("Word@ Word2@"), "Word Word2", "Should handle multiple trailing @")
        self.assertEqual(clean_text("NoNoise"), "NoNoise", "Should not alter clean string")
        self.assertEqual(clean_text("Ends with k( but not prefix"), "Ends with k( but not prefix")
        self.assertEqual(clean_text("Not a prefix@"), "Not a prefix") # Trailing @
        self.assertEqual(clean_text("Email user@example.com"), "Email user@example.com", "Should not remove @ in email-like patterns")
        self.assertEqual(clean_text("k(@ Test)"), "@ Test)", "Should remove k( prefix, not the later @ if it's part of content")


if __name__ == '__main__':
    unittest.main()
