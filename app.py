from flask import Flask, request, redirect
import mysql.connector

import requests
import json

config_file = "./config.json"

with open(config_file) as f:
    config = json.load(f)

API_ENDPOINT = config["discord"]["api_endpoint"]
CLIENT_ID = config["discord"]["client_id"]
CLIENT_SECRET = config["discord"]["client_secret"]
REDIRECT_URI = config["discord"]["redirect_uri"]

ALLOWED_SERVERS = config["discord"]["allowed_servers"]

DATABASE_HOST = config["database"]["host"]
DATABASE_USER = config["database"]["user"]
DATABASE_PASSWORD = config["database"]["password"]
DATABASE_NAME = config["database"]["name"]

database = mysql.connector.connect(
    host=DATABASE_HOST, user=DATABASE_USER, password=DATABASE_PASSWORD
)

database_name = DATABASE_NAME

query = database.cursor()
query.execute("CREATE DATABASE IF NOT EXISTS " + database_name)
query.execute("USE " + database_name)

#  TODO: create tables if not present

query.execute(
    "CREATE TABLE IF NOT EXISTS users (user_id INT AUTO_INCREMENT PRIMARY KEY, discord_id VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, token VARCHAR(255) NOT NULL, refresh_token VARCHAR(255) NOT NULL)"
)
query.execute(
    "CREATE TABLE IF NOT EXISTS clips (clip_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL, file VARCHAR(255) NOT NULL, author_id VARCHAR(255) NOT NULL, FOREIGN KEY (author_id) REFERENCES users(discord_id))"
)


app = Flask(__name__)


@app.route("/")
def index():
    return "Hello, World!"


@app.route("/login")
def login():
    # redirect to discord oauth2
    return redirect(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )


@app.route("/users")
def users():
    query.execute("SELECT name FROM users")
    return str(query.fetchall())


def add_user(discord_id, name, token, refresh_token):
    # INSERT INTO users (name, token, refresh_token) VALUES ('test_user', 'token', 'refresh')
    query.execute(
        f"INSERT INTO users (discord_id, name, token, refresh_token) VALUES ('{discord_id}', '{name}', '{token}', '{refresh_token}')"
    )
    database.commit()


def is_existing_user(discord_id):
    query.execute(f"SELECT * FROM users WHERE discord_id = {discord_id}")
    return query.fetchall() != []


@app.route("/clips")
def clips():
    query.execute("SELECT name FROM clips")
    return str(query.fetchall())


def add_clip(name, file, author_id):
    #  INSERT INTO clips (clip_id, name, file, author_id) VALUES (NULL, 'test_clip', 'test_clip.mp4', '1')
    # filepath = f"{upload_folder}/clips/{user_id}/{name}"
    query.execute(
        f"INSERT INTO clips (name, file, author_id) VALUES ('{name}', '{file}', '{author_id}')"
    )


def get_token(code):
    # stolen directly from discord docs
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(
        "%s/oauth2/token" % API_ENDPOINT,
        data=data,
        headers=headers,
        auth=(CLIENT_ID, CLIENT_SECRET),
    )
    r.raise_for_status()

    return json.loads(r.text)


def get_discord_data(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{API_ENDPOINT}/users/@me", headers=headers)
    r.raise_for_status()

    response = json.loads(r.text)

    return response


def is_in_allowed_servers(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers=headers)
    r.raise_for_status()

    response = json.loads(r.text)

    # throw error if user is not in allowed servers
    if not any(server["id"] in ALLOWED_SERVERS for server in response):
        return False
    else:
        return True


# /oauth?code=1234
@app.route("/oauth")
def oauth():
    response = get_token(request.args.get("code"))
    access_token = response["access_token"]
    refresh_token = response["refresh_token"]

    discord_user = get_discord_data(access_token)

    if not is_in_allowed_servers(access_token):
        return "You are not allowed to be here"

    if not is_existing_user(discord_user["id"]):
        add_user(
            discord_user["id"],
            discord_user["username"],
            access_token,
            refresh_token,
        )
    else:
        #  update token
        pass

    return "Logged in"  #  FIX: redirect to home page


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
