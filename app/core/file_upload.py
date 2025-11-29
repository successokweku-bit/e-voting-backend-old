import os
import uuid
from fastapi import UploadFile, HTTPException
from typing import Optional
import shutil

class FileUploadService:
    # Allowed image types and max size (5MB)
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    @staticmethod
    async def save_upload_file(upload_file: UploadFile, upload_dir: str = "uploads") -> Optional[str]:
        """
        Save uploaded file and return the file URL
        """
        try:
            # Create upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Validate file size
            contents = await upload_file.read()
            if len(contents) > FileUploadService.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {FileUploadService.MAX_FILE_SIZE // (1024 * 1024)}MB"
                )
            
            # Validate file extension
            file_extension = os.path.splitext(upload_file.filename)[1].lower()
            if file_extension not in FileUploadService.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Allowed types: {', '.join(FileUploadService.ALLOWED_EXTENSIONS)}"
                )
            
            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                buffer.write(contents)
            
            # Return relative URL (in production, this would be a CDN URL)
            return f"/{upload_dir}/{unique_filename}"
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail="Error uploading file")
    
    @staticmethod
    def delete_file(file_url: str) -> bool:
        """
        Delete uploaded file
        """
        try:
            if file_url and file_url.startswith("/uploads/"):
                file_path = file_url[1:]  # Remove leading slash
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
            return False
        except Exception:
            return False