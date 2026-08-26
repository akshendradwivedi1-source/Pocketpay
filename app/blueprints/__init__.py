import os
from flask import Blueprint, render_template, send_from_directory, current_app

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/<path:path>')
def serve_frontend(path):
    if path and not path.startswith('api/') and not path.startswith('auth/'):
        template_path = os.path.join(current_app.root_path, 'templates', 'index.html')
        if os.path.exists(template_path):
            return render_template('index.html')
    return render_template('index.html')
