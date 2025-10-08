from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until = models.DateField()
    on_trial = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)

    # Default schema for new tenants
    auto_create_schema = True

    class Meta:
       pass