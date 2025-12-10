
# PrimeVista — Styled Flask + SQLite App

A modern-styled landing page (Hero, Services, Why, About, Projects, Clients, Newsletter) with an Admin panel.

## Run
1) `pip install -r requirements.txt`
2) `python app.py --init-db`
3) `flask --app app.py --debug run`

Image paths use `url_for('static', filename='img/...')` from where `app.py` sits.
