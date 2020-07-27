
from django.conf.urls import patterns, url
from django.contrib.auth.decorators import permission_required, user_passes_test
from mediastore.views import ArtistList, ChangeArtist, AlbumList, ChangeAlbum, SongList, ChangeSong

urlpatterns = patterns(
    '',
    url(r'^artists/$', permission_required('mediastore.ik_manage_media')(ArtistList.as_view()), name='artist_list'),
    url(r'^artist/$', permission_required('mediastore.ik_manage_media')(ChangeArtist.as_view()), name='change_artist'),
    url(r'^artist/(?P<object_id>[-\w]+)/$', permission_required('mediastore.ik_manage_media')(ChangeArtist.as_view()), name='change_artist'),

    url(r'^albums/$', permission_required('mediastore.ik_manage_media')(AlbumList.as_view()), name='album_list'),
    url(r'^album/$', permission_required('mediastore.ik_manage_media')(ChangeAlbum.as_view()), name='change_album'),
    url(r'^album/(?P<object_id>[-\w]+)/$', permission_required('mediastore.ik_manage_media')(ChangeAlbum.as_view()),
        name='change_album'),

    url(r'^songs/$', permission_required('mediastore.ik_manage_media')(SongList.as_view()), name='song_list'),
    url(r'^song/$', permission_required('mediastore.ik_manage_media')(ChangeSong.as_view()), name='change_song'),
    url(r'^song/(?P<object_id>[-\w]+)/$', permission_required('mediastore.ik_manage_media')(ChangeSong.as_view()), name='change_song'),
)
