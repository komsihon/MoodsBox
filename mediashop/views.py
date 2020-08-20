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
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView

from ikwen.conf.settings import WALLETS_DB_ALIAS
from ikwen.core.constants import CONFIRMED, COMPLETE
from ikwen.core.utils import get_service_instance
from ikwen.billing.models import MoMoTransaction
from ikwen.billing.mtnmomo.views import MTN_MOMO

from mediashop.models import Order, Download
from mediastore.models import Album, Song

logger = logging.getLogger('ikwen')


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
                album_list.append(Album.objects.get(pk=pk))
            except:
                try:
                    song_list.append(Song.objects.get(pk=pk))
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
    cancel_url = service.url + reverse('home')
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
    album = order.album_list[0]
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
    for song in album.song_set.all():
        filename = song.media.name
        song.download_link = generate_download_link(filename, expires)
        song_list.append(song)

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
