"""Back-compat shim.

Pout's logic now lives in the agents package (agents/writer.py for the Writer,
agents/designer.py for the Designer). This module re-exports the call sites that
the rest of the app and scheduler still import by their old names.
"""
from agents.writer import generate_post, generate_comment
from agents.designer import generate_theme

# Old name kept so existing routes keep working.
generate_custom_html = generate_theme

__all__ = ['generate_post', 'generate_comment', 'generate_theme', 'generate_custom_html']
