import json
from requests import get, post
from requests.auth import HTTPBasicAuth
from typing import Callable, Dict, List, Tuple

from b2py import constants, utils


class B2Error(Exception):
  """General exception type when interacting with the B2 API."""
  pass


class B2:
  """This module is a wrapper around the Backblaze B2 API to read and write files
  to a remote object store."""

  def __init__(self, account_id: str = None, account_key: str = None):
    """To initialize the interface we need access to a B2 account.

    Args:
      account_id: The ID of the account to connect to. This can be found by logging
                  into your Backblaze account. If not provided, we try to read from
                  the ENV variable `B2_ACCOUNT_ID`.
      account_key: The key to perform operations on your behalf. Once you reset
                   it, the old key will no longer work. If not provided, we try
                   to read from the ENV variable `B2_APPLICATION_KEY`.
    """
    self.account_id = account_id or constants.B2_ACCOUNT_ID
    self.account_key = account_key or constants.B2_ACCOUNT_KEY
    if not (self.account_id and self.account_key):
      raise B2Error('No ID or key for B2 account.')

    # Map from a bucket id to a tuple (upload_url, auth_token)
    self.upload_urls = {}
    # Map from a file id to a tuple(upload_url, auth_token)
    self.file_upload_urls = {}

    self.auth_token = None
    self._authorize()

  @property
  def authorized(self) -> bool:
    """
    Returns:
      Whether we have alread authenticated and received a token.
    """
    return bool(self.auth_token)

  def _call(self,
            host: str,
            endpoint: str = '',
            headers: Dict = {},
            body: Dict = {},
            requires_auth: bool = True,
            method: Callable = get,
            **kwargs) -> Dict:
    """Makes a B2 API call and catches any errors.

    Args:
      host: The host to use for the request.
      endpoint: The endpoint to get.
      headers: HTTP headers to send.
      body: Data to send in the body of the request.
      requires_auth: Whether the request requires the user to be logged in.
      method: The type of request for the URL fetch.
      kwargs: Any extra params to pass.

    Returns:
      The return call of the method on the parameters, if successful.
    """
    # Add authorization header
    if requires_auth:
      if not self.authorized:
        raise B2Error(
            'Must be authorized to make this call! Endpoint: {0}'.format(
                endpoint))
      headers['Authorization'] = self.auth_token

    # Call the API
    url = utils.construct_url(host, endpoint)
    response = method(url, headers=headers, params=body, **kwargs)
    if response.status_code >= 400:
      raise B2Error(
          'Received status code {0} making request to url {1}. {2}'.format(
              response.status_code, url, response.json()))

    return response

  def _authorize(self):
    """Authorize the client to access the B2 account."""
    auth = HTTPBasicAuth(self.account_id, self.account_key)
    response = self._call(constants.B2_API_BASE,
                          '/b2_authorize_account',
                          requires_auth=False,
                          auth=auth)
    data = response.json()
    self.auth_token = data['authorizationToken']
    self.api_url = data['apiUrl'] + constants.B2_API_VERSION
    self.download_url = data['downloadUrl']
    self.file_part_size = data['absoluteMinimumPartSize']
    if not self.authorized:
      raise B2Error('Failed to authorize with account id {0} and key {1}')

  def create_bucket(self, bucket_name: str, private: bool = True) -> Dict:
    """Create a new bucket.

    Args:
      bucket_name: The name of the new bucket.
      private: Whether files in the bucket should be all private.

    Returns:
      The new bucket data.
    """
    bucket_type = 'allPrivate' if private else 'allPublic'
    body = {
        'accountId': self.account_id,
        'bucketName': bucket_name,
        'bucketType': bucket_type
    }
    response = self._call(self.api_url, '/b2_create_bucket', body=body)
    return response.json()

  def delete_bucket(self, bucket_id: str):
    """Delete a bucket.

    Args:
      bucket_id: The bucket to delete.
    """
    body = {'accountId': self.account_id, 'bucketId': bucket_id}
    self._call(self.api_url, '/b2_delete_bucket', body=body)

  def list_buckets(self) -> List[Dict]:
    """List all the buckets.

    Returns:
      A list of all buckets in the account.
    """
    body = {'accountId': self.account_id}
    response = self._call(self.api_url, '/b2_list_buckets', body=body)
    return response.json()['buckets']

  def _get_upload_url(self, bucket_id: str):
    """In order to upload a file, we first request an upload URL.

    This method will update the `upload_urls` dict. We cannot upload to a bucket
    until that bucket has an entry in this dict.

    Args:
      bucket_id: The bucket to upload to.
    """
    body = {'bucketId': bucket_id}
    response = self._call(self.api_url, '/b2_get_upload_url', body=body)
    data = response.json()
    self.upload_urls[bucket_id] = (data['uploadUrl'],
                                   data['authorizationToken'])

  def _get_file_part_upload_url(self, file_id: str):
    """Get the URL to upload parts of a large file and save it to a dict.

    Args:
      file_id: The id of the large file.
    """
    body = {'fileId': file_id}
    response = self._call(self.api_url, '/b2_get_upload_part_url', body=body)
    data = response.json()
    self.file_upload_urls[file_id] = (data['uploadUrl'],
                                      data['authorizationToken'])

  def _start_large_file_upload(self,
                               bucket_id: str,
                               file_name: str,
                               content_type: str = None) -> str:
    """For large files, we upload in multiple parts.

    Args:
      bucket_id: The bucket to put the file in.
      file_name: The name of the file in the object store.
      content_type: The value of the Content-Type header to send.

    Returns:
      The file id of the created file.
    """
    body = {
        'bucketId': bucket_id,
        'fileName': file_name,
        'contentType': content_type or 'b2/x-auto'
    }
    response = self._call(self.api_url, '/b2_start_large_file', body=body)
    data = response.json()
    return data['fileId']

  def _upload_large_file_part(self, file_id: str, part_idx: int,
                              contents: str) -> Dict:
    """Upload a chunk of a large file.

    Args:
      upload_url: The url to send the upload request to.
      part_idx: The chunk number.
      contents: The content to write.
    """
    if file_id not in self.file_upload_urls:
      self._get_file_part_upload_url(file_id)
    upload_url, auth_token = self.file_upload_urls[file_id]
    headers = {
        'Authorization': auth_token,
        'X-Bz-Part-Number': str(part_idx),
        'Content-Length': str(len(contents)),
        'X-Bz-Content-Sha1': utils.sha1(contents)
    }
    response = self._call(upload_url,
                          method=post,
                          headers=headers,
                          requires_auth=False,
                          data=contents)
    return response.json()

  def _finish_large_file_upload(self, file_id: str, hashes: List[str]) -> Dict:
    """Finish the upload of a large file.

    Args:
      file_id: The file to finish uploading.
      hashes: A list of SHA1 hashes for the file parts to verify correct upload.

    Returns:
      The file information.
    """
    body = json.dumps({'fileId': file_id, 'partSha1Array': hashes})
    response = self._call(self.api_url,
                          '/b2_finish_large_file',
                          data=body,
                          method=post)
    return response.json()

  def _upload_large_file(self,
                         bucket_id: str,
                         file_name: str,
                         contents: str,
                         content_type: str = None) -> Dict:
    """For large files, we upload in multiple parts.
    We break up the file into chunks and upload each sequentially.

    Args:
      bucket_id: The bucket to put the file in.
      file_name: The name of the file in the object store.
      content_type: The value of the Content-Type header to send.

    Returns:
      Information about the created large file.
    """
    file_id = self._start_large_file_upload(bucket_id, file_name, content_type)
    num_parts = int(len(contents) / self.file_part_size) + 1
    if num_parts < 2:
      raise B2Error('Large file uploads should have at least 2 parts.')

    parts = [
        contents[i * self.file_part_size:(i + 1) * self.file_part_size]
        for i in range(num_parts)
    ]
    hashes = [
        self._upload_large_file_part(file_id, i + 1, part)['contentSha1']
        for i, part in enumerate(parts)
    ]
    return self._finish_large_file_upload(file_id, hashes)

  def upload_file(self,
                  bucket_id: str,
                  file_name: str,
                  contents: str,
                  content_type: str = None) -> Dict:
    """Upload a file to a given bucket.

    Args:
      bucket_id: The bucket to put the file in.
      file_name: The name of the file in the object store.
      contents: The file contents
      content_type: The value of the Content-Type header to send.

    Returns:
      Information about the created file.
    """
    if len(contents) > self.file_part_size:
      return self._upload_large_file(bucket_id, file_name, contents,
                                     content_type)

    if bucket_id not in self.upload_urls:
      self._get_upload_url(bucket_id)
    upload_url, auth_token = self.upload_urls[bucket_id]
    headers = {
        'Authorization': auth_token,
        'X-Bz-File-Name': file_name,
        'Content-Type': content_type or 'b2/x-auto',
        'Content-Length': str(len(contents)),
        'X-Bz-Content-Sha1': utils.sha1(contents)
    }
    response = self._call(upload_url,
                          method=post,
                          headers=headers,
                          requires_auth=False,
                          data=contents)
    return response.json()

  def download_file(self, file_id: str,
                    byte_range: Tuple[int, int] = None) -> str:
    """Downloads a file.

    Args:
      file_id: The Id of the file to download.
      byte_range: Tuple of start and end byte offsets to retrieve.

    Returns:
      The file contents.
    """
    headers = {}
    if byte_range:
      start, end = byte_range
      headers['Range'] = 'bytes={0}-{1}'.format(start, end)
    body = {'fileId': file_id}
    response = self._call(self.download_url,
                          '/b2api/v1/b2_download_file_by_id',
                          headers=headers,
                          body=body)
    return response.content

  def list_files(self,
                 bucket_id: str,
                 start_file_id: str = None,
                 limit: int = None) -> List[Dict]:
    """List files in a bucket.

    Args:
      bucket_id: The bucket to search.
      start_file_id: Id of the first file to list from.
      limit: The maximum number of files returned.

    Returns:
      The files in the bucket.
    """
    body = {
        'bucketId': bucket_id,
    }
    if start_file_id:
      body['startFileId'] = start_file_id
    if limit:
      body['maxFileCount'] = str(limit)
    response = self._call(self.api_url, '/b2_list_file_versions', body=body)
    return response.json()['files']

  def get_file_info(self, file_id: str) -> Dict:
    """Get metadata for a file.

    Args:
      file_id: The file to retrieve.

    Returns:
      The details of the file.
    """
    body = {'fileId': file_id}
    response = self._call(self.api_url, '/b2_get_file_info', body=body)
    return response.json()

  def delete_file(self, file_id: str, file_name: str):
    """Delete a file.

    Args:
      file_id: The Id of the file to delete.
      file_name: The name of the file.
    """
    body = {'fileId': file_id, 'fileName': file_name}
    self._call(self.api_url, '/b2_delete_file_version', body=body)
