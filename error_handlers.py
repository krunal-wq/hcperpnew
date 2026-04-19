"""
error_handlers.py — Register global HTTP error handlers
Register this in your app factory: register_error_handlers(app)
"""
from flask import render_template


def register_error_handlers(app):
    """Call this in your create_app() or app factory after creating app."""

    @app.errorhandler(403)
    def forbidden(e):
        return render_template(
            'errors/403.html',
            message="You do not have permission to access this page."
        ), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template(
            'errors/404.html',
            message="The page you are looking for does not exist."
        ), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template(
            'errors/500.html',
            message="An internal server error occurred. Please try again."
        ), 500
