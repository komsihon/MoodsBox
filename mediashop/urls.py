
from django.conf.urls import patterns, url
from mediashop.views import Home, MusicItemDetail, set_momo_order_checkout, confirm_checkout, Cart, \
    DownloadView, ArtistList, ArtistDetail, AlbumList, AlbumDetail, MediaList

urlpatterns = patterns(
    '',
    url(r'^$', Home.as_view(), name='home'),
    url(r'^cart$', Cart.as_view(), name='cart'),
    url(r'^download/(?P<order_id>[-\w]+)$', DownloadView.as_view(), name='download'),
    url(r'^set_checkout$', set_momo_order_checkout),
    url(r'^confirm_checkout/(?P<tx_id>[-\w]+)/(?P<signature>[-\w]+)$', confirm_checkout, name='confirm_checkout'),
    url(r'^artists$', ArtistList.as_view(), name='artist_list'),
    url(r'^artists/(?P<slug>[-\w]+)$', ArtistDetail.as_view(), name='artist_detail'),
    url(r'^albums$', AlbumList.as_view(), name='album_list'),
    url(r'^albums/(?P<slug>[-\w]+)$', AlbumDetail.as_view(), name='album_detail'),
    url(r'^songs$', MediaList.as_view(), name='song_list'),
    url(r'^(?P<artist_slug>[-\w]+)/(?P<item_slug>[-\w]+)$', MusicItemDetail.as_view(), name='music_item_detail'),
)
