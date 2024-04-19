from django.db import models


# Create your models here.
class ProcessTwoJobs(models.Model):
    urls = models.TextField()
    unique_emails = models.TextField(null=True, blank=True)
    unique_links = models.TextField(null=True, blank=True)
    status = models.IntegerField(null=True)
    created_at = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "processtwojobs"
