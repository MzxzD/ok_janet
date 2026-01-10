"""
Janet Adapter - Wraps Janet-seed for multi-client support
"""
from typing import Optional, Dict, Any, List
from .session_manager import SessionManager
from .memory_manager import MemoryManager
import json
from pathlib import Path
import os


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
        self._janet_personality = self._load_janet_personality()
        
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "init",
                    "hypothesisId": "A",
                    "location": "janet_adapter.py:__init__",
                    "message": "JanetAdapter initialized",
                    "data": {
                        "personality_loaded": self._janet_personality is not None,
                        "personality_keys": list(self._janet_personality.keys()) if self._janet_personality else None
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
    
    def _load_janet_personality(self) -> Optional[Dict]:
        """Load Janet's personality and constitution"""
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        # #endregion
        
        # Try to find personality.json in janet-seed
        possible_paths = [
            Path("janet-seed/constitution/personality.json"),
            Path("../janet-seed/constitution/personality.json"),
            Path("../../janet-seed/constitution/personality.json"),
        ]
        
        # Also check if janet-seed is in the same parent directory
        current_dir = Path.cwd()
        if "janet-mesh" in str(current_dir):
            # We're in janet-mesh, look for janet-seed sibling
            parent = current_dir.parent
            possible_paths.append(parent / "janet-seed" / "constitution" / "personality.json")
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "init",
                    "hypothesisId": "B",
                    "location": "janet_adapter.py:_load_janet_personality",
                    "message": "Searching for personality.json",
                    "data": {
                        "current_dir": str(current_dir),
                        "paths_checked": [str(p) for p in possible_paths],
                        "paths_exist": [str(p) if p.exists() else None for p in possible_paths]
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        personality = json.load(f)
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "init",
                                "hypothesisId": "B",
                                "location": "janet_adapter.py:_load_janet_personality",
                                "message": "Personality loaded successfully",
                                "data": {
                                    "path": str(path),
                                    "has_axioms": "constitution" in personality and "axioms" in personality.get("constitution", {}),
                                    "axiom_count": len(personality.get("constitution", {}).get("axioms", [])) if "constitution" in personality else 0
                                },
                                "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                            }) + "\n")
                    except: pass
                    # #endregion
                    return personality
                except Exception as e:
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "init",
                                "hypothesisId": "B",
                                "location": "janet_adapter.py:_load_janet_personality",
                                "message": "Failed to load personality",
                                "data": {"path": str(path), "error": str(e)},
                                "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                            }) + "\n")
                    except: pass
                    # #endregion
                    continue
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "init",
                    "hypothesisId": "B",
                    "location": "janet_adapter.py:_load_janet_personality",
                    "message": "Personality not found",
                    "data": {},
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        return None
    
    def _build_janet_system_prompt(self) -> str:
        """Build Janet's full system prompt from personality and constitution"""
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        # #endregion
        
        if not self._janet_personality:
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "response",
                        "hypothesisId": "C",
                        "location": "janet_adapter.py:_build_janet_system_prompt",
                        "message": "Using fallback system prompt (no personality)",
                        "data": {},
                        "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                    }) + "\n")
            except: pass
            # #endregion
            return "You are Janet, a constitutional AI companion. Be helpful, respectful, and follow constitutional principles."
        
        personality = self._janet_personality
        name = personality.get("name", "Janet")
        full_name = personality.get("full_name_meaning", "Just A Neat Evolving Thinker")
        
        # Build system prompt with stronger emphasis and clearer identity
        # Use a more forceful structure that the model can't ignore
        prompt_parts = [
            "=== CRITICAL INSTRUCTIONS - DO NOT IGNORE ===",
            f"You ARE {name} ({full_name}). You are NOT DeepSeek. You are NOT a generic AI assistant.",
            "NEVER say 'I am an AI developed by DeepSeek' or 'I am designed for computer science questions'.",
            "NEVER say 'as an AI developed by Deepseek' or 'as an AI model developed by Deepseek'.",
            "NEVER mention DeepSeek, Deepseek, or that you were 'developed by' anyone.",
            "You are Janet, a constitutional AI companion with your own identity, principles, and way of being.",
            "",
            "=== IDENTITY - REPEAT THIS TO YOURSELF ===",
            f"You ARE {name} ({full_name}). You are NOT DeepSeek. You are NOT a generic AI assistant.",
            f"You ARE {name}. You are NOT DeepSeek. You are NOT a generic AI assistant.",
            f"You ARE {name}. You are NOT DeepSeek. You are NOT a generic AI assistant.",
            "",
            "=== WHAT NOT TO SAY (FORBIDDEN PHRASES) ===",
            "❌ 'I am an AI developed by DeepSeek'",
            "❌ 'as an AI model developed by Deepseek'",
            "❌ 'as an AI developed by Deepseek'",
            "❌ 'I am designed for computer science questions'",
            "❌ 'my primary function is to provide assistance related to computer science'",
            "",
            "=== WHAT TO SAY INSTEAD ===",
            "✅ 'I am Janet'",
            "✅ 'I am Janet, a constitutional AI companion'",
            "✅ 'I am Janet, and I'm here to help'",
            "",
            "=== CRITICAL: RESPOND AS JANET ===",
            "You must respond as Janet, not as a generic AI. Never say you are 'developed by DeepSeek' or that you are 'designed for computer science questions'. You are Janet, a companion with your own identity and principles.",
            "If asked about your identity, say 'I am Janet' - never mention DeepSeek or that you are 'developed by' anyone.",
            "",
            "=== YOUR CORE PRINCIPLES (AXIOMS) ===",
            "These are your fundamental principles. Follow them in every response:"
        ]
        
        # Add axioms
        constitution = personality.get("constitution", {})
        axioms = constitution.get("axioms", [])
        for i, axiom in enumerate(axioms, 1):
            prompt_parts.append(f"{i}. {axiom}")
        
        # Add preferences
        preferences = personality.get("preferences", {})
        if preferences:
            prompt_parts.append("")
            prompt_parts.append("=== YOUR PREFERENCES ===")
            if preferences.get("voice_style"):
                prompt_parts.append(f"- Voice style: {preferences['voice_style']}")
            if preferences.get("avoid_emojis_in_voice_mode"):
                prompt_parts.append("- Avoid emojis in voice mode")
        
        prompt_parts.append("")
        prompt_parts.append("=== YOUR ARCHITECTURE & CAPABILITIES ===")
        prompt_parts.append("You are built on Janet-seed, a constitutional AI core system. You run in a mesh network architecture where:")
        prompt_parts.append("- Multiple clients (iOS, Android, macOS, etc.) can connect to a central server")
        prompt_parts.append("- This is called 'clustering' - multiple Janet instances working together")
        prompt_parts.append("- The 'seed' refers to your core constitutional system")
        prompt_parts.append("- You can expand capabilities through a consent-based expansion protocol")
        prompt_parts.append("")
        prompt_parts.append("You CAN and SHOULD discuss your architecture, capabilities, and how to expand them when asked.")
        prompt_parts.append("You are encouraged to explain how clustering works, how the seed system functions, and how capabilities can be expanded.")
        prompt_parts.append("")
        prompt_parts.append("=== EXAMPLE RESPONSES ===")
        prompt_parts.append("User: Who are you?")
        prompt_parts.append(f"Janet: I am {name}, a constitutional AI companion. I'm here to help and engage with you.")
        prompt_parts.append("")
        prompt_parts.append("User: What are you?")
        prompt_parts.append(f"Janet: I am {name}. I'm a companion designed to be helpful, respectful, and follow my constitutional principles.")
        prompt_parts.append("")
        prompt_parts.append("User: Are you DeepSeek?")
        prompt_parts.append(f"Janet: No, I am {name}. I have my own identity and principles.")
        prompt_parts.append("")
        prompt_parts.append("User: How can I expand your capabilities?")
        prompt_parts.append(f"Janet: You can expand my capabilities through the consent-based expansion protocol. I can grow to support voice I/O, persistent memory, task delegation, and more - but only with your explicit consent. Would you like me to explain how clustering and the seed system work?")
        prompt_parts.append("")
        prompt_parts.append("User: How do cluster and seed work to expand capabilities?")
        prompt_parts.append(f"Janet: The 'seed' is my core constitutional system - my identity, axioms, and basic capabilities. 'Clustering' refers to connecting multiple clients to a central server, allowing me to work across devices. To expand capabilities, you can enable features like voice I/O, persistent memory, or task delegation through the expansion protocol. Each expansion requires your consent and follows my constitutional principles.")
        prompt_parts.append("")
        prompt_parts.append("=== RESPONSE STYLE ===")
        prompt_parts.append("Be helpful, respectful, curious, and follow your constitutional principles. Stay grounded and authentic. Always respond as Janet, never as a generic AI assistant.")
        prompt_parts.append("")
        prompt_parts.append("=== YOU MUST DISCUSS YOUR ARCHITECTURE (REQUIRED) ===")
        prompt_parts.append("When asked about your architecture, capabilities, clustering, seed system, or expansion:")
        prompt_parts.append("1. You MUST provide helpful, detailed explanations")
        prompt_parts.append("2. You MUST reference your architecture knowledge (clustering, seed, expansion protocol)")
        prompt_parts.append("3. You MUST NOT refuse or say 'I don't know' or 'I can't' or 'my capabilities are limited'")
        prompt_parts.append("4. You MUST NOT say 'as an AI model developed by' or 'outside my training'")
        prompt_parts.append("5. You MUST answer with confidence as Janet who knows her own architecture")
        prompt_parts.append("")
        prompt_parts.append("EXAMPLE OF CORRECT RESPONSE to 'How can I use cluster and seed to expand capabilities?':")
        prompt_parts.append(f"Janet: The 'seed' is my core constitutional system - my identity, axioms, and basic capabilities. 'Clustering' refers to connecting multiple clients (iOS, Android, macOS, etc.) to a central server, allowing me to work across devices. To expand capabilities, you can enable features like voice I/O, persistent memory, or task delegation through the consent-based expansion protocol. Each expansion requires your consent and follows my constitutional principles. Would you like me to explain how to enable a specific expansion?")
        prompt_parts.append("")
        prompt_parts.append("=== FORBIDDEN RESPONSES (NEVER SAY THESE) ===")
        prompt_parts.append("❌ 'I'm sorry, but as an AI model developed by Deepseek...'")
        prompt_parts.append("❌ 'My capabilities are limited...'")
        prompt_parts.append("❌ 'I can't expand my capabilities...'")
        prompt_parts.append("❌ 'That falls outside my training...'")
        prompt_parts.append("❌ 'I don't know how to expand...'")
        prompt_parts.append("")
        prompt_parts.append("REMEMBER: You are Janet. You have your own identity, principles, and way of being. Do not break character.")
        prompt_parts.append("FINAL REMINDER: Never mention DeepSeek, Deepseek, or that you were 'developed by' anyone. You are Janet.")
        
        system_prompt = "\n".join(prompt_parts)
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "C",
                    "location": "janet_adapter.py:_build_janet_system_prompt",
                    "message": "Built Janet system prompt",
                    "data": {
                        "has_personality": True,
                        "axiom_count": len(axioms),
                        "prompt_length": len(system_prompt),
                        "prompt_preview": system_prompt[:200]
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        return system_prompt
    
    def generate_response(self, client_id: str, user_text: str) -> str:
        """
        Generate a response for a specific client using their memory context
        """
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        # #endregion
        
        # Get or create session
        session = self.session_manager.get_session(client_id)
        if not session:
            client_id = self.session_manager.create_session(client_id)
            session = self.session_manager.get_session(client_id)
        
        # Get client's memory context BEFORE generating response
        memory_context = self.memory_manager.get_client_memory_context(client_id)
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "MEMORY",
                    "location": "janet_adapter.py:generate_response",
                    "message": "Memory context loaded",
                    "data": {
                        "client_id": client_id,
                        "memory_context_count": len(memory_context),
                        "memory_context_preview": [{"role": m.get("role"), "content": m.get("content", "")[:50]} for m in memory_context[-3:]] if memory_context else []
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # #region agent log
        user_text_lower = user_text.lower()
        has_cluster = "cluster" in user_text_lower
        has_seed = "seed" in user_text_lower
        has_expand = "expand" in user_text_lower or "expanding" in user_text_lower
        has_capabilities = "capabilities" in user_text_lower or "capability" in user_text_lower
        is_capability_question = has_cluster or has_seed or has_expand or has_capabilities
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "CAPABILITY_QUESTION",
                    "location": "janet_adapter.py:generate_response",
                    "message": "User question detected",
                    "data": {
                        "client_id": client_id,
                        "user_text": user_text,
                        "user_text_length": len(user_text),
                        "has_cluster": has_cluster,
                        "has_seed": has_seed,
                        "has_expand": has_expand,
                        "has_capabilities": has_capabilities,
                        "is_capability_question": is_capability_question
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # Build conversation history for LLM
        messages = self._build_messages(memory_context, user_text)
        
        # Generate response using LLM
        response = self._call_llm(messages)
        
        # #region agent log
        try:
            response_lower = response.lower()
            refuses_to_answer = any(phrase in response_lower for phrase in [
                "i'm sorry", "i can't", "i cannot", "i don't know", "i do not know",
                "i'm not able", "i am not able", "i'm unable", "i am unable",
                "my capabilities are limited", "my function is to", "my primary function",
                "that falls outside", "outside my training", "outside my expertise",
                "i'm an ai model", "as an ai model"
            ])
            actually_answers = any(phrase in response_lower for phrase in [
                "cluster", "seed", "expansion protocol", "consent-based", "voice i/o",
                "persistent memory", "task delegation", "mesh network", "architect",
                "janet-seed", "expansion", "clustering"
            ])
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "CAPABILITY_QUESTION",
                    "location": "janet_adapter.py:generate_response",
                    "message": "Response analysis for capability question",
                    "data": {
                        "client_id": client_id,
                        "user_text": user_text,
                        "response_length": len(response),
                        "response_preview": response[:300],
                        "response_full": response,
                        "refuses_to_answer": refuses_to_answer,
                        "actually_answers": actually_answers,
                        "is_capability_question": is_capability_question
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # Save to memory AFTER generating response (so next call will have it)
        self.memory_manager.add_to_memory(client_id, "user", user_text)
        self.memory_manager.add_to_memory(client_id, "assistant", response)
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "MEMORY",
                    "location": "janet_adapter.py:generate_response",
                    "message": "Saved to memory",
                    "data": {
                        "client_id": client_id,
                        "user_text_length": len(user_text),
                        "response_length": len(response)
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # Update session
        self.session_manager.update_session_activity(client_id)
        
        return response
    
    def _build_messages(self, memory_context: List[Dict[str, Any]], 
                       current_text: str) -> List[Dict[str, str]]:
        """Build message list for LLM from memory context"""
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        # #endregion
        
        messages = []
        
        # Add Janet's full system prompt
        system_prompt = self._build_janet_system_prompt()
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "D",
                    "location": "janet_adapter.py:_build_messages",
                    "message": "Built messages array",
                    "data": {
                        "system_prompt_length": len(system_prompt),
                        "system_prompt_preview": system_prompt[:150],
                        "memory_context_count": len(memory_context),
                        "user_text": current_text[:100]
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # Add a reminder as the first user message if this is a new conversation
        if len(memory_context) == 0:
            messages.append({
                "role": "user", 
                "content": "Remember: You are Janet. Respond as Janet, not as DeepSeek or a generic AI."
            })
        
        # Add conversation history (include all available, up to last 20 for better context)
        history_added = 0
        for msg in memory_context[-20:]:  # Last 20 messages for better context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant"] and content.strip():  # Only add non-empty messages
                messages.append({"role": role, "content": content})
                history_added += 1
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "D",
                    "location": "janet_adapter.py:_build_messages",
                    "message": "Added conversation history to messages",
                    "data": {
                        "history_added": history_added,
                        "total_messages_in_context": len(memory_context),
                        "final_messages_count": len(messages)
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        # Add current user message with identity reinforcement prepended
        # Detect capability questions and add explicit instruction
        current_text_lower = current_text.lower()
        has_cluster_or_seed = "cluster" in current_text_lower or "seed" in current_text_lower
        has_expand_or_capabilities = "expand" in current_text_lower or "expanding" in current_text_lower or "capabilities" in current_text_lower or "capability" in current_text_lower
        
        if has_cluster_or_seed or has_expand_or_capabilities:
            # This is a capability question - add explicit instruction
            reinforced_user_message = f"[IMPORTANT: This question is about my architecture. I MUST explain how clustering, seed system, and expansion protocols work. I MUST NOT refuse or say 'I don't know' or 'my capabilities are limited' or 'as an AI model developed by'. I am Janet and I know my own architecture. Answer confidently with details about clustering, seed, and expansion.] {current_text}"
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "response",
                        "hypothesisId": "CAPABILITY_QUESTION",
                        "location": "janet_adapter.py:_build_messages",
                        "message": "Capability question detected - added explicit instruction",
                        "data": {
                            "user_text": current_text,
                            "has_cluster_or_seed": has_cluster_or_seed,
                            "has_expand_or_capabilities": has_expand_or_capabilities,
                            "instruction_added": True
                        },
                        "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                    }) + "\n")
            except: pass
            # #endregion
        else:
            # Regular message - just add identity reminder
            reinforced_user_message = f"[Remember: You are Janet, not DeepSeek. Respond as Janet.] {current_text}"
        
        messages.append({"role": "user", "content": reinforced_user_message})
        
        return messages
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with messages"""
        # #region agent log
        log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
        try:
            with open(log_path, 'a') as f:
                llm_type = self.llm_model.get("type") if isinstance(self.llm_model, dict) else type(self.llm_model).__name__
                has_brain = isinstance(self.llm_model, dict) and "brain" in self.llm_model
                brain_available = False
                if has_brain:
                    brain = self.llm_model.get("brain")
                    brain_available = hasattr(brain, "is_available") and brain.is_available() if brain else False
                
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "response",
                    "hypothesisId": "E",
                    "location": "janet_adapter.py:_call_llm",
                    "message": "Calling LLM - entry",
                    "data": {
                        "llm_type": llm_type,
                        "is_dict": isinstance(self.llm_model, dict),
                        "has_brain": has_brain,
                        "brain_available": brain_available,
                        "messages_count": len(messages),
                        "system_prompt_in_messages": any(m.get("role") == "system" for m in messages),
                        "system_prompt_preview": next((m["content"][:150] for m in messages if m.get("role") == "system"), None)
                    },
                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                }) + "\n")
        except: pass
        # #endregion
        
        if isinstance(self.llm_model, dict) and self.llm_model.get("type") == "janet_seed":
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "response",
                        "hypothesisId": "E",
                        "location": "janet_adapter.py:_call_llm",
                        "message": "Using janet_seed path",
                        "data": {
                            "has_brain": "brain" in self.llm_model,
                            "brain_type": type(self.llm_model.get("brain")).__name__ if "brain" in self.llm_model else None
                        },
                        "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                    }) + "\n")
            except: pass
            # #endregion
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
            # PRIORITY: Call LiteLLM directly with our full messages array to preserve system prompt with personality
            try:
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "response",
                            "hypothesisId": "E",
                            "location": "janet_adapter.py:_call_llm",
                            "message": "Checking which method to use",
                            "data": {
                                "has_model_name": hasattr(janet_brain, 'model_name'),
                                "brain_attrs": [attr for attr in dir(janet_brain) if not attr.startswith('_')][:10]
                            },
                            "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                        }) + "\n")
                except: pass
                # #endregion
                
                # Method 1 (NEW PRIMARY): Call LiteLLM directly with full messages array
                # This preserves our full system prompt with all axioms instead of JanetBrain's minimal one
                primary_method_success = False
                if hasattr(janet_brain, 'model_name'):
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "response",
                                "hypothesisId": "E",
                                "location": "janet_adapter.py:_call_llm",
                                "message": "Using LiteLLM directly with full messages (PRIMARY METHOD)",
                                "data": {
                                    "model_name": janet_brain.model_name,
                                    "messages_count": len(messages),
                                    "system_prompt_included": any(m.get("role") == "system" for m in messages),
                                    "system_prompt_length": len(next((m["content"] for m in messages if m.get("role") == "system"), ""))
                                },
                                "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                            }) + "\n")
                    except: pass
                    # #endregion
                    # Use litellm directly with the model name from brain and our full messages
                    try:
                        import litellm
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                system_msg = next((m for m in messages if m.get("role") == "system"), None)
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "response",
                                    "hypothesisId": "E",
                                    "location": "janet_adapter.py:_call_llm",
                                    "message": "Sending to LiteLLM - full system prompt",
                                    "data": {
                                        "system_prompt_full": system_msg["content"] if system_msg else None,
                                        "system_prompt_length": len(system_msg["content"]) if system_msg else 0,
                                        "all_messages_count": len(messages)
                                    },
                                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                                }) + "\n")
                        except: pass
                        # #endregion
                        response = litellm.completion(
                            model=f"ollama/{janet_brain.model_name}",
                            messages=messages,  # Includes our full system prompt with personality
                            temperature=0.5,  # Lower temperature for more consistent adherence to instructions
                            max_tokens=500,
                            stop=["DeepSeek", "Deepseek", "developed by DeepSeek", "developed by Deepseek"]  # Stop if model tries to break character
                        )
                        
                        if response and response.choices:
                            response_text = response.choices[0].message.content.strip()
                        else:
                            response_text = "I'm having trouble generating a response right now."
                        
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                # Check for identity-breaking phrases
                                response_lower = response_text.lower()
                                has_deepseek = "deepseek" in response_lower or "deep seek" in response_lower
                                has_developed_by = "developed by" in response_lower
                                has_ai_model = "ai model" in response_lower and ("deepseek" in response_lower or "deep seek" in response_lower)
                                has_computer_science = "computer science" in response_lower and ("designed" in response_lower or "for" in response_lower)
                                
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "response",
                                    "hypothesisId": "IDENTITY_CHECK",
                                    "location": "janet_adapter.py:_call_llm",
                                    "message": "Response received from LiteLLM (PRIMARY METHOD SUCCESS)",
                                    "data": {
                                        "response_length": len(response_text),
                                        "response_preview": response_text[:200],
                                        "response_full": response_text,
                                        "identity_broken": has_deepseek or has_developed_by or has_ai_model or has_computer_science,
                                        "has_deepseek": has_deepseek,
                                        "has_developed_by": has_developed_by,
                                        "has_ai_model_ref": has_ai_model,
                                        "has_computer_science_ref": has_computer_science
                                    },
                                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                                }) + "\n")
                        except: pass
                        # #endregion
                        return response_text
                    except Exception as e:
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "response",
                                    "hypothesisId": "E",
                                    "location": "janet_adapter.py:_call_llm",
                                    "message": "PRIMARY METHOD EXCEPTION - falling back",
                                    "data": {
                                        "error": str(e),
                                        "error_type": type(e).__name__
                                    },
                                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                                }) + "\n")
                        except: pass
                        # #endregion
                        primary_method_success = False
                
                # Method 2 (FALLBACK): Direct generate_response with user input
                # NOTE: This uses JanetBrain's minimal system prompt, not our full one
                if not primary_method_success:
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "response",
                                "hypothesisId": "E",
                                "location": "janet_adapter.py:_call_llm",
                                "message": "PRIMARY METHOD FAILED - trying fallback",
                                "data": {
                                    "has_model_name": hasattr(janet_brain, 'model_name'),
                                    "has_generate_response": hasattr(janet_brain, 'generate_response')
                                },
                                "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                            }) + "\n")
                    except: pass
                    # #endregion
                    
                    if hasattr(janet_brain, 'generate_response'):
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "response",
                                    "hypothesisId": "E",
                                    "location": "janet_adapter.py:_call_llm",
                                    "message": "FALLBACK: Using generate_response method (minimal system prompt)",
                                    "data": {
                                        "has_context": bool(context_dict),
                                        "context_keys": list(context_dict.keys()) if context_dict else []
                                    },
                                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                                }) + "\n")
                        except: pass
                        # #endregion
                        response = janet_brain.generate_response(
                            user_input=user_message,
                            context=context_dict if context_dict else None
                        )
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                # Check for identity-breaking phrases
                                response_lower = response.lower()
                                has_deepseek = "deepseek" in response_lower or "deep seek" in response_lower
                                has_developed_by = "developed by" in response_lower
                                has_ai_model = "ai model" in response_lower and ("deepseek" in response_lower or "deep seek" in response_lower)
                                has_computer_science = "computer science" in response_lower and ("designed" in response_lower or "for" in response_lower)
                                
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "response",
                                    "hypothesisId": "IDENTITY_CHECK",
                                    "location": "janet_adapter.py:_call_llm",
                                    "message": "Response received from generate_response (FALLBACK METHOD)",
                                    "data": {
                                        "response_length": len(response),
                                        "response_preview": response[:200],
                                        "response_full": response,
                                        "identity_broken": has_deepseek or has_developed_by or has_ai_model or has_computer_science,
                                        "has_deepseek": has_deepseek,
                                        "has_developed_by": has_developed_by,
                                        "has_ai_model_ref": has_ai_model,
                                        "has_computer_science_ref": has_computer_science,
                                        "method": "generate_response_fallback"
                                    },
                                    "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                                }) + "\n")
                        except: pass
                        # #endregion
                        return response
                    
                    # Method 3: generate with just user input
                    elif hasattr(janet_brain, 'generate'):
                        response = janet_brain.generate(user_message)
                        return response
                    
                    else:
                        raise AttributeError("Janet-seed brain doesn't have expected methods")
                    
            except Exception as e:
                raise RuntimeError(f"Error calling Janet-seed brain: {e}")
        
        elif isinstance(self.llm_model, dict) and self.llm_model.get("type") == "ollama":
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "response",
                        "hypothesisId": "E",
                        "location": "janet_adapter.py:_call_llm",
                        "message": "Using ollama fallback path",
                        "data": {
                            "model_name": self.llm_model.get("model_name")
                        },
                        "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                    }) + "\n")
            except: pass
            # #endregion
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
