import os
import subprocess

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models
from djangotoolbox.fields import ListField

from ikwen.core.models import AbstractWatchModel
from ikwen.core.fields import MultiImageField, EventFileField


def generate_song_preview(filename):
    media_root = getattr(settings, 'MEDIA_ROOT')
    previews_folder = media_root + "previews/songs/"
    if not os.path.exists(previews_folder):
        os.makedirs(previews_folder)
    preview = media_root + "previews/" + filename.replace(media_root, '')
    from ikwen.core.log import ikwen_error_log_filename
    eh = open(ikwen_error_log_filename, 'a')
    command = "ffmpeg -ss 00:00:00 -i %s -t 00:00:30 -c copy %s" % (filename, preview)
    subprocess.call(command.split(' '), stderr=eh)


class Artist(AbstractWatchModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    photo = MultiImageField(upload_to='artists_photos', blank=True, null=True)

    turnover_history = ListField()
    earnings_history = ListField()
    units_sold_history = ListField()

    total_turnover = models.IntegerField(default=0)
    total_earnings = models.IntegerField(default=0)
    total_units_sold = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name

    def _get_image(self):
        return self.photo
    image = property(_get_image)


class Album(AbstractWatchModel):
    artist = models.ForeignKey(Artist)
    title = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(db_index=True)
    cover = MultiImageField(upload_to='albums_covers', blank=True, null=True)
    release = models.DateField(blank=True, null=True, db_index=True)
    archive = models.FileField(upload_to='albums_covers', blank=True, null=True)
    cost = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False)
    show_on_home = models.BooleanField(default=False)
    order_of_appearance = models.IntegerField(default=0)

    turnover_history = ListField()
    earnings_history = ListField()
    units_sold_history = ListField()

    total_turnover = models.IntegerField(default=0)
    total_earnings = models.IntegerField(default=0)
    total_units_sold = models.IntegerField(default=0)

    class Meta:
        unique_together = ('artist', 'title')

    def __unicode__(self):
        return "%s - %s (%d)" % (self.artist.name, self.title, self.release.year)

    def _get_image(self):
        return self.cover
    image = property(_get_image)

    def get_obj_details(self):
        return "XAF %s" % intcomma(self.cost)


class Song(AbstractWatchModel):
    artist = models.ForeignKey(Artist)
    album = models.ForeignKey(Album, blank=True, null=True)
    title = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(db_index=True)
    cover = MultiImageField(upload_to='songs_covers', blank=True, null=True)
    preview = models.FileField(upload_to='song_previews', blank=True, null=True, editable=False)
    media = EventFileField(upload_to='songs', blank=True, null=True, callback=generate_song_preview)
    download_link = models.URLField(blank=True, null=True)
    cost = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_on_home = models.BooleanField(default=False)
    order_of_appearance = models.IntegerField(default=0)

    turnover_history = ListField()
    earnings_history = ListField()
    units_sold_history = ListField()

    total_turnover = models.IntegerField(default=0)
    total_earnings = models.IntegerField(default=0)
    total_units_sold = models.IntegerField(default=0)

    class Meta:
        unique_together = ('artist', 'album', 'title')

    def __unicode__(self):
        return "%s - %s" % (self.title, self.artist.name)

    def _get_image(self):
        if self.cover and self.cover.name:
            return self.cover
        if self.album:
            return self.album.cover
    image = property(_get_image)

    def get_obj_details(self):
        return "XAF %d" % self.cost
