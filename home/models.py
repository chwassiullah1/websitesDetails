from django.db import models


# Create your models here.
class ProcessTwoJobs(models.Model):
    urls = models.TextField()
    unique_emails = models.TextField(null=True, blank=True)
    unique_links = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    status = models.IntegerField(null=True)
    created_at = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "processtwojobs"


class EmailDetails(models.Model):
    input_emails = models.TextField(null=True, blank=True)
    email_detail = models.TextField(null=True, blank=True)
    domain = models.TextField(null=True, blank=True)
    type = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_details"
