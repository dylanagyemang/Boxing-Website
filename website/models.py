from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, index=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    notes = db.relationship('Note')

class Boxer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    nickname = db.Column(db.String(150))
    hometown = db.Column(db.String(200))
    nationality = db.Column(db.String(100))
    weight_class = db.Column(db.String(100))
    stance = db.Column(db.String(50))
    years_active = db.Column(db.String(50))
    record_wins = db.Column(db.Integer, default=0)
    record_losses = db.Column(db.Integer, default=0)
    record_draws = db.Column(db.Integer, default=0)
    wins_by_ko = db.Column(db.Integer, default=0)
    no_contests = db.Column(db.Integer, default=0)
    titles = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    wikipedia_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
