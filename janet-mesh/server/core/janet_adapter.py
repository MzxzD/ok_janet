"""
Janet Adapter - Wraps Janet-seed for multi-client support
"""
from typing import Optional, Dict, Any, List
from .session_manager import SessionManager
from .memory_manager import MemoryManager


class JanetAdapter:
    """
    Adapter layer for Janet-seed that supports multiple clients
    with shared LLM but isolated memory contexts.
    """
    
    def __init__(self, llm_model: Any, memory_manager: MemoryManager,
                 session_manager: SessionManager):
        self.llm_model = llm_model
        self.memory_manager = memory_manager
        self.session_manager = session_manager
    
    def generate_response(self, client_id: str, user_text: str) -> str:
        """
        Generate a response for a specific client using their memory context
        """
        # Get or create session
        session = self.session_manager.get_session(client_id)
        if not session:
            client_id = self.session_manager.create_session(client_id)
            session = self.session_manager.get_session(client_id)
        
        # Get client's memory context
        memory_context = self.memory_manager.get_client_memory_context(client_id)
        
        # Build conversation history for LLM
        messages = self._build_messages(memory_context, user_text)
        
        # Generate response using LLM
        response = self._call_llm(messages)
        
        # Save to memory
        self.memory_manager.add_to_memory(client_id, "user", user_text)
        self.memory_manager.add_to_memory(client_id, "assistant", response)
        
        # Update session
        self.session_manager.update_session_activity(client_id)
        
        return response
    
    def _build_messages(self, memory_context: List[Dict[str, Any]], 
                       current_text: str) -> List[Dict[str, str]]:
        """Build message list for LLM from memory context"""
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": "You are Janet, a helpful AI assistant. Be concise and friendly."
        })
        
        # Add conversation history
        for msg in memory_context[-10:]:  # Last 10 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
        
        # Add current user message
        messages.append({"role": "user", "content": current_text})
        
        return messages
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with messages"""
        if isinstance(self.llm_model, dict) and self.llm_model.get("type") == "janet_seed":
            # Use Janet-seed's brain (which uses LiteLLM with DeepSeek)
            janet_brain = self.llm_model["brain"]
            
            # Get the user message (last message)
            user_message = messages[-1]["content"]
            
            # Build context dict from previous messages
            # Janet-seed's generate_response expects context as Dict[str, Any]
            context_dict = {}
            if len(messages) > 1:
                # Convert previous messages to conversation history format
                conversation_history = []
                for msg in messages[:-1]:  # All except the last (user) message
                    if msg.get("role") in ["user", "assistant"]:
                        conversation_history.append({
                            "role": msg.get("role"),
                            "content": msg.get("content", "")
                        })
                if conversation_history:
                    context_dict["conversation_history"] = conversation_history
            
            # Try different methods Janet-seed's brain might use
            try:
                # Method 1: Direct generate_response with user input (primary method)
                if hasattr(janet_brain, 'generate_response'):
                    response = janet_brain.generate_response(
                        user_input=user_message,
                        context=context_dict if context_dict else None
                    )
                    return response
                
                # Method 2: generate_response with just user input
                elif hasattr(janet_brain, 'generate'):
                    response = janet_brain.generate(user_message)
                    return response
                
                # Method 3: Try to use brain's LLM router directly
                elif hasattr(janet_brain, 'llm_router') or hasattr(janet_brain, '_llm_router'):
                    router = getattr(janet_brain, 'llm_router', None) or getattr(janet_brain, '_llm_router', None)
                    if router and hasattr(router, 'generate'):
                        # Convert messages to format LiteLLM expects
                        response = router.generate(messages=messages)
                        if isinstance(response, dict):
                            return response.get("content", str(response))
                        return str(response)
                
                else:
                    raise AttributeError("Janet-seed brain doesn't have expected methods")
                    
            except Exception as e:
                raise RuntimeError(f"Error calling Janet-seed brain: {e}")
        
        elif isinstance(self.llm_model, dict) and self.llm_model.get("type") == "ollama":
            # Ollama API
            client = self.llm_model["client"]
            model_name = self.llm_model["model_name"]
            
            # Convert messages to Ollama format
            response = client.chat(
                model=model_name,
                messages=messages
            )
            return response["message"]["content"]
        
        elif hasattr(self.llm_model, "create_chat_completion"):
            # llama.cpp or similar
            response = self.llm_model.create_chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return response["choices"][0]["message"]["content"]
        
        else:
            # Fallback: try to use as if it's a Janet-seed core
            try:
                # If Janet-seed has a generate_response method
                if hasattr(self.llm_model, "generate_response"):
                    return self.llm_model.generate_response(messages[-1]["content"])
            except:
                pass
            
            # Last resort: simple prompt
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            return f"Response to: {messages[-1]['content']}"
    
    def get_client_context(self, client_id: str) -> Dict[str, Any]:
        """Get full context for a client"""
        session = self.session_manager.get_session(client_id)
        if not session:
            return {}
        
        memory_context = self.memory_manager.get_client_memory_context(client_id)
        
        return {
            "client_id": client_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(memory_context),
            "preferences": session.preferences
        }
