"""
Validation-only agent with an intent classification tool.

This creates a separate agent configuration that includes a tool for classifying
user intent. The agent can call this tool when it's unclear about question type.
This is entirely self-contained in validation code - no app changes needed.
"""
import time
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.agents import AgentFinish
from langchain_openai import ChatOpenAI

from validation.services.rag_service import get_validation_rag_service
from validation.services.user_data_tool import UserHiveDataTool
from validation.services.config import OPENROUTER_API_KEY, RAG_CONFIG


class IntentClassificationTool(BaseTool):
    """
    Tool that classifies user intent to help the agent decide which tools to use.
    
    The agent can call this tool when it's uncertain about whether a question
    requires personal data, documents, or both.
    """
    name: str = "classify_user_intent"
    description: str = """Classify the user's intent to determine what type of data is needed.
    
    USE THIS TOOL when you're uncertain about what the user is asking for:
    - Is this about their personal hives/data?
    - Is this a general beekeeping question?
    - Does this require both personal data AND general knowledge?
    
    This tool will analyze the question and return:
    - PRIMARY_DATA_NEED: "personal_only", "documents_only", or "both_combined"
    - Explanation of why this classification was made
    
    After getting the classification, use the appropriate tools:
    - If "personal_only": use get_user_hive_data
    - If "documents_only": use search_beekeeping_documents  
    - If "both_combined": use both tools
    
    Parameters:
    - question: The user's question to classify
    """
    
    _real_service: Any
    
    def __init__(self, real_service):
        super().__init__()
        self._real_service = real_service
    
    def _run(
        self,
        question: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Classify the user's intent."""
        try:
            # Extract callbacks from run_manager to pass to classification (for token tracking)
            callbacks = None
            if run_manager:
                # Try multiple ways to get callbacks from run_manager
                if hasattr(run_manager, 'handlers') and run_manager.handlers:
                    callbacks = run_manager.handlers
                elif hasattr(run_manager, 'callbacks') and run_manager.callbacks:
                    callbacks = run_manager.callbacks
                elif hasattr(run_manager, 'get_child'):
                    # Use run_manager's child context which should have callbacks
                    child_manager = run_manager.get_child()
                    if hasattr(child_manager, 'handlers') and child_manager.handlers:
                        callbacks = child_manager.handlers
            
            intent = self._real_service.classify_user_intent(question, callbacks=callbacks)
            
            # Log if callbacks were passed (for debugging token tracking)
            if callbacks:
                logging.debug(f"IntentClassificationTool: Callbacks passed to classify_user_intent for token tracking")
            else:
                logging.warning(f"IntentClassificationTool: No callbacks available from run_manager - classification LLM calls may not be tracked")
            
            # Format as a readable string for the agent
            primary_need = intent.get("PRIMARY_DATA_NEED", "both_combined")
            specific_focus = intent.get("SPECIFIC_FOCUS", "general")
            tool_strategy = intent.get("TOOL_STRATEGY", "parallel_search")
            
            result = f"""Intent Classification Result:
- PRIMARY_DATA_NEED: {primary_need}
- SPECIFIC_FOCUS: {specific_focus}
- TOOL_STRATEGY: {tool_strategy}

Recommended action:
"""
            if primary_need == "personal_only":
                result += "Use get_user_hive_data tool to retrieve the user's personal hive information."
            elif primary_need == "documents_only":
                result += "Use search_beekeeping_documents tool to find authoritative beekeeping information."
            else:
                result += "Use both get_user_hive_data and search_beekeeping_documents tools to combine personal data with general knowledge."
            
            return result
        except Exception as e:
            return f"Error classifying intent: {str(e)}"
    
    async def _arun(
        self,
        question: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return self._run(question, run_manager)


class AgentWithIntentToolExecutor:
    """
    Strategy that uses an agent with an intent classification tool.
    
    The agent has access to:
    1. classify_user_intent - tool to classify intent when uncertain
    2. search_beekeeping_documents - document search tool
    3. get_user_hive_data - user data tool
    
    The agent decides when to call the classification tool based on question clarity.
    """
    
    def __init__(self):
        self._real_service = get_validation_rag_service()
        
        # Initialize LLM (same as real service)
        self.llm = ChatOpenAI(
            model=RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b'),
            temperature=0.3,
            max_tokens=5000,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1"
        )
        
        # Create intent classification tool
        self.intent_tool = IntentClassificationTool(self._real_service)
        
        # Initialize agent components to get document search tool
        # This creates the document_search_tool we need
        if not hasattr(self._real_service, 'document_search_tool'):
            self._real_service._init_agent_components()
        self.document_search_tool = self._real_service.document_search_tool
    
    def execute_query(
        self,
        question: str,
        user_id: int,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a query using an agent with intent classification tool."""
        max_retries = 2
        overall_start = time.perf_counter()  # Track total time across all retries
        
        # Initialize variables that will be used after the loop
        result = None
        answer = ""
        token_usage_by_model = {}
        
        for attempt in range(max_retries + 1):
            start = time.perf_counter()
            
            # Initialize token usage tracker for this attempt
            attempt_token_usage = {}
            
            # Use LangChain's built-in UsageMetadataCallbackHandler for token tracking
            from langchain_core.callbacks import UsageMetadataCallbackHandler
            from langchain_core.runnables import RunnableConfig
            
            usage_callback = UsageMetadataCallbackHandler()
            
            # Create user data tool
            user_data_tool = UserHiveDataTool(user_id)
            
            # Combine all tools: intent classification + document search + user data
            tools = [
                self.intent_tool,
                self.document_search_tool,
                user_data_tool,
            ]
            
            # Create agent prompt that encourages using classification tool for ambiguous cases
            agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a smart beekeeping assistant. You have access to three tools:

1. classify_user_intent - Use this tool to determine what type of data is needed to answer the question.
   USE THIS TOOL when:
   - The question could be answered with either personal data OR general knowledge (e.g., "what should I do about varroa", "how can I prevent beetles")
   - The question is ambiguous about whether it needs personal context (e.g., "when should I treat", "what's the best approach")
   - You're unsure whether the user wants advice based on their specific situation or general best practices
   - The question mentions both personal context ("my", "I") AND asks for general information
   
   You can SKIP this tool ONLY if:
   - The question is clearly ONLY about personal data (e.g., "which of my hives", "my last inspection date")
   - The question is clearly ONLY general knowledge (e.g., "what is a queen excluder", "define varroa mite")
   
2. search_beekeeping_documents - Search authoritative beekeeping documents for factual information.
   Use this for general beekeeping questions, best practices, measurements, or recommendations.
   
3. get_user_hive_data - Get the user's personal hive inspection data.
   Use this when the user asks about "my hives", "which of my", or personal data.

WORKFLOW:
1. FIRST, assess the question:
   - If clearly ONLY personal (e.g., "which of my hives", "my last inspection"), go directly to get_user_hive_data
   - If clearly ONLY general (e.g., "what is a queen excluder", "define varroa"), go directly to search_beekeeping_documents
   - If the question could benefit from EITHER personal data OR general knowledge, OR if you're uncertain, THEN call classify_user_intent FIRST
2. Based on the classification result (or your assessment), use the appropriate tool(s):
   - If personal only: use get_user_hive_data ONCE
   - If general only: use search_beekeeping_documents ONCE
   - If both needed: use BOTH tools (each ONCE)
3. AFTER calling the necessary tool(s), IMMEDIATELY provide your final answer. Do NOT call any more tools.

CRITICAL RULES:
- When in doubt, use classify_user_intent - it helps ensure you use the right tools
- Call each tool AT MOST ONCE per query
- NEVER call the same tool twice
- After calling a tool and getting its result, you MUST provide your answer immediately
- Do NOT call tools again after you have the information you need
- Your final response should be a complete answer to the user's question
- Do NOT ask for more information or call additional tools after you have retrieved data
- Format your response naturally without mentioning tool names or execution details
- Be specific and cite sources when making factual claims

TOOL CALLING FORMAT:
- When calling tools, provide parameters in JSON format
- For get_user_hive_data: provide {{"days_back": <number>, "include_all_hives": <true/false>}} - parameters have defaults if omitted
- For search_beekeeping_documents: provide {{"query": "<search query>"}}
- For classify_user_intent: provide {{"question": "<the question>"}}
- Try to format JSON correctly, but the system will use defaults for missing or invalid fields"""),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
            # Create LLM instance
            model_name = RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
            llm_for_agent = ChatOpenAI(
                model=model_name,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                openai_api_key=self.llm.openai_api_key,
                openai_api_base=self.llm.openai_api_base,
                streaming=False
            )
            
            # Create agent
            agent = create_openai_tools_agent(
                llm=llm_for_agent,
                tools=tools,
                prompt=agent_prompt
            )
            
            # Create agent executor with reasonable max iterations
            # Match production: max_iterations=10
            # handle_parsing_errors=True provides a default error message to the LLM when JSON parsing fails
            # This helps the LLM retry with better formatting
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                handle_parsing_errors=True,  # Provides default error message for parsing failures
                return_intermediate_steps=True,  # We want to track if classification tool was used
                max_iterations=10  # Match production - increased to allow complex multi-step queries while preventing infinite loops
            )
            
            # Execute the agent with callback to track token usage
            # We'll monitor intermediate steps to detect loops
            try:
                # Use invoke with a custom callback to monitor for loops
                from langchain_core.callbacks import BaseCallbackHandler
                
                class LoopDetectionCallback(BaseCallbackHandler):
                    def __init__(self):
                        self.tool_calls = []
                        self.step_count = 0
                    
                    def on_agent_action(self, action, **kwargs):
                        self.step_count += 1
                        if hasattr(action, 'tool') and action.tool:
                            tool_name = action.tool
                            # Only add if it's a valid string tool name, not an exception or error
                            if isinstance(tool_name, str) and not tool_name.startswith('_'):
                                self.tool_calls.append(tool_name)
                
                loop_callback = LoopDetectionCallback()
                
                result = agent_executor.invoke(
                    {"input": question},
                    config=RunnableConfig(callbacks=[usage_callback, loop_callback])
                )
                
                # Check if we detected a loop (same tool called multiple times)
                if len(loop_callback.tool_calls) != len(set(loop_callback.tool_calls)):
                    logging.warning(f"Detected potential loop: tools called {loop_callback.tool_calls}")
            except Exception as e:
                # If agent execution fails, check if we should retry
                logging.error(f"Agent execution failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    continue  # Retry on exception
                else:
                    # Last attempt failed, return error
                    latency_ms = (time.perf_counter() - overall_start) * 1000
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {
                            "classification_tool_used": False,
                            "predicted_intent": None,
                            "agent_strategy": "intent_tool_agent",
                            "error": str(e),
                            "token_usage_by_model": token_usage_by_model,
                        },
                        "latency_ms": latency_ms,
                    }
            
            # Extract token usage from the callback's usage_metadata
            if hasattr(usage_callback, 'usage_metadata') and usage_callback.usage_metadata:
                for model_name, usage in usage_callback.usage_metadata.items():
                    # Normalize model name
                    normalized_name = model_name
                    if 'gpt-oss' in model_name.lower():
                        normalized_name = RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
                    elif 'gpt-4o' in model_name.lower() and 'gpt-4o-mini' not in model_name.lower():
                        normalized_name = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
                    
                    if normalized_name not in attempt_token_usage:
                        attempt_token_usage[normalized_name] = {"input": 0, "output": 0}
                    
                    attempt_token_usage[normalized_name]["input"] += usage.get('input_tokens', 0)
                    attempt_token_usage[normalized_name]["output"] += usage.get('output_tokens', 0)
            
            # Merge token usage into overall tracker
            for model_name, usage in attempt_token_usage.items():
                if model_name not in token_usage_by_model:
                    token_usage_by_model[model_name] = {"input": 0, "output": 0}
                token_usage_by_model[model_name]["input"] += usage["input"]
                token_usage_by_model[model_name]["output"] += usage["output"]
            
            # Get the final answer directly from result.get("output")
            # This IS the final answer - no extraction or filtering needed
            answer = result.get("output", "")
            
            # If agent hit max_iterations, check intermediate_steps for AgentFinish
            if answer == "Agent stopped due to max iterations." or not answer:
                intermediate_steps = result.get("intermediate_steps", [])
                if intermediate_steps:
                    # Look for AgentFinish in intermediate_steps (contains the final answer)
                    for step in reversed(intermediate_steps):  # Check from end backwards
                        if isinstance(step, tuple) and len(step) >= 2:
                            action = step[0]
                            # Check if this is an AgentFinish (final answer)
                            if isinstance(action, AgentFinish):
                                answer = action.return_values.get("output", "")
                                if answer:
                                    break
            
            # Check if we got a valid answer - if so, break out of retry loop
            if answer and answer.strip() and answer != "Agent stopped due to max iterations.":
                break
            
            # If this wasn't the last attempt, continue to retry
            if attempt < max_retries:
                logging.warning(f"Attempt {attempt + 1} failed (answer empty or max_iterations), retrying...")
                continue
            
            # Last attempt failed, use default message
            if not answer or not answer.strip():
                answer = "I couldn't process your question. Please try rephrasing it."
        
        # Calculate total latency across all retries
        latency_ms = (time.perf_counter() - overall_start) * 1000
        
        # Track if classification tool was used (result should be available from last attempt)
        intermediate_steps = result.get("intermediate_steps", []) if result else []
        classification_used = False
        predicted_intent = None
        
        for step in intermediate_steps:
            action = step[0]
            if hasattr(action, 'tool') and action.tool == "classify_user_intent":
                classification_used = True
                # Try to extract the classification result
                observation = step[1]
                if isinstance(observation, str) and "PRIMARY_DATA_NEED:" in observation:
                    # Parse the intent from the observation
                    for line in observation.split("\n"):
                        if "PRIMARY_DATA_NEED:" in line:
                            predicted_intent = line.split(":")[-1].strip()
                            break
        
        # Process sources (similar to real service)
        sources = []
        if hasattr(self._real_service, '_last_source_documents') and self._real_service._last_source_documents:
            for doc in self._real_service._last_source_documents:
                sources.append({
                    "title": doc.metadata.get("document_title", "Unknown"),
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "page_number": doc.metadata.get("page_number"),
                    "similarity": doc.metadata.get("similarity", 0.0),
                    "chunk_text": doc.page_content if hasattr(doc, 'page_content') and doc.page_content else None,
                })
        
        # Reset source documents for next query
        if hasattr(self._real_service, '_last_source_documents'):
            self._real_service._last_source_documents = []
        
        # Calculate total latency across all retries
        latency_ms = (time.perf_counter() - overall_start) * 1000
        
        # Format result
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "metadata": {
                "classification_tool_used": classification_used,
                "predicted_intent": predicted_intent,
                "agent_strategy": "intent_tool_agent",
                "token_usage_by_model": token_usage_by_model,  # Store per-model usage
            },
            "latency_ms": latency_ms,
        }

