from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.auth.decorators import permission_required, user_passes_test

from ikwen.flatpages.views import FlatPageView
from ikwen.billing.views import TransactionLog
from mediashop.views import Home

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^shop/', include('mediashop.urls', namespace='mediashop')),
    url(r'^laakam/store/', include('mediastore.urls', namespace='mediastore')),

    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^billing/', include('ikwen.billing.urls', namespace='billing')),

   url(r'^billing/transactions/$', permission_required('mediashop.ik_view_dashboard')(TransactionLog.as_view()), name='dashboard'),
   url(r'^ikwen/theming/', include('ikwen.theming.urls', namespace='theming')),
   url(r'^ikwen/cashout/', include('ikwen.cashout.urls', namespace='cashout')),
   url(r'^ikwen/', include('ikwen.core.urls', namespace='ikwen')),

    url(r'^page/(?P<url>[-\w]+)/$', FlatPageView.as_view(), name='flatpage'),
    url(r'^$', Home.as_view(), name='home'),
)
