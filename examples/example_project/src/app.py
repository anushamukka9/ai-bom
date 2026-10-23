"""Example agent app. Fixture only; nothing here runs."""

import cohere
import openai

client = openai.OpenAI()
backup = cohere.Client()
