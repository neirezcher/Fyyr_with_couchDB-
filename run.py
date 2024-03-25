import json
import dateutil.parser
import babel
from flask import Flask, render_template, request, Response, flash, redirect, url_for, abort, jsonify
from couchdb import Server
from couchdb.mapping import Document
from couchdb.design import ViewDefinition
import logging
from logging import Formatter, FileHandler
#from flask_wtf import FlaskForm  (not used here but in forms.py)
from forms import *

from datetime import datetime
import re
from operator import itemgetter # for sorting lists of tuples
from models import Artist,Venue, Show
#----------------------------------------------------------------------------#

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

# Create the Flask app
app = Flask(__name__)
# Load configuration
app.config.from_pyfile('config.py')

# Connect to CouchDB using the configured server URL
server = Server(app.config['COUCHDB_DATABASE_URI'])

# Select the database using the configured database name
db = server[app.config['COUCHDB_DATABASE']]
#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#


def format_datetime(value, format='medium'):
    date = dateutil.parser.parse(value)
    if format == 'full':
        format = "EEEE MMMM, d, y 'at' h:mma"
    elif format == 'medium':
        format = "EE MM, dd, y h:mma"
    return babel.dates.format_datetime(date, format)


app.jinja_env.filters['datetime'] = format_datetime


#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
    return render_template('pages/home.html')


#  Venues
#  ----------------------------------------------------------------


@app.route('/venues')
def venues():
    # Get all venues
    venues = Venue.view('_all_docs', include_docs=True)

    data = []  # A list of dictionaries, where city, state, and venues are dictionary keys

    # Create a set of all the cities/states combinations uniquely
    cities_states = set()
    for venue in venues:
        cities_states.add((venue.doc.city, venue.doc.state))  # Add tuple
    
    # Turn the set into an ordered list
    cities_states = list(cities_states)
    cities_states.sort(key=itemgetter(1, 0))  # Sorts on second column first (state), then by city.

    now = datetime.now()  # Don't get this over and over in a loop!

    # Now iterate over the unique values to seed the data dictionary with city/state locations
    for loc in cities_states:
        # For this location, see if there are any venues there, and add if so
        venues_list = []
        for venue in venues:
            if (venue.doc.city == loc[0]) and (venue.doc.state == loc[1]):

                # If we've got a venue to add, check how many upcoming shows it has
                num_upcoming = sum(1 for show in venue.doc.shows if show['start_time'] > now)

                venues_list.append({
                    "id": venue.id,
                    "name": venue.doc.name,
                    "num_upcoming_shows": num_upcoming
                })

        # After all venues are added to the list for a given location, add it to the data dictionary
        data.append({
            "city": loc[0],
            "state": loc[1],
            "venues": venues_list
        })

    return render_template('pages/venues.html', areas=data)

@app.route('/venues/search', methods=['POST'])
def search_venues():
    search_term = request.form.get('search_term', '').strip()

    # Use CouchDB's map/reduce functions for text search
    # Define a map function to emit documents containing the search term
    map_function = '''function(doc) {
        if (doc.name && doc.name.toLowerCase().indexOf('%s') !== -1) {
            emit(doc._id, doc);
        }
    }''' % search_term.lower()

    # Get all venues that match the search term
    venues = Venue.view('_design/search', map_function)

    venue_list = []
    now = datetime.now()
    for venue in venues:
        venue_doc = Venue.load(venue.id)
        venue_shows = venue_doc.shows
        num_upcoming = sum(1 for show in venue_shows if show['start_time'] > now)

        venue_list.append({
            "id": venue.id,
            "name": venue_doc.name,
            "num_upcoming_shows": num_upcoming
        })

    response = {
        "count": len(venue_list),
        "data": venue_list
    }

    return render_template('pages/search_venues.html', results=response, search_term=search_term)


