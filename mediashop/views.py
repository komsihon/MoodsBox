import base64
import hashlib
import random
import string
import time
import logging
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.contrib import messages
from django.core.paginator import PageNotAnInteger, EmptyPage, Paginator
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView

from ikwen.conf.settings import WALLETS_DB_ALIAS
from ikwen.core.constants import CONFIRMED, COMPLETE
from ikwen.core.views import HybridListView
from ikwen.core.utils import get_service_instance, as_matrix
from ikwen.billing.models import MoMoTransaction
from ikwen.billing.mtnmomo.views import MTN_MOMO

from mediashop.models import Order, Download
from mediastore.models import Album, Song, Artist

logger = logging.getLogger('ikwen')

COZY = "Cozy"
COMPACT = "Compact"
COMFORTABLE = "Comfortable"


class Home(TemplateView):
    template_name = 'mediashop/home.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        try:
            main_album = Album.objects.select_related('artist').get(is_main=True)
        except:
            main_album = Album.objects.select_related('artist').filter(is_active=True).order_by('-id')[0]
        album_list = Album.objects.exclude(pk=main_album.id).filter(is_active=True).order_by('-id')
        order_id = self.request.session.get('order_id')
        if order_id:
            timeout = getattr(settings, 'SECURE_LINK_TIMEOUT', 90)
            ninety_mn_ago = datetime.now() - timedelta(minutes=timeout)
            try:
                order = Order.objects.get(pk=order_id, status=COMPLETE, created_on__lte=ninety_mn_ago)
            except Order.DoesNotExist:
                order = None
            context['order'] = order
        context['main_album'] = main_album
        context['album_list'] = album_list
        return context


class AlbumList(HybridListView):
    template_name = 'mediashop/music_item_detail.html'

    def get_context_data(self, **kwargs):
        context = super(AlbumList, self).get_context_data(**kwargs)
        slug = kwargs.get('slug')
        if slug:
            artist = get_object_or_404(Artist, slug=slug)
            album_list = Album.objects.select_related('artist').filter(artist=artist).order_by('-id')
            song_list = Song.objects.select_related('artist').filter(artist=artist, album=None).order_by('-id')
        else:
            album_list = Album.objects.select_related('artist').all().order_by('-id')[:20]
            song_list = Song.objects.select_related('artist').filter(album=None)[:20].order_by('-id')
        context['album_list'] = album_list
        context['song_list'] = song_list
        return context


