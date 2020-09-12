from django.template.defaultfilters import slugify
from django.utils.translation import gettext as _

from ikwen.core.views import HybridListView, ChangeObjectBase

from mediastore.models import Artist, Album, Song
from mediastore.admin import ArtistAdmin, AlbumAdmin, SongAdmin


class ArtistList(HybridListView):
    model = Artist


class ChangeArtist(ChangeObjectBase):
    model = Artist
    model_admin = ArtistAdmin
    image_help_text = _("Upload artist photo")

    def after_save(self, request, obj, *args, **kwargs):
        obj.tags = slugify(obj.name).replace('-', ' ')
        obj.save()


class AlbumList(HybridListView):
    model = Album


class ChangeAlbum(ChangeObjectBase):
    model = Album
    model_admin = AlbumAdmin
    label_field = 'title'
    image_help_text = _("Upload album cover image")

    def after_save(self, request, obj, *args, **kwargs):
        is_main = request.GET.get('is_main')
        if is_main:  # There can only on main album at a time
            Album.objects.update(is_main=False)
            obj.is_main = True
        obj.tags = slugify(obj.title).replace('-', ' ')
        obj.save()


class SongList(HybridListView):
    model = Song


class ChangeSong(ChangeObjectBase):
    model = Song
    model_admin = SongAdmin
    label_field = 'title'
    image_help_text = _("Upload song cover image")

    def after_save(self, request, obj, *args, **kwargs):
        obj.tags = slugify(obj.title).replace('-', ' ')
        obj.save()
