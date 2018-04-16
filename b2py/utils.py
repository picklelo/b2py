from datetime import datetime
import hashlib

def construct_url(base, endpoint):
  """Construct a URL.

  Args:
      base: The root address, e.g. http://api.backblaze.com/b2api/v1.
      endpoint: The path of the endpoint, e.g. /list_buckets.

  Returns:
      A URL based on the info.
  """
  return ''.join((base, endpoint))

def read_file(file_name):
  """Reads the bytes of a file.

  Args:
      file_name: The file to read.

  Returns:
      The bytes of the file.
  """
  with open(file_name, 'rb') as f:
      return f.read()

def sha1(contents):
  """
  Args:
      contents: The bytes to hash.

  Returns:
      The sha1 hash of the contents.
  """
  return hashlib.sha1(contents).hexdigest()
