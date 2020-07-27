from django.contrib import admin


class ArtistAdmin(admin.ModelAdmin):
    fields = ('name', )


class AlbumAdmin(admin.ModelAdmin):
    fields = ('artist', 'title', 'release', 'cost', 'is_main', 'show_on_home')


class SongAdmin(admin.ModelAdmin):
    fields = ('artist', 'album', 'title', 'cost', 'show_on_home', )
