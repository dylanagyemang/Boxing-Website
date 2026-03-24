from flask import render_template, request, jsonify
from . import boxers_bp
from .. import db
from ..models import Boxer


@boxers_bp.route('/boxers')
def index():
    page = request.args.get('page', 1, type=int)
    weight_class = request.args.get('weight_class', '').strip()
    nationality = request.args.get('nationality', '').strip()

    query = Boxer.query
    if weight_class:
        query = query.filter(Boxer.weight_class == weight_class)
    if nationality:
        query = query.filter(Boxer.nationality == nationality)

    boxers = query.order_by(Boxer.name).paginate(page=page, per_page=12, error_out=False)

    wc_rows = db.session.query(Boxer.weight_class).filter(
        Boxer.weight_class.isnot(None)
    ).distinct().all()
    weight_classes = sorted(set(r[0] for r in wc_rows if r[0]))

    nat_rows = db.session.query(Boxer.nationality).filter(
        Boxer.nationality.isnot(None)
    ).distinct().all()
    nationalities = sorted(set(r[0] for r in nat_rows if r[0]))

    return render_template(
        'boxers/index.html',
        boxers=boxers,
        weight_classes=weight_classes,
        nationalities=nationalities,
        selected_weight_class=weight_class,
        selected_nationality=nationality,
    )


@boxers_bp.route('/boxers/<int:boxer_id>')
def profile(boxer_id):
    boxer = Boxer.query.get_or_404(boxer_id)
    titles_list = [t.strip() for t in boxer.titles.split('|') if t.strip()] if boxer.titles else []
    total_fights = (boxer.record_wins or 0) + (boxer.record_losses or 0) + (boxer.record_draws or 0)
    return render_template('boxers/profile.html', boxer=boxer, titles_list=titles_list, total_fights=total_fights)


@boxers_bp.route('/boxers/search')
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    results = Boxer.query.filter(
        Boxer.name.ilike(f'%{q}%') | Boxer.nickname.ilike(f'%{q}%')
    ).limit(10).all()
    return jsonify([{
        'id': b.id,
        'name': b.name,
        'nickname': b.nickname or '',
        'weight_class': b.weight_class or '',
        'record': f"{b.record_wins}-{b.record_losses}-{b.record_draws}",
    } for b in results])
