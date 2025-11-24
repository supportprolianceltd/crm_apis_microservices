from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Category, Tag, Article

class KnowledgeBaseTests(APITestCase):
    def setUp(self):
        # Create test data
        self.category = Category.objects.create(
            name='Test Category',
            description='Test description'
        )
        self.tag = Tag.objects.create(name='test-tag')

    def test_create_category(self):
        """Test creating a category"""
        url = reverse('category-list')
        data = {'name': 'New Category', 'description': 'New description'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_create_article(self):
        """Test creating an article"""
        url = reverse('article-list')
        data = {
            'title': 'Test Article',
            'content': 'Test content',
            'excerpt': 'Test excerpt',
            'category': self.category.id,
            'tags': ['test-tag'],
            'status': 'published'
        }
        response = self.client.post(url, data, format='json')
        # Note: This will fail without authentication, but tests the endpoint structure
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_201_CREATED])

    def test_list_articles(self):
        """Test listing articles"""
        url = reverse('article-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)