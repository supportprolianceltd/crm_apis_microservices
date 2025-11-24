from rest_framework import serializers
from .models import Category, Tag, Article

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'
        read_only_fields = ('created_at',)

class ArticleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags_list = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'view_count')

    def get_tags_list(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_author_name(self, obj):
        return f"{obj.author_first_name} {obj.author_last_name}".strip()

class ArticleCreateSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True
    )

    class Meta:
        model = Article
        fields = ('title', 'content', 'excerpt', 'category', 'tags', 'status',
                 'featured_image', 'reading_time', 'published_at')

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        current_user = self.context.get('current_user')

        if current_user:
            validated_data.update({
                'author_id': current_user['id'],
                'author_first_name': current_user['first_name'],
                'author_last_name': current_user['last_name'],
                'author_email': current_user['email'],
            })

        article = Article.objects.create(**validated_data)

        # Handle tags
        for tag_name in tags_data:
            tag, created = Tag.objects.get_or_create(name=tag_name.lower())
            article.tags.add(tag)

        return article

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            # Clear existing tags
            instance.tags.clear()
            # Add new tags
            for tag_name in tags_data:
                tag, created = Tag.objects.get_or_create(name=tag_name.lower())
                instance.tags.add(tag)

        return instance

class ArticleListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name = serializers.SerializerMethodField()
    tags_count = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ('id', 'title', 'slug', 'excerpt', 'author_name', 'category_name',
                 'status', 'published_at', 'created_at', 'view_count', 'tags_count')

    def get_author_name(self, obj):
        return f"{obj.author_first_name} {obj.author_last_name}".strip()

    def get_tags_count(self, obj):
        return obj.tags.count()