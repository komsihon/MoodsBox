import os
import subprocess

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import gettext_lazy as _
from djangotoolbox.fields import ListField

from ikwen.core.models import AbstractWatchModel, Service
from ikwen.core.fields import MultiImageField, FileField


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
    photo = MultiImageField(upload_to='artists_photos', required_width=300, required_height=300,
                            allowed_extensions=['jpg', 'jpeg'], blank=True, null=True,
                            help_text=_("JPEG Image, 300 &times; 300px"))
    is_active = models.BooleanField(default=True)
    tags = models.TextField(blank=True, null=True)

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

    def to_dict(self):
        val = super(Artist, self).to_dict()
        val['type'] = 'artist'
        val['url'] = reverse('mediashop:artist_detail', args=(self.slug, ))
        image_url = self.photo.name if self.photo.name else Service.LOGO_PLACEHOLDER
        val['image'] = getattr(settings, 'MEDIA_URL') + image_url
        return val


class Album(AbstractWatchModel):
    artist = models.ForeignKey(Artist)
    title = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(db_index=True)
    cover = MultiImageField(upload_to='albums_covers', required_width=300, required_height=300,
                            allowed_extensions=['jpg', 'jpeg'], blank=True, null=True,
                            help_text=_("JPEG Image, 300 &times; 300px"))
    release = models.DateField(blank=True, null=True, db_index=True)
    archive = FileField(upload_to='albums_covers', allowed_extensions=['zip', 'rar', '7z'], blank=True, null=True)
    cost = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False)
    show_on_home = models.BooleanField(default=False)
    order_of_appearance = models.IntegerField(default=0)
    tags = models.TextField(blank=True, null=True)

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

    def to_dict(self):
        val = super(Album, self).to_dict()
        val['type'] = 'album'
        val['url'] = reverse('mediashop:music_item_detail', args=(self.artist.slug, self.slug))
        image_url = self.cover.name if self.cover.name else Service.LOGO_PLACEHOLDER
        val['image'] = getattr(settings, 'MEDIA_URL') + image_url
        return val


class Song(AbstractWatchModel):
    artist = models.ForeignKey(Artist)
    album = models.ForeignKey(Album, blank=True, null=True)
    title = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(db_index=True)
    cover = MultiImageField(upload_to='songs_covers', required_width=300, required_height=300,
                            allowed_extensions=['jpg', 'jpeg'], blank=True, null=True,
                            help_text=_("JPEG Image, 300 &times; 300px"))
    preview = models.FileField(upload_to='song_previews', blank=True, null=True, editable=False)
    media = FileField(upload_to='songs', blank=True, null=True, allowed_extensions=['mp3'], callback=generate_song_preview)
    download_link = models.URLField(blank=True, null=True)
    cost = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_on_home = models.BooleanField(default=False)
    order_of_appearance = models.IntegerField(default=0)
    tags = models.TextField(blank=True, null=True)

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

    def to_dict(self):
        val = super(Song, self).to_dict()
        val['type'] = 'song'
        val['url'] = reverse('mediashop:music_item_detail', args=(self.artist.slug, self.slug))
        image_url = self.image.name if self.image.name else Service.LOGO_PLACEHOLDER
        val['image'] = getattr(settings, 'MEDIA_URL') + image_url
        return val
