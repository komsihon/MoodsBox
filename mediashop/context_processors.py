from django.conf import settings
from django.core.cache import cache
from mediastore.models import Album


def album_count(request):
    count = cache.get('album_count')
    if not count:
        count = Album.objects.filter(is_active=True).count()
        if not getattr(settings, 'DEBUG', False):
            cache.set('album_count', count)
    return {
        'album_count': count,
    }

