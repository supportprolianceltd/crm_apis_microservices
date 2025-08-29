import logging
from .storage import get_storage_service

logger = logging.getLogger(__name__)

def upload_file_dynamic(file_obj, file_name, content_type="application/octet-stream", storage_type=None):
    """
    Upload files using the selected storage backend.
    storage_type: 'supabase', 's3', 'azure', or 'local'
    """
    storage_service = get_storage_service(storage_type)
    try:
        success = storage_service.upload_file(file_obj, file_name, content_type)
        if success:
            return storage_service.get_public_url(file_name)
        else:
            raise Exception(f"Failed to upload {file_name}")
    except Exception as e:
        logger.error(f"Error uploading file {file_name}: {str(e)}")
        raise