@app.route('/venues/<int:venue_id>')
def show_venue(venue_id):
    # Get venue document by its ID
    venue = Venue.load(venue_id)

    # If venue does not exist, redirect to home page
    if not venue:
        return redirect(url_for('index'))

    # Get genres as a list of genre strings
    genres = venue.genres

    # Initialize lists for past and upcoming shows
    past_shows = []
    past_shows_count = 0
    upcoming_shows = []
    upcoming_shows_count = 0

    now = datetime.now()

    # Iterate over shows and categorize them as past or upcoming
    for show in venue.shows:
        artist_id = show['id_Artist']
        artist = Artist.load(artist_id)

        if show['start_time'] > now:
            upcoming_shows_count += 1
            upcoming_shows.append({
                "artist_id": artist_id,
                "artist_name": artist.name if artist else None,
                "artist_image_link": artist.image_link if artist else None,
                "start_time": show['start_time'].isoformat()
            })
        else:
            past_shows_count += 1
            past_shows.append({
                "artist_id": artist_id,
                "artist_name": artist.name if artist else None,
                "artist_image_link": artist.image_link if artist else None,
                "start_time": show['start_time'].isoformat()
            })
    # Construct data dictionary for rendering template
    data = {
        "id": venue.id,
        "name": venue.name,
        "genres": genres,
        "address": venue.address,
        "city": venue.city,
        "state": venue.state,
        "phone": venue.phone,  # Assuming phone is already formatted
        "website": venue.website,
        "facebook_link": venue.facebook_link,
        "seeking_talent": venue.seeking_talent,
        "seeking_description": venue.seeking_description,
        "image_link": venue.image_link,
        "past_shows": past_shows,
        "past_shows_count": past_shows_count,
        "upcoming_shows": upcoming_shows,
        "upcoming_shows_count": upcoming_shows_count
    }

    return render_template('pages/show_venue.html', venue=data)
#  Create Venue
#  ----------------------------------------------------------------

@app.route('/venues/create', methods=['GET'])
def create_venue_form():
    form = VenueForm()
    return render_template('forms/new_venue.html', form=form)

@app.route('/venues/create', methods=['POST'])
def create_venue_submission():

    form = VenueForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('create_venue_submission'))

    else:
        error_in_insert = False

        # Insert form data into DB
        try:
            # Create Venue document
            venue = Venue(
                name=name,
                city=city,
                state=state,
                address=address,
                phone=phone,
                image_link=image_link,
                facebook_link=facebook_link,
                website=website,
                seeking_talent=seeking_talent,
                seeking_description=seeking_description,
                genres=genres
            )

            # Save Venue document to CouchDB
            venue.store(db)
        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_venue_submission()')

        if not error_in_insert:
            # on successful db insert, flash success
            flash('Venue ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Venue ' + name + ' could not be listed.')
            print("Error in create_venue_submission()")
            # return redirect(url_for('create_venue_submission'))
            abort(500)
@app.route('/venues/<venue_id>/delete', methods=['GET'])
def delete_venue(venue_id):
    venue = Venue.load(db, venue_id)
    if not venue:
        return redirect(url_for('index'))
    else:
        error_on_delete = False
        # Need to hang on to venue name since will be lost after delete
        venue_name = venue.name
        try:
            venue.delete()
        except:
            error_on_delete = True

        if error_on_delete:
            flash(f'An error occurred deleting venue {venue_name}.')
            print("Error in delete_venue()")
            abort(500)
        else:
            # flash(f'Successfully removed venue {venue_name}')
            # return redirect(url_for('venues'))
            return jsonify({
                'deleted': True,
                'url': url_for('venues')
            })
#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
    artists = Artist.view(db, '_all_docs', include_docs=True)
    data = [{"id": artist.id, "name": artist.name} for artist in artists]

    return render_template('pages/artists.html', artists=data)


@app.route('/artists/search', methods=['POST'])
def search_artists():
    search_term = request.form.get('search_term', '').strip()

    # Define the views
    artists_view = ViewDefinition('artists', 'by_name', 'function(doc) { if (doc.name) { emit(doc.name.toLowerCase(), doc); } }')
    shows_view = ViewDefinition('shows', 'by_artist', 'function(doc) { if (doc.artist_id) { emit(doc.artist_id, doc); } }')

    # Query artists with name matching the search term using the view
    artists = list(artists_view(db))

    artist_list = []
    now = datetime.now()
    for artist in artists:
        # Query shows for the current artist using the view
        artist_shows = list(shows_view(db, key=artist.id))

        num_upcoming = sum(1 for show in artist_shows if show.start_time > now)

        artist_list.append({
            "id": artist.id,
            "name": artist.name,
            "num_upcoming_shows": num_upcoming
        })

    response = {
        "count": len(artist_list),
        "data": artist_list
    }

    return render_template('pages/search_artists.html', results=response, search_term=search_term)


