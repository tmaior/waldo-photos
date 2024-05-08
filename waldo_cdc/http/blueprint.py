from flask import Blueprint, jsonify
from structlog import get_logger

LOG = get_logger()

blueprint = Blueprint('base', __name__, static_folder='static', template_folder='templates')


def construct_blueprint(health_check_func):
    @blueprint.route('/health-check/', methods=['GET'])
    def health_check():
        (is_healthy, results) = health_check_func()

        status_code = 500 if not is_healthy else 200
        return jsonify({'healthy': is_healthy, 'results': results}), status_code

    return blueprint
