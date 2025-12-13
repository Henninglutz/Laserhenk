"""Flask Application Factory für LASERHENK."""

import os
from datetime import timedelta
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.auth import auth_bp
from app.api import api_bp
from app.crm import crm_bp


def create_app() -> Flask:
    """
    Erstelle und konfiguriere die Flask-Anwendung.

    Returns:
        Konfigurierte Flask App
    """
    # Flask mit korrektem template und static folder
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../templates/static',
        static_url_path='/static'
    )

    # Flask Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)

    # CORS - Allow all origins for development
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # JWT Manager
    jwt = JWTManager(app)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(crm_bp, url_prefix='/api/crm')

    # Health Check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'laserhenk-flask'}

    # Fabric Images - serve from storage/fabrics/images/
    @app.route('/fabrics/images/<path:filename>')
    def serve_fabric_image(filename):
        """Serve fabric images from local storage."""
        from flask import send_from_directory
        import os

        # Path to fabric images directory
        images_dir = os.path.join(app.root_path, '..', 'storage', 'fabrics', 'images')
        images_dir = os.path.abspath(images_dir)

        try:
            return send_from_directory(images_dir, filename)
        except FileNotFoundError:
            # Fallback to placeholder if image not found
            from flask import redirect
            return redirect(f'https://via.placeholder.com/400x300?text={filename}', code=302)

    # Root - serve static frontend
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    return app


# Global app instance for development
app = create_app()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"🚀 LASERHENK Flask App starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
