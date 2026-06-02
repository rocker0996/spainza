"""File handling business logic."""
import os
import uuid
import zipfile
import mimetypes
from werkzeug.utils import secure_filename
from datetime import datetime

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', '7z', 'tar', 'gz'}
ALLOWED_DOCUMENT_WITH_IMAGES = ALLOWED_DOCUMENT_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
ALLOWED_MESSAGE_FILE_EXTENSIONS = ALLOWED_DOCUMENT_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB
MAX_MESSAGE_FILE_SIZE = 25 * 1024 * 1024  # 25MB
MAX_SNIFF_BYTES = 8192

OPENXML_EXPECTED_PREFIX = {
    "docx": "word/",
    "xlsx": "xl/",
    "pptx": "ppt/",
}

ALLOWED_MIME_BY_EXTENSION = {
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "doc": {"application/msword"},
    "xls": {"application/vnd.ms-excel"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "zip": {"application/zip"},
    "rar": {"application/vnd.rar", "application/x-rar-compressed"},
    "7z": {"application/x-7z-compressed"},
    "tar": {"application/x-tar"},
    "gz": {"application/gzip", "application/x-gzip"},
}

GENERIC_ALLOWED_MIME = {"application/octet-stream", "binary/octet-stream"}

# Browser / OS variants that differ from the canonical MIME in ALLOWED_MIME_BY_EXTENSION.
MIME_CANONICAL_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
    "image/x-citrix-png": "image/png",
    "application/x-pdf": "application/pdf",
    "application/x-zip-compressed": "application/zip",
    "application/x-rar-compressed": "application/vnd.rar",
    "text/x-plain": "text/plain",
}


