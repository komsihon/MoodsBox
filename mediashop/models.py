
from django.db import models
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.constants import PENDING
from ikwen.core.models import Model, AbstractWatchModel
from ikwen.accesscontrol.models import Member


class Order(Model):
    member = models.ForeignKey(Member, blank=True, null=True, related_name='orders')
    phone = models.CharField(max_length=15, blank=True, null=True)
    album_list = ListField(EmbeddedModelField("mediastore.Album"))
    song_list = ListField(EmbeddedModelField("mediastore.Song"))
    download_list = ListField(EmbeddedModelField("Download"))
    total_cost = models.IntegerField(default=0)
    expires = models.IntegerField(default=0, db_index=True)
    mean = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=15, default=PENDING)
    tags = models.CharField(max_length=150, blank=True, null=True, db_index=True)


class Download(Model):
    order = models.ForeignKey(Order)
    link = models.CharField(max_length=150)
