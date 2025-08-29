# # apps/core/signals.py
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.core.mail import send_mail
# from care_coordination.models import Shift  # Corrected import

# @receiver(post_save, sender=Shift)
# def notify_shift_change(sender, instance, **kwargs):
#     if instance.state == 'reallocated':
#         send_mail(
#             'Shift Reassigned',
#             f'Shift reassigned to {instance.carer.username}.',
#             'from@lumina-care.com',
#             [instance.carer.email],
#         )