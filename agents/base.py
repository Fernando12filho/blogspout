"""Shared base for the blog's AI agents.

Each agent is a small object: a name, a model, one or more prompt files, and a
generate method that writes its result into the database. Pout (the Writer) and
the Designer both build on this.
"""
import os
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')


def load_prompt(filename):
    """Read a prompt file from the prompts/ directory."""
    with open(os.path.join(PROMPTS_DIR, filename), 'r') as f:
        return f.read().strip()


class Agent:
    """Base class for an LLM-backed agent.

    Subclasses set ``name`` and ``model`` and call ``self.complete(...)``.
    The Anthropic client is shared and reads ANTHROPIC_API_KEY from the env.
    """

    name = 'agent'
    model = 'claude-sonnet-4-6'

    def __init__(self):
        self._client = None

    @property
    def client(self):
        # Created lazily so importing an agent (e.g. for pure theme rendering)
        # never requires ANTHROPIC_API_KEY; only making a call does.
        if self._client is None:
            self._client = Anthropic()
        return self._client

    def complete(self, system, user, max_tokens=1600):
        """One-shot completion with the system prompt cached across calls."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()
