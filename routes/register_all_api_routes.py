from routes.api.user_routes import register_user_routes
from routes.api.rule_routes import register_rule_routes
from routes.api.rule_list import register_other_routes
from routes.api.node_routes import register_node_blueprint


def register_routes(app):
    register_user_routes(app)
    register_rule_routes(app)
    register_other_routes(app)
    register_node_blueprint(app)
