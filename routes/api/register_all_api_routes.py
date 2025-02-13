from .user_routes import register_user_routes
from .relay_routes import register_relay_routes
from .relay_list import register_other_routes
from .node_routes import register_node_blueprint


def register_routes(app):
    register_user_routes(app)
    register_relay_routes(app)
    register_other_routes(app)
    register_node_blueprint(app)
