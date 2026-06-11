import os
import requests
from django.conf import settings
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spamapi.settings') 
django.setup()

api_key = settings.SAFE_BROWSING_API_KEY2

url_api = "https://safebrowsing.googleapis.com/v5/urls:search"
params = {'key': api_key, 'urls': 'http://www.google.com'}

response = requests.get(url_api, params=params)
print("Safe Status:", response.status_code)
print("Safe bytes:", response.content)

params['urls'] = 'http://testsafebrowsing.appspot.com/s/malware.html'
response = requests.get(url_api, params=params)
print("Malware Status:", response.status_code)
print("Malware bytes:", response.content)

