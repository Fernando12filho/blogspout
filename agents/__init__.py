"""AI agents for the blog.

- WriterAgent (Pout): writes posts and comments.
- DesignerAgent: designs a bespoke per-post visual theme.
"""
from .writer import WriterAgent, writer, generate_post, generate_comment
from .designer import (
    DesignerAgent,
    designer,
    generate_theme,
    build_theme_head,
    theme_head,
)

__all__ = [
    'WriterAgent', 'writer', 'generate_post', 'generate_comment',
    'DesignerAgent', 'designer', 'generate_theme',
    'build_theme_head', 'theme_head',
]
