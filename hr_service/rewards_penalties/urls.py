from django.urls import path
from .views import RewardListCreateView, PenaltyListCreateView, RewardRetrieveUpdateDestroyView, PenaltyRetrieveUpdateDestroyView, UserPenaltiesListView, UserRewardsListView

app_name = 'rewards_penalties'

urlpatterns = [
    # Rewards
    path('rewards/', RewardListCreateView.as_view(), name='reward-list-create'),
    path('rewards/<str:id>/', RewardRetrieveUpdateDestroyView.as_view(), name='reward-detail'),  # <str:id> matches CharField PK
    
    # Penalties
    path('penalties/', PenaltyListCreateView.as_view(), name='penalty-list-create'),
    path('penalties/<str:id>/', PenaltyRetrieveUpdateDestroyView.as_view(), name='penalty-detail'),
    # Add these paths to hr/rewards_penalties/urls.py inside the urlpatterns list

    # User-specific endpoints
    path('user/rewards/', UserRewardsListView.as_view(), name='user-rewards-list'),
    path('user/penalties/', UserPenaltiesListView.as_view(), name='user-penalties-list'),
]