@app.route('/artists/<int:artist_id>')
def show_artist(artist_id):
    artist = Artist.load(db, artist_id)
    if not artist:
        return redirect(url_for('index'))
    else:
        genres = artist.genres
        
        past_shows = []
        past_shows_count = 0
        upcoming_shows = []
        upcoming_shows_count = 0
        now = datetime.now()
        for show in artist.shows:
            venue = Venue.load(db, show['venue_id'])
            if venue:
                if show['start_time'] > now:
                    upcoming_shows_count += 1
                    upcoming_shows.append({
                        "venue_name": venue.name,
                        "venue_image_link": venue.image_link,
                        "start_time": format_datetime(str(show['start_time']))
                    })
                elif show['start_time'] < now:
                    past_shows_count += 1
                    past_shows.append({
                        "venue_name": venue.name,
                        "venue_image_link": venue.image_link,
                        "start_time": format_datetime(str(show['start_time']))
                    })

        data = {
            "id": artist_id,
            "name": artist.name,
            "genres": genres,
            "city": artist.city,
            "state": artist.state,
            "phone": artist.phone,
            "website": artist.website,
            "facebook_link": artist.facebook_link,
            "seeking_venue": artist.seeking_venue,
            "seeking_description": artist.seeking_description,
            "image_link": artist.image_link,
            "past_shows": past_shows,
            "past_shows_count": past_shows_count,
            "upcoming_shows": upcoming_shows,
            "upcoming_shows_count": upcoming_shows_count
        }

    return render_template('pages/show_artist.html', artist=data)
#  Update
#  ----------------------------------------------------------------
@app.route('/artists/<int:artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
    # Fetch the artist document from the database
    artist = Artist.load(db, artist_id)
    if not artist:
        # If artist does not exist, redirect to index page
        return redirect(url_for('index'))
    
    # Prepopulate the form with existing artist data
    form = ArtistForm(obj=artist)

    # Prepare artist data for rendering
    artist_data = {
        "id": artist_id,
        "name": artist.name,
        "genres": artist.genres,
        "city": artist.city,
        "state": artist.state,
        "phone": artist.phone,
        "website": artist.website,
        "facebook_link": artist.facebook_link,
        "seeking_venue": artist.seeking_venue,
  
        "seeking_description": artist.seeking_description,
        "image_link": artist.image_link
    }

    return render_template('forms/edit_artist.html', form=form, artist=artist_data)

@app.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
    form = ArtistForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    phone = form.phone.data
    phone = re.sub('\D', '', phone)  # Normalize phone number
    genres = form.genres.data
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()

    if not form.validate():
        flash(form.errors)
        return redirect(url_for('edit_artist_submission', artist_id=artist_id))

    else:
        error_in_update = False

        try:
            # Retrieve the existing artist object
            artist = Artist.load(db, artist_id)

            # Update artist fields
            artist.name = name
            artist.city = city
            artist.state = state
            artist.phone = phone
            artist.seeking_venue = seeking_venue
            artist.seeking_description = seeking_description
            artist.image_link = image_link
            artist.website = website
            artist.facebook_link = facebook_link

            # Clear existing genres
            artist.genres = []

            # Assign genres
            for genre in genres:
                artist.genres.append(genre)

            # Attempt to save changes
            artist.store(db)

        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_artist_submission()')

        if not error_in_update:
            flash('Artist ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_artist', artist_id=artist_id))
        else:
            flash('An error occurred. Artist ' + name + ' could not be updated.')
            print("Error in edit_artist_submission()")
            abort(500)
@app.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
    form = VenueForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    phone = re.sub('\D', '', phone)  # Normalize phone number
    genres = form.genres.data
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()

    if not form.validate():
        flash(form.errors)
        return redirect(url_for('edit_venue_submission', venue_id=venue_id))

    else:
        error_in_update = False

        try:
            # Retrieve the existing venue object
            venue = Venue.load(db, venue_id)

            # Update venue fields
            venue.name = name
            venue.city = city
            venue.state = state
            venue.address = address
            venue.phone = phone
            venue.seeking_talent = seeking_talent
            venue.seeking_description = seeking_description
            venue.image_link = image_link
            venue.website = website
            venue.facebook_link = facebook_link

            # Clear existing genres
            venue.genres = []

            # Assign genres
            for genre in genres:
                venue.genres.append(genre)

            # Attempt to save changes
            venue.store(db)

        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_venue_submission()')

        if not error_in_update:
            flash('Venue ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_venue', venue_id=venue_id))
        else:
            flash('An error occurred. Venue ' + name + ' could not be updated.')
            print("Error in edit_venue_submission()")
            abort(500)
