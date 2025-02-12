from flask import Flask, render_template
from flask_login import login_required, current_user

def register_other_routes(app):
    @app.route('/')
    @login_required
    def index():
        relay_rules = []
        return render_template('dashboard.html', relay_rules=relay_rules, current_user=current_user)

    @app.route('/dual_management')
    @login_required
    def dual_management():
        return render_template('dual_management.html', current_user=current_user)