class SongList(HybridListView):
    template_name = 'mediashop/song_list.html'
    html_results_template_name = 'mediashop/snippets/song_list_results.html'

    def _get_row_len(self):
        config = get_service_instance().config
        if config.theme and config.theme.display == COMFORTABLE:
            return 2
        elif config.theme and config.theme.display == COZY:
            return 3
        return 4

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        if slug:
            artist = get_object_or_404(Artist, slug=slug)
            queryset = Song.objects.select_related('artist').filter(artist=artist, album=None).order_by('-id')
        else:
            queryset = Song.objects.select_related('artist').filter(is_active=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(SongList, self).get_context_data(**kwargs)
        slug = kwargs.get('slug')
        queryset = context['object_list']
        page_size = 9 if self.request.user_agent.is_mobile else 15
        if slug:
            artist = get_object_or_404(Artist, slug=slug)
            album_list = Album.objects.select_related('artist').filter(artist=artist).order_by('-id')
            context['album_list'] = album_list
        paginator = Paginator(queryset, page_size)
        products_page = paginator.page(1)
        context['products_page'] = products_page
        context['product_list_as_matrix'] = as_matrix(products_page.object_list, self._get_row_len())
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('format') == 'html_results':
            page_size = 9 if self.request.user_agent.is_mobile else 15
            queryset = self.get_queryset()
            product_queryset = self.get_search_results(queryset, max_chars=4)
            paginator = Paginator(product_queryset, page_size)
            page = self.request.GET.get('page')
            try:
                products_page = paginator.page(page)
                context['product_list_as_matrix'] = as_matrix(products_page.object_list, self._get_row_len())
            except PageNotAnInteger:
                products_page = paginator.page(1)
                context['product_list_as_matrix'] = as_matrix(products_page.object_list, self._get_row_len())
            except EmptyPage:
                products_page = paginator.page(paginator.num_pages)
                context['product_list_as_matrix'] = as_matrix(products_page.object_list, self._get_row_len())
            context['products_page'] = products_page
            return render(self.request, 'shopping/snippets/product_list_results.html', context)
        else:
            return super(SongList, self).render_to_response(context, **response_kwargs)


class MusicItemDetail(TemplateView):
    template_name = 'mediashop/music_item_detail.html'

    def get_context_data(self, **kwargs):
        context = super(MusicItemDetail, self).get_context_data(**kwargs)
        artist_slug = kwargs.get('artist_slug')
        item_slug = kwargs.get('item_slug')
        artist = get_object_or_404(Artist, slug=artist_slug)
        try:
            item = Album.objects.select_related('artist').get(artist=artist, slug=item_slug, is_active=True)
        except Album.DoesNotExist:
            try:
                item = Song.objects.select_related('artist', 'album').get(artist=artist, slug=item_slug, is_active=True)
            except:
                raise Http404("No such item found")
        context['product'] = item
        return context


class Cart(TemplateView):
    template_name = 'mediashop/cart.html'


class DownloadView(TemplateView):
    template_name = 'mediashop/download.html'

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == 'log_download':
            now = datetime.now()
            order_id = request.GET['order_id']
            link = request.GET['link']
            order = Order.objects.get(pk=order_id)
            created_on = now.strftime('%Y-%m-%d %H:%M:%S')
            download = Download(order=order, link=link, created_on=created_on)
            order.download_list.append(download)
            order.save()
        return super(DownloadView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(DownloadView, self).get_context_data(**kwargs)
        order_id = kwargs.get('order_id')
        if not order_id and not getattr(settings, 'DEBUG', False):
            return HttpResponseRedirect(reverse('home'))
        self.request.session['order_id'] = order_id
        order = get_object_or_404(Order, pk=order_id)
        diff = datetime.now() - order.created_on
        if diff.total_seconds() >= 3600:
            order.is_more_than_one_hour_old = True
        context['order'] = order
        return context


def set_momo_order_checkout(request, *args, **kwargs):
    service = get_service_instance()
    config = service.config
    item_id_list = request.POST.get('item_id_list')
    album_list = []
    song_list = []
    total_cost = 0

    if item_id_list:
        item_id_list = item_id_list.split(',')
        for pk in item_id_list:
            try:
                album = Album.objects.get(pk=pk)
                total_cost += album.cost
                album_list.append(album)
            except:
                try:
                    song = Song.objects.get(pk=pk)
                    total_cost += song.cost
                    song_list.append(song)
                except:
                    continue

    order = Order.objects.create(total_cost=total_cost, album_list=album_list, song_list=song_list)
    model_name = 'mediashop.Order'
    mean = request.GET.get('mean', MTN_MOMO)
    signature = ''.join([random.SystemRandom().choice(string.ascii_letters + string.digits) for i in range(16)])
    MoMoTransaction.objects.using(WALLETS_DB_ALIAS).filter(object_id=order.id).delete()
    tx = MoMoTransaction.objects.using(WALLETS_DB_ALIAS)\
        .create(service_id=service.id, type=MoMoTransaction.CASH_OUT, amount=total_cost, phone='N/A', model=model_name,
                object_id=order.id, task_id=signature, wallet=mean, username=request.user.username, is_running=True)
    notification_url = service.url + reverse('mediashop:confirm_checkout', args=(tx.id, signature))
    logger.debug(notification_url)
    cancel_url = service.url + reverse('mediashop:cart')
    return_url = service.url + reverse('mediashop:download', args=(order.id, ))
    gateway_url = getattr(settings, 'IKWEN_PAYMENT_GATEWAY_URL', 'http://payment.ikwen.com/v1')
    endpoint = gateway_url + '/request_payment'
    params = {
        'username': getattr(settings, 'IKWEN_PAYMENT_GATEWAY_USERNAME', service.project_name_slug),
        'amount': total_cost,
        'merchant_name': config.company_name,
        'notification_url': notification_url,
        'return_url': return_url,
        'cancel_url': cancel_url,
        'user_id': request.user.username
    }
    try:
        r = requests.get(endpoint, params)
        resp = r.json()
        token = resp.get('token')
        if token:
            next_url = gateway_url + '/checkoutnow/' + resp['token'] + '?mean=' + mean
        else:
            logger.error("%s - Init payment flow failed with URL %s and message %s" % (service.project_name, r.url, resp['errors']))
            messages.error(request, resp['errors'])
            next_url = cancel_url
    except:
        logger.error("%s - Init payment flow failed with URL." % service.project_name, exc_info=True)
        next_url = cancel_url
    return HttpResponseRedirect(next_url)


def confirm_checkout(request, *args, **kwargs):
    status = request.GET['status']
    message = request.GET['message']
    operator_tx_id = request.GET['operator_tx_id']
    phone = request.GET['phone']
    tx_id = kwargs['tx_id']
    try:
        tx = MoMoTransaction.objects.using(WALLETS_DB_ALIAS).get(pk=tx_id)
        if not getattr(settings, 'DEBUG', False):
            tx_timeout = getattr(settings, 'IKWEN_PAYMENT_GATEWAY_TIMEOUT', 15) * 60
            expiry = tx.created_on + timedelta(seconds=tx_timeout)
            if datetime.now() > expiry:
                return HttpResponse("Transaction %s timed out." % tx_id)
    except:
        raise Http404("Transaction %s not found" % tx_id)

    callback_signature = kwargs.get('signature')
    no_check_signature = request.GET.get('ncs')
    if getattr(settings, 'DEBUG', False):
        if not no_check_signature:
            if callback_signature != tx.task_id:
                return HttpResponse('Invalid transaction signature')
    else:
        if callback_signature != tx.task_id:
            return HttpResponse('Invalid transaction signature')

    if status != MoMoTransaction.SUCCESS:
        return HttpResponse("Notification for transaction %s received with status %s" % (tx_id, status))

    tx.status = status
    tx.message = message
    tx.processor_tx_id = operator_tx_id
    tx.phone = phone
    tx.is_running = False
    tx.save()

    order_id = tx.object_id
    order = Order.objects.get(pk=order_id)
    mean = tx.wallet
    service = get_service_instance()

    # config = service.config
    amount = tx.amount * (100 - 3) / 100

    service.raise_balance(amount, mean)
    tx = MoMoTransaction.objects.using('wallets').get(service_id=service.id, object_id=order_id)
    order.phone = tx.phone
    order.mean = mean
    song_list = []
    timeout = getattr(settings, 'SECURE_LINK_TIMEOUT', 90)
    expires = int(time.time()) + timeout * 60
    while True:
        try:
            order = Order.objects.get(expires=expires)
            expires += 1
        except:
            break

    order.expires = expires
    for album in order.album_list:
        if album.archive.name:
            archive = Song(title='%s Full Album' % album.title)
            filename = album.archive.name
            archive.download_link = generate_download_link(filename, expires)
            song_list.append(archive)

    for song in order.song_list:
        filename = song.media.name
        song.download_link = generate_download_link(filename, expires)
        song_list.append(song)
    order.song_list = song_list
    order.status = CONFIRMED
    order.save()
    return HttpResponse("Notification received")


def generate_download_link(filename, expires):
    if not filename:
        return
    secret = getattr(settings, 'SECURE_LINK_SECRET', 'enigma')
    input_string = '%d%s %s' % (expires, '/' + filename, secret)
    m = hashlib.md5()
    m.update(input_string)
    md5 = base64.b64encode(m.digest())
    md5 = md5.replace('=', '').replace('+', '-').replace('/', '_')
    static_url = getattr(settings, 'SECURE_LINK_BASE_URL', 'http://cdn.ikwen.com/')
    link = static_url + filename + '?md5=' + md5 + '&expires=%d' % expires
    return link