#  Create Artist
#  ----------------------------------------------------------------
@app.route('/artists/create', methods=['GET'])
def create_artist_form():
    form = ArtistForm()
    return render_template('forms/new_artist.html', form=form)

@app.route('/artists/create', methods=['POST'])
def create_artist_submission():
    form = ArtistForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    phone = form.phone.data
    phone = re.sub('\D', '', phone)  # Normalize phone number
    genres = form.genres.data
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()

    if not form.validate():
        flash(form.errors)
        return redirect(url_for('create_artist_submission'))

    else:
        error_in_insert = False

        try:
            # Create a new artist document
            new_artist = Artist(name=name, city=city, state=state, phone=phone,
                                seeking_venue=seeking_venue, seeking_description=seeking_description,
                                image_link=image_link, website=website, facebook_link=facebook_link)

            # Assign genres to the new artist
            for genre in genres:
                new_artist.genres.append(genre)

            # Save the new artist to the database
            new_artist.store(db)

        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_artist_submission()')

        if not error_in_insert:
            flash('Artist ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Artist ' + name + ' could not be listed.')
            print("Error in create_artist_submission()")
            abort(500)

@app.route('/artists/<artist_id>/delete', methods=['GET'])
def delete_artist(artist_id):
    # Deletes an artist based on AJAX call from the artist page
    artist = Artist.query.get(artist_id)
    if not artist:
        # User somehow faked this call, redirect home
        return redirect(url_for('index'))
    else:
        error_on_delete = False
        # Need to hang on to artist name since it will be lost after delete
        artist_name = artist.name
        try:
            # Delete the artist document
            artist.delete()
        except Exception as e:
            error_on_delete = True
            print(f"Error deleting artist: {e}")
        if error_on_delete:
            flash(f'An error occurred deleting artist {artist_name}.')
            print("Error in delete_artist()")
            abort(500)
        else:
            # Return JSON response indicating successful deletion
            return jsonify({
                'deleted': True,
                'url': url_for('artists')
                })  # Assuming there's a route named 'artists' to list all artists
#  Shows
#  ----------------------------------------------------------------
@app.route('/shows')
def shows():
    # displays list of shows at /shows
    data = []
    shows = Show.view('_all_docs', include_docs=True)  # Assuming you have a view that emits all Show documents

    for show in shows:
        # Extract relevant data from the Show document
        venue_id = show.venue.id
        venue_name = show.venue.name
        artist_id = show.artist.id
        artist_name = show.artist.name
        artist_image_link = show.artist.image_link
        start_time = show.start_time

        data.append({
            "venue_id": venue_id,
            "venue_name": venue_name,
            "artist_id": artist_id,
            "artist_name": artist_name,
            "artist_image_link": artist_image_link,
            "start_time": start_time.isoformat()  # Assuming ISO 8601 format for datetime
        })

    # Render the template with the show data
    return render_template('pages/shows.html', shows=data)  
@app.route('/shows/create', methods=['GET'])
def create_shows():
    # renders form.
    form = ShowForm()
    return render_template('forms/new_show.html', form=form)

@app.route('/shows/create', methods=['POST'])
def create_show_submission():
    # Extract data from the request
    form = ShowForm()

    artist_id = form.artist_id.data.strip()
    venue_id = form.venue_id.data.strip()
    start_time = form.start_time.data

    if not artist_id or not venue_id or not start_time:
        return jsonify({'error': 'Missing data in request'}), 400

    try:
        # Check if both artist and venue exist
        artist = Artist.load(artist_id)
        venue = Venue.load(venue_id)

        if not artist or not venue:
            return jsonify({'error': 'Artist or Venue not found'}), 404

        # Create the show document
        show = Show(
            start_time=start_time,
            artist={
                'id': artist_id,
                'name': artist.name,
                'image_link': artist.image_link
            },
            venue={
                'id': venue_id,
                'name': venue.name
            }
        )
        show.store(db)  # Save the show document to the database
        if artist and venue:
            # Add the show to the artist's and venue's shows list
            artist.shows.append({'venue_id': venue_id, 'start_time': start_time})
            artist.store(db) 
            venue.shows.append({'artist_id': artist_id, 'start_time': start_time})
            venue.store(db)
        return jsonify({'success': True}), 201  # Return success response
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Return error response



@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
