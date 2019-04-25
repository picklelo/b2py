from datetime import datetime
import hashlib


def construct_url(base: str, endpoint: str) -> str:
  """Construct a URL from a base URL and an API endpoint.

  Args:
    base: The root address, e.g. http://api.backblaze.com/b2api/v1.
    endpoint: The path of the endpoint, e.g. /list_buckets.

  Returns:
    A URL based on the info.
  """
  return ''.join((base, endpoint))


def read_file(file_name: str) -> str:
  """Reads the bytes of a file.

  Args:
    file_name: The file to read.

  Returns:
    The bytes of the file.
  """
  with open(file_name, 'rb') as f:
    return f.read()


def write_file(file_name: str, contents: str):
  """Reads the bytes of a file.

  Args:
    file_name: The file to read.

  Returns:
    The bytes of the file.
  """
  with open(file_name, 'wb') as f:
    return f.write(contents)


def sha1(contents: str) -> str:
  """
  Args:
    contents: The bytes to hash.

  Returns:
    The sha1 hash of the contents.
  """
  return hashlib.sha1(contents).hexdigest()
