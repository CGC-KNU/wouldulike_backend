from django.db import models

class Notification(models.Model):
    content = models.TextField()
    scheduled_time = models.DateTimeField()
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content