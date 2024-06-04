import json

from djongo import models

from djongo import models


class DomainsData(models.Model):
    _id = models.ObjectIdField(primary_key=True)  # Use "_id" for MongoDB
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "domains_data"
        app_label = 'process_one'



# def save_domain_if_unique(final_json):
#     """
#     Parses JSON, checks for domain existence, and creates a DomainQueue instance only if unique.
#
#     Args:
#         final_json (str): The JSON string containing domain data.
#
#     Returns:
#         DomainQueue: The created instance if unique, otherwise None.
#
#     Raises:
#         ValueError: If the JSON string is invalid.
#     """
#
#     try:
#         final_json_data = json.loads(final_json)
#         domain = final_json_data.get('domain')
#     except json.JSONDecodeError:
#         raise ValueError("Invalid JSON string provided")
#
#     if domain:
#         # Check for existing domain using case-insensitive search
#         existing_domain = DomainQueue.objects.filter(data__domain__iexact=domain).first()
#         if not existing_domain:
#             instance = DomainQueue.objects.create(data=final_json_data)
#             return instance
#         else:
#             print(f"Domain '{domain}' already exists, skipping...")
#     else:
#         print("No 'domain' key found in JSON data")
#
#     return None
