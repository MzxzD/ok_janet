"""
Error Handler - Centralized error handling and logging
"""
import logging
import traceback
from typing import Optional, Dict, Any
from datetime import datetime


class ErrorHandler:
    """Handles errors and provides user-friendly messages"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an error and return user-friendly response"""
        error_id = datetime.now().isoformat()
        
        # Log full error
        self.logger.error(f"Error [{error_id}]: {str(error)}")
        self.logger.debug(traceback.format_exc())
        
        # Determine error type
        error_type = type(error).__name__
        
        # Create user-friendly message
        if isinstance(error, ConnectionError):
            user_message = "Connection error. Please check your network connection."
        elif isinstance(error, FileNotFoundError):
            user_message = "Required file not found. Please check your configuration."
        elif isinstance(error, ImportError):
            user_message = "Missing dependency. Please install required packages."
        elif isinstance(error, RuntimeError):
            user_message = str(error)
        else:
            user_message = "An unexpected error occurred. Please try again."
        
        return {
            "type": "error",
            "error_id": error_id,
            "error_type": error_type,
            "message": user_message,
            "context": context or {}
        }
    
    def handle_model_error(self, model_name: str, error: Exception) -> Dict[str, Any]:
        """Handle model-specific errors"""
        return self.handle_error(error, {"model": model_name})
    
    def handle_connection_error(self, client_id: str, error: Exception) -> Dict[str, Any]:
        """Handle connection errors"""
        return self.handle_error(error, {"client_id": client_id})


# Global error handler instance
error_handler = ErrorHandler()
