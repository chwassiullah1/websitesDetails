from django.db import models
import datetime


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
        app_label = 'home'


class EmailDetails(models.Model):
    input_emails = models.TextField(null=True, blank=True)
    email_detail = models.TextField(null=True, blank=True)
    domain = models.TextField(null=True, blank=True)
    type = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_details"
        app_label = 'home'


class DomainQueue(models.Model):
    domain = models.TextField(null=True, blank=True)
    processed = models.BooleanField(null=True, blank=True)
    priority = models.IntegerField(default=1, null=True, blank=True)
    process_start = models.DateTimeField(null=True, blank=True)
    process_finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "domain_queue"
        app_label = 'home'

    def start_process(self):
        self.start_time = datetime.datetime.utcnow()
        self.save()

    def end_process(self):
        self.end_time = datetime.datetime.utcnow()
        self.save()
