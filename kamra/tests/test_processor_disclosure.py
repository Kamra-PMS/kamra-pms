from unittest import TestCase

from kamra.assistant_privacy import processor_disclosure as d


class TestProcessorDisclosure(TestCase):
	def test_matches_by_host(self):
		self.assertIn("Ollama", d("http://127.0.0.1:11434/v1"))
		self.assertIn("Ollama", d("http://gpu-box:11434/v1"))
		self.assertIn("OpenAI", d("https://api.openai.com/v1"))
		self.assertIn("OpenAI", d("https://acme.openai.azure.com/openai"))
		self.assertIn("Gemini", d("https://generativelanguage.googleapis.com/v1beta/openai"))
		self.assertIn("Groq", d("https://api.groq.com/openai/v1"))
		self.assertIn("OpenRouter", d("https://openrouter.ai/api/v1"))

	def test_lookalike_hosts_are_not_trusted(self):
		for url in (
			"https://openai.com.evil.example/v1",
			"https://evil.example/?openrouter.ai",
			"https://notgroq.com",
			None,
			"::bad",
		):
			self.assertNotIn("OpenAI", d(url))
			self.assertNotIn("OpenRouter", d(url))
			self.assertNotIn("Groq", d(url))
