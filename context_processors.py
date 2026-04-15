"""
context_processors.py
=====================
Flask Context Processors — Har template mein automatically available variables inject karta hai.

app.py mein register karo:
    from context_processors import register_context_processors
    register_context_processors(app)
"""

from flask_login import current_user
from models.permission import Module


def register_context_processors(app):
    """Register all context processors with Flask app."""

    @app.context_processor
    def inject_nav_modules():
        """
        nav_modules — Sidebar ke liye sirf ACTIVE modules inject karta hai.
        
        Yeh automatically har template mein available hota hai.
        
        Sidebar mein is_active=False modules kabhi nahi dikhenge kyunki
        yahan filter ho jaate hain.
        """
        if not current_user.is_authenticated:
            return {'nav_modules': []}

        try:
            # Sirf active modules — parent aur children dono
            active_modules = (
                Module.query
                .filter_by(is_active=True)
                .order_by(Module.parent_id.nullsfirst(), Module.sort_order)
                .all()
            )
            return {'nav_modules': active_modules}

        except Exception:
            # DB error hone par empty list — app crash na ho
            return {'nav_modules': []}
