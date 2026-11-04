import json
import os
import pytest
from pathlib import Path

TEST_DB = "test.db"

# Flask-SQLAlchemy reads the database URI only once, when the app is imported,
# so point it at the test database before importing (otherwise the tests would
# run against, and drop, the real flaskr.db)
os.environ["DATABASE_URL"] = f"sqlite:///{Path(__file__).resolve().parent.parent.joinpath(TEST_DB)}"

from project.app import app, db
from project.models import Post


@pytest.fixture
def client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    app.config["TESTING"] = True
    app.config["DATABASE"] = BASE_DIR.joinpath(TEST_DB)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get('/delete/1')
    data = json.loads(rv.data)
    assert data["status"] == 1


def add_posts(*posts):
    """Insert (title, text) posts straight into the test database"""
    for title, text in posts:
        db.session.add(Post(title, text))
    db.session.commit()


def test_search_page(client):
    """Ensure the search page loads with a search box and no results"""
    rv = client.get("/search/")
    assert rv.status_code == 200
    assert b'name="query"' in rv.data
    assert b'class="entry"' not in rv.data


def test_search_matches_title_and_text(client):
    """Ensure search returns posts whose title or text match, and only those"""
    add_posts(
        ("Flask tips", "routing basics"),
        ("Cooking", "how to make flask-shaped bread"),
        ("Gardening", "tomatoes and basil"),
    )
    rv = client.get("/search/?query=flask")
    assert b"Flask tips" in rv.data  # matches title
    assert b"Cooking" in rv.data  # matches text
    assert b"Gardening" not in rv.data


def test_search_is_case_insensitive(client):
    """Ensure search ignores upper/lower case"""
    add_posts(("Hello World", "first post"))
    rv = client.get("/search/?query=hELLo")
    assert b"Hello World" in rv.data


def test_search_no_results(client):
    """Ensure a query that matches nothing shows no posts"""
    add_posts(("Hello World", "first post"))
    rv = client.get("/search/?query=xyz")
    assert b"Hello World" not in rv.data


def test_search_results_have_post_id(client):
    """Ensure each result's heading carries the post id, so click-to-delete works"""
    add_posts(("Hello World", "first post"))
    rv = client.get("/search/?query=hello")
    assert b'<h2 id="1">Hello World</h2>' in rv.data


def test_index_links_to_search(client):
    """Ensure the home page has a link to the search page"""
    rv = client.get("/")
    assert b'href="/search/"' in rv.data
