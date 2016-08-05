# -*- coding: utf-8 -*-
import os.path
import re
import datetime
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, flash, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/brasileirao_2016.db'
app.config['SECRET_KEY'] = 'dev key'

db = SQLAlchemy(app)


class Table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    the_round = db.Column(db.Integer)
    date = db.Column(db.Date)
    home_team = db.Column(db.String(120))
    home_team_result = db.Column(db.Integer)
    away_team_result = db.Column(db.Integer)
    away_team = db.Column(db.String(120))

    predicts_string = db.Column(db.String(300))
    predicts_last_refresh_date = db.Column(db.DateTime)

    def __init__(self, the_round, date, home_team, home_team_result, away_team, away_team_result):
        self.the_round = the_round
        self.date = date
        self.home_team = home_team
        self.home_team_result = home_team_result
        self.away_team = away_team
        self.away_team_result = away_team_result

    def __repr__(self):
        return u'{} x {}'.format(self.home_team, self.away_team)


@app.route('/')
def index():
    game = Table.query.filter(Table.date >= datetime.datetime.now()).first()

    if not game:
        return redirect(url_for('refresh_table'))

    return redirect(url_for('table', page=game.the_round))


@app.route('/table/<int:page>')
def table(page=1):
    games = Table.query.filter().order_by('the_round').paginate(page, 10, False)

    passed = games.items[0].date < datetime.date.today() and games.items[0].home_team_result == None

    return render_template('index.html', games=games, passed=passed)


@app.route('/refresh_table')
def refresh_table():
    r = requests.get('http://www.tabeladobrasileirao.net/')

    soup = BeautifulSoup(r.text.encode('utf-8'), 'html.parser')
    table_html = soup.find('tbody')

    for row in table_html.findAll("tr"):
        game = dict()

        match = row.find('td', {"class": "match"})\
                   .find('div', {"class": "game-round"})\
                   .find(text=True)
        game['round'] = int(match)

        date_string = row.find('td', {"class": "date"}).find(text=True)
        date_string = '{}/{}'.format(date_string, '2016')
        game['date'] = datetime.datetime.strptime(date_string, "%d/%m/%Y").date()

        game['home_team'] = row.find('td', {"class": "match"})\
                               .find('div', {"class": "home"})['title']

        result = row.findAll('div', {"class": "game-scoreboard-input"})
        home_team_result = result[0].find(text=True)
        away_team_result = result[2].find(text=True)

        try:
            game['home_team_result'] = int(home_team_result)
            game['away_team_result'] = int(away_team_result)
        except ValueError:
            game['home_team_result'] = None
            game['away_team_result'] = None

        game['away_team'] = row.find('td', {"class": "match"})\
                               .find('div', {"class": "visitor"})['title']

        print(game)

        game_register = Table.query.filter_by(home_team=game['home_team'],
                                              away_team=game['away_team']).count()

        if game_register == 0:
            table = Table(game['round'], game['date'], game['home_team'], game['home_team_result'],
                          game['away_team'], game['away_team_result'])

            db.session.add(table)
            db.session.commit()

    flash('Tabela atualizada.')

    next_url = request.args.get('next', None)

    if next_url:
        return redirect(request.args.get('next'))
    return redirect(url_for('index'))


@app.route('/predicts/<int:id>')
def predicts(id):
    game = Table.query.get(id)

    r = requests.get(u'http://www.bing.com/search?q={}'.format(game))

    soup = BeautifulSoup(r.text.encode('utf-8'), 'html.parser')
    div = soup.find('div',{'id':'tab_4'}).findNext('span',{'class':'b_demoteText'}).find_next_sibling(text=True)

    game.predicts_string = div
    game.predicts_last_refresh_date = datetime.datetime.now()
    db.session.commit()

    flash(u'Previsão para {} atualizada.'.format(game))
    return redirect(request.args.get('next'))


if __name__ == '__main__':
    if not os.path.isfile(app.config['SQLALCHEMY_DATABASE_URI']):
        db.create_all()

    app.run(debug=True)
