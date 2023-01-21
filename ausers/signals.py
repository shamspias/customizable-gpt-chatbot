from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    if created:
        Customer.objects.create(user=instance, sex="male")
        print("Customer created")


@receiver(post_save, sender=User)
def save_customer_profile(sender, instance, **kwargs):
    instance.profile.save()


post_save.connect(create_customer_profile, sender=User)
post_save.connect(save_customer_profile, sender=User)
