from django.contrib import admin
from .models import Category, Tag, Article

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author_name', 'category', 'status', 'published_at', 'view_count')
    list_filter = ('status', 'category', 'published_at')
    search_fields = ('title', 'content', 'author_first_name', 'author_last_name')
    ordering = ('-published_at',)
    readonly_fields = ('view_count', 'created_at', 'updated_at')

    def author_name(self, obj):
        return f"{obj.author_first_name} {obj.author_last_name}".strip()
    author_name.short_description = 'Author'