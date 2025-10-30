from celery import shared_task
from .models import Review, ReviewAnalyticsSummary
from .utils.analytics import calculate_sentiment

@shared_task
def update_review_summary(tenant_id):
    # Recalculate totals, averages, sentiment
    summary = ReviewAnalyticsSummary.objects.get(tenant_id=tenant_id)
    summary.total_reviews = Review.objects.filter(tenant_id=tenant_id).count()
    summary.average_rating = Review.objects.filter(tenant_id=tenant_id).aggregate(avg=models.Avg('rating'))['avg'] or 0
    summary.sentiment_score = calculate_sentiment(tenant_id)  # Avg polarity
    summary.save()