class FileService:
    """Service for handling file uploads and storage."""
    
    def __init__(self):
        self.storage_path = os.path.join(os.getcwd(), 'storage')
        self.messages_path = os.path.join(self.storage_path, 'messages')
        self.documents_path = os.path.join(self.storage_path, 'documents')
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure storage directories exist."""
        os.makedirs(self.messages_path, exist_ok=True)
        os.makedirs(self.documents_path, exist_ok=True)
    
    def _allowed_file(self, filename, allowed_extensions):
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions

    def _extract_extension(self, filename):
        if '.' not in filename:
            return ""
        return filename.rsplit('.', 1)[1].lower()

    def _check_size(self, file, max_size):
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > max_size:
            raise ValueError(f"File too large. Maximum size: {max_size / 1024 / 1024}MB")
        return file_size

    def _read_file_head(self, file, limit=MAX_SNIFF_BYTES):
        file.seek(0)
        head = file.read(limit)
        file.seek(0)
        return head

    def _matches_magic_signature(self, ext, header):
        if ext == "png":
            return header.startswith(b"\x89PNG\r\n\x1a\n")
        if ext in {"jpg", "jpeg"}:
            return header.startswith(b"\xff\xd8\xff")
        if ext == "gif":
            return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
        if ext == "webp":
            return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        if ext == "pdf":
            return header.startswith(b"%PDF-")
        if ext in {"doc", "xls", "ppt"}:
            return header.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1")
        if ext in {"docx", "xlsx", "pptx", "zip"}:
            return (
                header.startswith(b"PK\x03\x04")
                or header.startswith(b"PK\x05\x06")
                or header.startswith(b"PK\x07\x08")
            )
        if ext == "rar":
            return header.startswith(b"Rar!\x1A\x07\x00") or header.startswith(b"Rar!\x1A\x07\x01\x00")
        if ext == "7z":
            return header.startswith(b"\x37\x7A\xBC\xAF\x27\x1C")
        if ext == "gz":
            return header.startswith(b"\x1F\x8B")
        if ext == "tar":
            return len(header) > 262 and header[257:262] == b"ustar"
        if ext == "txt":
            # Text files do not have a stable magic signature.
            # We only reject obvious binary blobs.
            return b"\x00" not in header
        return False

    def _normalize_mime(self, mime: str) -> str:
        base = (mime or "").split(";", 1)[0].strip().lower()
        return MIME_CANONICAL_ALIASES.get(base, base)

    def _validate_declared_mime(self, ext, filename, file, *, magic_ok: bool = False):
        declared_mime = self._normalize_mime(getattr(file, "mimetype", "") or "")
        if not declared_mime:
            return

        guessed_mime, _ = mimetypes.guess_type(filename)
        guessed_mime = self._normalize_mime(guessed_mime or "")

        allowed = set(ALLOWED_MIME_BY_EXTENSION.get(ext, set())) | GENERIC_ALLOWED_MIME
        for value in list(allowed):
            allowed.add(self._normalize_mime(value))
        if guessed_mime:
            allowed.add(guessed_mime)

        if declared_mime in allowed:
            return

        # Trust file signature when the payload matches the extension.
        if magic_ok and ext not in {"txt"}:
            return

        raise ValueError("Invalid file content type")

    def _validate_openxml_container(self, file, ext):
        expected_prefix = OPENXML_EXPECTED_PREFIX.get(ext)
        if not expected_prefix:
            return
        file.seek(0)
        try:
            with zipfile.ZipFile(file.stream, "r") as zf:
                names = [name.lower() for name in zf.namelist()]
        except zipfile.BadZipFile as error:
            file.seek(0)
            raise ValueError("Invalid Office document container") from error
        file.seek(0)

        if "[content_types].xml" not in names:
            raise ValueError("Invalid Office document structure")
        if not any(name.startswith(expected_prefix) for name in names):
            raise ValueError("Invalid Office document structure")

    def _validate_by_content(self, file, ext, filename):
        header = self._read_file_head(file, MAX_SNIFF_BYTES)
        magic_ok = self._matches_magic_signature(ext, header)
        if not magic_ok:
            raise ValueError("Invalid file signature")
        self._validate_declared_mime(ext, filename, file, magic_ok=magic_ok)
        if ext in OPENXML_EXPECTED_PREFIX:
            self._validate_openxml_container(file, ext)
    
    def _generate_unique_filename(self, original_filename):
        """Generate unique filename while preserving extension."""
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return f"{unique_name}.{ext}" if ext else unique_name
    
    def save_message_image(self, file, user_id):
        """Save an image from a message."""
        if not file or file.filename == '':
            raise ValueError("No file provided")
        
        if not self._allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")

        original_name = file.filename or ""
        ext = self._extract_extension(original_name)
        safe_original_name = secure_filename(original_name)
        if not self._extract_extension(safe_original_name) and ext:
            safe_original_name = f"upload.{ext}"
        else:
            ext = self._extract_extension(safe_original_name) or ext
        self._check_size(file, MAX_IMAGE_SIZE)
        self._validate_by_content(file, ext, safe_original_name)
        
        # Create user-specific directory
        user_messages_path = os.path.join(self.messages_path, str(user_id))
        os.makedirs(user_messages_path, exist_ok=True)
        
        # Generate unique filename
        filename = self._generate_unique_filename(safe_original_name)
        filepath = os.path.join(user_messages_path, filename)
        
        # Save file
        file.save(filepath)
        
        # Return relative path for database storage
        return f"messages/{user_id}/{filename}"
    
    def save_message_file(self, file, user_id):
        """Save a file from a message (documents, archives, etc)."""
        if not file or file.filename == '':
            raise ValueError("No file provided")
        
        if not self._allowed_file(file.filename, ALLOWED_MESSAGE_FILE_EXTENSIONS):
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_MESSAGE_FILE_EXTENSIONS)}")

        original_name = file.filename or ""
        ext = self._extract_extension(original_name)
        safe_original_name = secure_filename(original_name)
        if not self._extract_extension(safe_original_name) and ext:
            safe_original_name = f"upload.{ext}"
        else:
            ext = self._extract_extension(safe_original_name) or ext
        self._check_size(file, MAX_MESSAGE_FILE_SIZE)
        self._validate_by_content(file, ext, safe_original_name)
        
        # Create user-specific directory
        user_messages_path = os.path.join(self.messages_path, str(user_id))
        os.makedirs(user_messages_path, exist_ok=True)
        
        # Generate unique filename
        filename = self._generate_unique_filename(safe_original_name)
        filepath = os.path.join(user_messages_path, filename)
        
        # Save file
        file.save(filepath)
        
        # Return relative path and original filename
        return f"messages/{user_id}/{filename}", safe_original_name
    
    def save_document(self, file, user_id, document_type='general'):
        """Save a document file."""
        if not file or file.filename == '':
            raise ValueError("No file provided")
        
        if not self._allowed_file(file.filename, ALLOWED_DOCUMENT_WITH_IMAGES):
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_DOCUMENT_WITH_IMAGES)}")

        original_name = file.filename or ""
        ext = self._extract_extension(original_name)
        safe_original_name = secure_filename(original_name)
        if not self._extract_extension(safe_original_name) and ext:
            safe_original_name = f"upload.{ext}"
        else:
            ext = self._extract_extension(safe_original_name) or ext
        self._check_size(file, MAX_DOCUMENT_SIZE)
        self._validate_by_content(file, ext, safe_original_name)
        
        # Create user-specific directory
        user_docs_path = os.path.join(self.documents_path, str(user_id), document_type)
        os.makedirs(user_docs_path, exist_ok=True)
        
        # Generate unique filename
        filename = self._generate_unique_filename(safe_original_name)
        filepath = os.path.join(user_docs_path, filename)
        
        # Save file
        file.save(filepath)
        
        # Return relative path for database storage
        return f"documents/{user_id}/{document_type}/{filename}"
    
    def get_file_path(self, relative_path):
        """Get absolute file path from relative path."""
        return os.path.join(self.storage_path, relative_path)
    
    def delete_file(self, relative_path):
        """Delete a file by its relative path."""
        try:
            filepath = self.get_file_path(relative_path)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting file: {e}")
        return False
    
    def file_exists(self, relative_path):
        """Check if file exists."""
        filepath = self.get_file_path(relative_path)
        return os.path.exists(filepath)
