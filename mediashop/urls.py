
from django.conf.urls import patterns, url
from mediashop.views import set_momo_order_checkout, confirm_checkout, DownloadView

urlpatterns = patterns(
    '',
    url(r'^download/(?P<order_id>[-\w]+)$', DownloadView.as_view(), name='download'),
    url(r'^set_checkout$', set_momo_order_checkout),
    url(r'^confirm_checkout/(?P<tx_id>[-\w]+)/(?P<signature>[-\w]+)$', confirm_checkout, name='confirm_checkout'),
)
