import os

# B2
B2_ACCOUNT_ID = os.getenv('B2_ACCOUNT_ID')
B2_ACCOUNT_KEY = os.getenv('B2_APPLICATION_KEY')

B2_API_HOST = 'https://api.backblazeb2.com'
B2_API_VERSION = '/b2api/v2'
B2_API_BASE = B2_API_HOST + B2_API_VERSION
