# -*- coding: utf-8 -*-
import random
import string
import logging

import requests
import json

from currencies.templatetags.currency import do_currency
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.http import urlunquote
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import TemplateView


from ikwen.core.utils import get_service_instance, parse_paypal_response, EC_ENDPOINT
from ikwen.billing.models import PaymentMean

from mediashop.views import parse_order_info
from mediashop.views import confirm_checkout
from mediashop.models import Order

logger = logging.getLogger('ikwen')


class SetExpressCheckout(TemplateView):
    template_name = 'shopping/paypal/cancel.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def post(self, request, *args, **kwargs):
        service = get_service_instance()
        payment_mean = PaymentMean.objects.get(slug='paypal')
        if getattr(settings, 'DEBUG', False):
            paypal = json.loads(payment_mean.credentials)
        else:
            try:
                paypal = json.loads(payment_mean.credentials)
            except:
                return HttpResponse("Error, Could not parse PayPal parameters.")

        try:
            order = parse_order_info(request)
        except:
            messages.error(request, "Failed to parse order information")
            return HttpResponseRedirect(reverse('mediashop:cart'))

        if getattr(settings, 'UNIT_TESTING', False):
            signature = 'dumb_signature'
        else:
            signature = ''.join([random.SystemRandom().choice(string.ascii_letters + string.digits) for n in range(16)])
        request.session['signature'] = signature
        request.session['return_url'] = service.url + reverse('mediashop:download', args=(order.id, ))

        if getattr(settings, 'UNIT_TESTING', False):
            return HttpResponse(json.dumps({"order_id": order.id}))

        line_items = {}
        for i in range(len(order.album_list)):
            album = order.album_list[i]
            line_items.update({
                "L_PAYMENTREQUEST_0_NAME%d" % i: album.title,
                "L_PAYMENTREQUEST_0_DESC%d" % i: album.title,
                "L_PAYMENTREQUEST_0_AMT%d" % i: do_currency(album.cost, order.currency.code),
                "L_PAYMENTREQUEST_0_QTY%d" % i: 1,
                "L_PAYMENTREQUEST_0_TAXAMT%d" % i: 0,
                "L_PAYMENTREQUEST_0_NUMBER%d" % i: i + 1,
                "L_PAYMENTREQUEST_0_ITEMURL%d" % i: service.url + reverse('mediashop:music_item_detail', args=(album.artist.slug, album.slug, )),
                "L_PAYMENTREQUEST_0_ITEMCATEGORY%d" % i: 'Digital'
            })

        for i in range(len(order.song_list)):
            song = order.song_list[i]
            line_items.update({
                "L_PAYMENTREQUEST_0_NAME%d" % i: song.title,
                "L_PAYMENTREQUEST_0_DESC%d" % i: song.title,
                "L_PAYMENTREQUEST_0_AMT%d" % i: do_currency(song.cost, order.currency.code),
                "L_PAYMENTREQUEST_0_QTY%d" % i: 1,
                "L_PAYMENTREQUEST_0_TAXAMT%d" % i: 0,
                "L_PAYMENTREQUEST_0_NUMBER%d" % i: i + 1,
                "L_PAYMENTREQUEST_0_ITEMURL%d" % i: service.url + reverse('mediashop:music_item_detail', args=(song.artist.slug, song.slug, )),
                "L_PAYMENTREQUEST_0_ITEMCATEGORY%d" % i: 'Digital'
            })

        ec_data = {
            "USER": paypal['username'],
            "PWD": paypal['password'],
            "SIGNATURE": paypal['signature'],
            "METHOD": "SetExpressCheckout",
            "VERSION": 124.0,
            "RETURNURL": service.url + reverse('mediashop:paypal_get_details') + '?order_id=' + order.id,
            "CANCELURL": service.url + reverse('mediashop:cart'),
            "PAYMENTREQUEST_0_PAYMENTACTION": "Sale",
            "PAYMENTREQUEST_0_AMT": do_currency(order.total_cost, order.currency.code),
            "PAYMENTREQUEST_0_ITEMAMT": do_currency(order.total_cost, order.currency.code),
            "PAYMENTREQUEST_0_SHIPPINGAMT": 0,
            "PAYMENTREQUEST_0_TAXAMT": 0,
            "PAYMENTREQUEST_0_CURRENCYCODE": order.currency.code,
            "PAYMENTREQUEST_0_DESC": "Purchase on " + service.project_name
        }
        ec_data.update(line_items)
        try:
            response = requests.post(EC_ENDPOINT, data=ec_data)
            result = parse_paypal_response(response.content.decode('utf-8'))
            ACK = result['ACK']
            if ACK == 'Success' or ACK == 'SuccessWithWarning':
                if getattr(settings, 'DEBUG', False):
                    redirect_url = 'https://www.sandbox.paypal.com/checkoutnow?token=' + result['TOKEN']
                else:
                    redirect_url = 'https://www.paypal.com/checkoutnow?token=' + result['TOKEN']
                return HttpResponseRedirect(redirect_url)
            else:
                order.delete()
                context = self.get_context_data(**kwargs)
                if getattr(settings, 'DEBUG', False):
                    context['paypal_error'] = urlunquote(response.content.decode('utf-8'))
                else:
                    context['paypal_error'] = urlunquote(result['L_LONGMESSAGE0'])
                messages.error(request, 'Initiating PayPal transaction failed.')
                return HttpResponseRedirect(reverse('mediashop:cart'))
        except Exception as e:
            logger.error("%s - PayPal error." % service.project_name, exc_info=True)
            if getattr(settings, 'DEBUG', False):
                raise e
            context = self.get_context_data(**kwargs)
            messages.error(request, 'Could not initiate transaction due to server error. Contact administrator.')
            return render(request, 'shopping/paypal/cancel.html', context)


