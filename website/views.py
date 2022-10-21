from flask import Blueprint, render_template

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template("home.html")

@views.route('/jab')
def jab():
    return render_template("jab.html")

@views.route('/cross')
def cross():
    return render_template("cross.html")

@views.route('/styles')
def styles():
    return render_template("styles.html")

@views.route('/stances')
def stances():
    return render_template("stances.html")

@views.route('/hook')
def hook():
    return render_template("hook.html")

@views.route('/uppercut')
def uppercut():
    return render_template("uppercuts.html")

@views.route('/movement')
def movement():
    return render_template("movement.html")

@views.route('/quiz')
def boxers():
    return render_template("quiz.html")


@views.route('/favicon.ico')
def favicon():
    return render_template("favicon.ico")

