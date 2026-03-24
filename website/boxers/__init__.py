from flask import Blueprint

boxers_bp = Blueprint('boxers', __name__)

from . import routes  # noqa: E402, F401