class GetExpressCheckoutDetails(TemplateView):
    template_name = 'shopping/paypal/confirmation.html'

    def get(self, request, *args, **kwargs):
        service = get_service_instance()
        paypal = json.loads(PaymentMean.objects.get(slug='paypal').credentials)
        paypal_token = request.GET['token']
        ec_data = {
            "USER": paypal['username'],
            "PWD": paypal['password'],
            "SIGNATURE": paypal['signature'],
            "METHOD": "GetExpressCheckoutDetails",
            "VERSION": 124.0,
            "TOKEN": paypal_token
        }
        try:
            response = requests.post(EC_ENDPOINT, data=ec_data)
            result = parse_paypal_response(response.content.decode('utf-8'))
            ACK = result['ACK']
            if ACK == 'Success' or ACK == 'SuccessWithWarning':
                request.session['token'] = paypal_token
                request.session['payer_id'] = request.GET['PayerID']
                context = self.get_context_data(**kwargs)
                context['amount'] = urlunquote(result['PAYMENTREQUEST_0_AMT'])
                return render(request, self.template_name, context)
            else:
                try:
                    Order.objects.get(pk=request.GET['order_id']).delete()
                except Order.DoesNotExist:
                    pass
                context = self.get_context_data(**kwargs)
                if getattr(settings, 'DEBUG', False):
                    context['paypal_error'] = urlunquote(response.content.decode('utf-8'))
                else:
                    context['paypal_error'] = urlunquote(result['L_LONGMESSAGE0'])
                messages.error(request, 'API Error: Confirming PayPal transaction failed.')
                return HttpResponseRedirect(reverse('mediashop:cart'))
        except Exception as e:
            logger.error("%s - PayPal error." % service.project_name, exc_info=True)
            if getattr(settings, 'DEBUG', False):
                raise e
            messages.error(request, 'Server Error: Confirming PayPal transaction failed.')
            return HttpResponseRedirect(reverse('mediashop:cart'))


