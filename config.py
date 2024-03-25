import os

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.  Must run with "python app.py" for this to be picked up
DEBUG = True

# Secret key for sessions
SECRET_KEY = os.urandom(32)

# CouchDB database configuration
COUCHDB_SERVER = 'http://localhost:5984/'  # Assuming CouchDB is running locally
COUCHDB_DATABASE = 'fyyur'  # Name of the CouchDB database

# CouchDB authentication credentials (if required)
COUCHDB_USERNAME = 'admin'
COUCHDB_PASSWORD = 'admin'

# CouchDB database URI with authentication credentials
COUCHDB_DATABASE_URI = f'http://{COUCHDB_USERNAME}:{COUCHDB_PASSWORD}@localhost:5984/'