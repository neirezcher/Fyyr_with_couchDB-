
from couchdb.mapping import Document, TextField, IntegerField, BooleanField, DateTimeField, ListField, Mapping,DictField


class Venue(Document):
    name = TextField()
    city = TextField()
    state = TextField()
    address = TextField()
    phone = TextField()
    image_link = TextField()
    facebook_link = TextField()
    website = TextField()
    seeking_talent = BooleanField(default=False)
    seeking_description = TextField()
    genres = ListField(TextField())
    shows = ListField(DictField(Mapping.build(start_time=DateTimeField(),
                                              id_Artist=TextField())))

class Artist(Document):
    name = TextField()
    city = TextField()
    state = TextField()
    phone = TextField()
    image_link = TextField()
    facebook_link = TextField()
    website = TextField()
    seeking_venue = BooleanField(default=False)
    seeking_description = TextField()
    genres = ListField(TextField())
    shows = ListField(DictField(Mapping.build(start_time=DateTimeField(),
                                          id_Venue=TextField()))) 

class Show(Document):
    start_time = DateTimeField()
    artist = Mapping.build(
        id=TextField(),
        name=TextField(),
        image_link=TextField()
    )
    venue = Mapping.build(
        id=TextField(),
        name=TextField()
    )