class DoExpressCheckout(TemplateView):
    template_name = 'shopping/paypal/cancel.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def post(self, request, *args, **kwargs):
        if getattr(settings, 'UNIT_TESTING', False):
            return confirm_checkout(request, signature=request.session['signature'], *args, **kwargs)

        service = get_service_instance()
        paypal = json.loads(PaymentMean.objects.get(slug='paypal').credentials)
        order_id = request.POST['order_id']
        order = Order.objects.get(pk=order_id)
        line_items = {}
        for i in range(len(order.album_list)):
            album = order.album_list[i]
            line_items.update({
                "L_PAYMENTREQUEST_0_NAME%d" % i: album.title,
                "L_PAYMENTREQUEST_0_DESC%d" % i: album.title,
                "L_PAYMENTREQUEST_0_AMT%d" % i: do_currency(album.cost, order.currency.code),
                "L_PAYMENTREQUEST_0_QTY%d" % i: 1,
                "L_PAYMENTREQUEST_0_TAXAMT%d" % i: 0,
                "L_PAYMENTREQUEST_0_NUMBER%d" % i: i + 1,
                "L_PAYMENTREQUEST_0_ITEMURL%d" % i: service.url + reverse('mediashop:music_item_detail', args=(album.artist.slug, album.slug, )),
                "L_PAYMENTREQUEST_0_ITEMCATEGORY%d" % i: 'Digital'
            })

        for i in range(len(order.song_list)):
            song = order.song_list[i]
            line_items.update({
                "L_PAYMENTREQUEST_0_NAME%d" % i: song.title,
                "L_PAYMENTREQUEST_0_DESC%d" % i: song.title,
                "L_PAYMENTREQUEST_0_AMT%d" % i: do_currency(song.cost, order.currency.code),
                "L_PAYMENTREQUEST_0_QTY%d" % i: 1,
                "L_PAYMENTREQUEST_0_TAXAMT%d" % i: 0,
                "L_PAYMENTREQUEST_0_NUMBER%d" % i: i + 1,
                "L_PAYMENTREQUEST_0_ITEMURL%d" % i: service.url + reverse('mediashop:music_item_detail', args=(song.artist.slug, song.slug, )),
                "L_PAYMENTREQUEST_0_ITEMCATEGORY%d" % i: 'Digital'
            })

        ec_data = {
            "USER": paypal['username'],
            "PWD": paypal['password'],
            "SIGNATURE": paypal['signature'],
            "METHOD": "DoExpressCheckoutPayment",
            "VERSION": 124.0,
            "TOKEN": request.session['token'],
            "PAYERID": request.session['payer_id'],
            "PAYMENTREQUEST_0_PAYMENTACTION": "Sale",
            "PAYMENTREQUEST_0_AMT": do_currency(order.total_cost, order.currency.code),
            "PAYMENTREQUEST_0_ITEMAMT": do_currency(order.total_cost, order.currency.code),
            "PAYMENTREQUEST_0_SHIPPINGAMT": 0,
            "PAYMENTREQUEST_0_TAXAMT": 0,
            "PAYMENTREQUEST_0_CURRENCYCODE": order.currency.code,
            "PAYMENTREQUEST_0_DESC": "Purchase on " + service.project_name
        }
        ec_data.update(line_items)
        if getattr(settings, 'DEBUG', False):
            response = requests.post(EC_ENDPOINT, data=ec_data)
            result = parse_paypal_response(response.content.decode('utf-8'))
            ACK = result['ACK']
            if ACK == 'Success' or ACK == 'SuccessWithWarning':
                return confirm_checkout(request, signature=request.session['signature'], *args, **kwargs)
            else:
                try:
                    Order.objects.get(pk=request.POST['order_id']).delete()
                except Order.DoesNotExist:
                    pass
                context = self.get_context_data(**kwargs)
                if getattr(settings, 'DEBUG', False):
                    context['paypal_error'] = urlunquote(response.content.decode('utf-8'))
                else:
                    context['paypal_error'] = urlunquote(result['L_LONGMESSAGE0'])
                messages.error(request, 'API Error: Terminating PayPal transaction failed.')
                return HttpResponseRedirect(reverse('mediashop:cart'))
        else:
            try:
                response = requests.post(EC_ENDPOINT, data=ec_data)
                result = parse_paypal_response(response.content.decode('utf-8'))
                ACK = result['ACK']
                if ACK == 'Success' or ACK == 'SuccessWithWarning':
                    return confirm_checkout(request, signature=request.session['signature'], *args, **kwargs)
                else:
                    try:
                        Order.objects.get(pk=request.POST['order_id']).delete()
                    except Order.DoesNotExist:
                        pass
                    context = self.get_context_data(**kwargs)
                    if getattr(settings, 'DEBUG', False):
                        context['paypal_error'] = urlunquote(response.content.decode('utf-8'))
                    else:
                        context['paypal_error'] = urlunquote(result['L_LONGMESSAGE0'])
                    messages.error(request, 'API Error: Terminating PayPal transaction failed.')
                    return HttpResponseRedirect(reverse('mediashop:cart'))
            except Exception as e:
                logger.error("%s - PayPal error. Order ID: %s" % (service.project_name, order.id), exc_info=True)
                messages.error(request, 'Could not terminate transaction due to server error. Contact administrator.')
                return HttpResponseRedirect(reverse('mediashop:cart'))
