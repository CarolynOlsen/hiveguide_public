"""
Validation-only RAG service.

This is a copy/modification of backend/rag/langchain_service.py that can be
freely modified for testing different strategies without affecting the main app.

Key differences from the app version:
- Uses validation/services/config.py instead of backend/rag/config.py
- Can be modified for strategy testing
- All components are self-contained in validation/
"""
import time
import json
import re
import math
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks import (
    CallbackManagerForToolRun,
    AsyncCallbackManagerForToolRun,
)
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.callbacks import get_openai_callback
from langchain_core.tools import BaseTool
from langchain_core.agents import AgentFinish
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from validation.services.config import DATABASE_URL, OPENAI_API_KEY, OPENROUTER_API_KEY, RAG_CONFIG
from validation.services.models import DocumentChunk
from validation.services.user_data_tool import UserHiveDataTool

# Suppress verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
import warnings
warnings.filterwarnings("ignore", message=".*Importing verbose from langchain root module.*")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core.globals")


class PostgresVectorStore:
    """Custom vector store using existing PostgreSQL schema."""
    
    def __init__(self, connection_string: str, embedding_function):
        self.connection_string = connection_string
        self.embedding_function = embedding_function
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def similarity_search(self, query: str, k: int = 4, **kwargs) -> List[Document]:
        """Perform similarity search using the existing database structure."""
        query_embedding = self.embedding_function.embed_query(query)
        
        session = self.SessionLocal()
        try:
            chunks = session.query(DocumentChunk).filter(
                DocumentChunk.embedding_vector.isnot(None)
            ).all()
            
            def cosine_similarity(vec1, vec2):
                return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            
            chunks_with_similarity = [
                (chunk, cosine_similarity(chunk.embedding_vector, query_embedding))
                for chunk in chunks
            ]
            
            chunks_with_similarity.sort(key=lambda x: x[1], reverse=True)
            top_chunks = chunks_with_similarity[:k]
            
            documents = []
            for chunk, similarity in top_chunks:
                doc = Document(
                    page_content=chunk.chunk_text,
                    metadata={
                        'document_title': chunk.document_title,
                        'similarity': similarity,
                        'chunk_id': chunk.id,
                        'page_number': chunk.page_number,
                        'section_title': chunk.section_title,
                        'organization': chunk.organization,
                        'publication_year': chunk.publication_year,
                        'source_url': chunk.source_url
                    }
                )
                documents.append(doc)
            
            return documents
        finally:
            session.close()


class ValidationRAGService:
    """
    Validation-only RAG service that can be freely modified for strategy testing.
    
    This is a simplified version of LangChainRAGService with the essential
    components needed for validation. Modify this file to test different strategies.
    """
    
    def __init__(self):
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=RAG_CONFIG.get('embedding_model', 'text-embedding-3-small'),
            openai_api_key=OPENAI_API_KEY
        )
        
        # Initialize LLM
        # Note: OpenRouter usage accounting is enabled by default in API responses
        # Token usage should be available in response_metadata or usage_metadata
        self.llm = ChatOpenAI(
            model=RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b'),
            temperature=0.3,
            max_tokens=5000,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1"
        )
        
        # Initialize vector store
        self.vector_store = PostgresVectorStore(
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings
        )
        
        # Initialize retriever
        self.retriever = self._create_retriever()
        
        # Storage for source documents
        self._last_source_documents = []
        
        # Initialize agent components
        self._init_agent_components()
    
    def _create_retriever(self):
        """Create a retriever from the vector store."""
        class CustomRetriever(BaseRetriever):
            def __init__(self, vector_store, k=10):
                super().__init__()
                self._vector_store = vector_store
                self._k = k
            
            def _get_relevant_documents(self, query: str) -> List[Document]:
                return self._vector_store.similarity_search(query, k=self._k)
            
            async def _aget_relevant_documents(self, query: str) -> List[Document]:
                return self._get_relevant_documents(query)
        
        return CustomRetriever(self.vector_store, k=RAG_CONFIG.get('top_k_chunks', 10))
    
    def _run_retrieval(self, query: str, callbacks=None) -> Dict[str, Any]:
        """Execute retrieval and LLM response generation."""
        documents = self.retriever.invoke(query)
        context_text = self._format_documents(documents)
        
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a helpful beekeeping expert. Answer questions based on the provided context.

Context from beekeeping documents:
{context}

Question: {question}

Answer: """
        )
        
        # Use LLM with callbacks if provided, otherwise use default
        llm_to_use = self.llm
        if callbacks:
            # Create LLM instance with callbacks to ensure token tracking
            # Get model name from llm or fallback to config
            model_name = getattr(self.llm, 'model_name', None) or getattr(self.llm, 'model', None) or RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
            llm_to_use = ChatOpenAI(
                model=model_name,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                openai_api_key=self.llm.openai_api_key,
                openai_api_base=self.llm.openai_api_base,
                callbacks=callbacks
            )
        
        response_chain = (
            prompt_template
            | llm_to_use
            | StrOutputParser()
        )
        
        answer_text = response_chain.invoke({
            "context": context_text,
            "question": query
        })
        
        return {
            "result": answer_text,
            "source_documents": documents
        }
    
    def _format_documents(self, documents: List[Document]) -> str:
        """Format retrieved documents into a context string."""
        if not documents:
            return "No relevant documents found."
        
        formatted_sections = []
        for index, doc in enumerate(documents, start=1):
            metadata = doc.metadata or {}
            title = metadata.get('document_title') or f"Document {index}"
            page = metadata.get('page_number')
            header_parts = [f"[Source {index}] {title}"]
            if page is not None:
                header_parts.append(f"(Page {page})")
            header = " ".join(header_parts)
            formatted_sections.append(f"{header}\n{doc.page_content}")
        
        return "\n\n".join(formatted_sections)
    
    def _init_agent_components(self):
        """Initialize agent components."""
        # Create document search tool
        class DocumentSearchTool(BaseTool):
            name: str = "search_beekeeping_documents"
            description: str = """Search through beekeeping documents for factual information.
            
            USE THIS WHEN:
            - User asks for specific numbers, measurements, or weights
            - User wants best practices or recommendations
            - User asks "what are signs of" or "how to" questions
            - Making any factual claims about beekeeping practices
            
            DO NOT USE FOR:
            - Questions purely about the user's personal hive data (use user data tool instead)"""
            
            _retrieval_fn: Any
            _parent_service: Any
            
            def __init__(self, retrieval_fn, parent_service):
                super().__init__()
                self._retrieval_fn = retrieval_fn
                self._parent_service = parent_service
            
            def _run(
                self,
                query: str,
                run_manager: Optional[CallbackManagerForToolRun] = None,
                **kwargs  # Accept any additional keyword arguments LangChain might pass
            ) -> str:
                try:
                    # Extract callbacks from run_manager to pass to retrieval
                    # LangChain should propagate callbacks from AgentExecutor to tool run_manager
                    # We extract them to ensure they're passed to the LLM call in _run_retrieval
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
                    
                    result = self._retrieval_fn(query, callbacks=callbacks)
                    if "source_documents" in result:
                        source_docs = result["source_documents"]
                        self._parent_service._last_source_documents.extend(source_docs)
                        logging.debug(f"DocumentSearchTool: Added {len(source_docs)} source documents")
                    else:
                        logging.warning(f"DocumentSearchTool: No source_documents in result. Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
                    
                    # Log if callbacks were passed (for debugging token tracking)
                    if callbacks:
                        logging.debug(f"DocumentSearchTool: Callbacks passed to _run_retrieval for token tracking")
                    else:
                        logging.warning(f"DocumentSearchTool: No callbacks available from run_manager - tool LLM calls may not be tracked")
                    
                    return result.get("result", "No information found in documents.")
                except Exception as e:
                    logging.error(f"DocumentSearchTool error: {e}")
                    return f"Error searching documents: {str(e)}"
            
            async def _arun(
                self,
                query: str,
                run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
                **kwargs  # Accept any additional keyword arguments LangChain might pass
            ) -> str:
                return self._run(query, **kwargs)
        
        self.document_search_tool = DocumentSearchTool(self._run_retrieval, self)
        
        # Create agent prompt (can be modified for different strategies)
        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a smart beekeeping assistant. For every question, follow this exact process:

STEP 1 - ANALYZE THE QUESTION:
- What specific information is the user requesting?
- Do they want info about THEIR hives ("my hives", "which of my", "when did I last") or GENERAL beekeeping knowledge?
- Are they asking for measurements, comparisons, recommendations, or personal hive analysis?

STEP 2 - DETERMINE DATA STRATEGY:
- If asking about "my hives/my data": Use get_user_hive_data tool FIRST
- If asking for specific facts/measurements: Use search_beekeeping_documents FIRST
- If combining personal analysis with factual standards: Use BOTH tools

STEP 3 - BE PRECISE AND SPECIFIC:
- For personal questions: Give specific hive names, exact dates, and actual measurements
- For factual claims: Always cite the documented sources you found
- Don't give generic advice when specific data is available

STEP 4 - STOP WHEN YOU HAVE ENOUGH INFORMATION:
- Once you have the necessary data from tools, provide your answer immediately
- Do NOT make additional tool calls if you already have sufficient information

CRITICAL RULES:
1. NEVER include tool execution details or debug information in your response
2. Your response should read naturally and professionally
3. When making factual claims, you MUST search documents first
4. When users ask about "my hives", provide specific hive names and inspection details
5. STOP after you have enough information - don't make redundant tool calls

Formatting Requirements:
- NO tables or table formatting
- Use bullet points, numbered lists, or simple paragraphs
- Format for mobile readability with clear line breaks
- Be concise and scannable"""),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
    
    def _classify_with_langchain(self, question: str, callbacks=None) -> Dict[str, Any]:
        """Classify user intent using LLM."""
        classification_prompt = f"""
        Analyze this beekeeping question and classify the user's intent:
        
        Question: {question}
        
        Determine:
        1. PRIMARY_DATA_NEED: personal_only (asking about their own hives), documents_only (general knowledge), or both_combined (personal + general)
        2. SPECIFIC_FOCUS: weight, queen_status, disease, general_advice, inspection_patterns, feeding, seasonal_prep, equipment, etc.
        3. URGENCY: immediate_action_needed, routine_check, informational
        4. TOOL_STRATEGY: user_data_first, documents_first, or parallel_search
        
        Look for these indicators:
        - "my hives", "my bees", "which of my", "when did I last" = personal_only
        - "what should", "how to", "what are signs of", specific measurements = documents_first
        - "which of my hives need" + factual criteria = both_combined
        
        Respond in JSON format only.
        """
        
        # Use LLM with callbacks if provided (for token tracking)
        llm_to_use = self.llm
        if callbacks:
            model_name = getattr(self.llm, 'model_name', None) or getattr(self.llm, 'model', None) or RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
            llm_to_use = ChatOpenAI(
                model=model_name,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                openai_api_key=self.llm.openai_api_key,
                openai_api_base=self.llm.openai_api_base,
                callbacks=callbacks
            )
        
        result = llm_to_use.invoke(classification_prompt)
        
        try:
            intent = json.loads(result.content)
        except Exception:
            # Fallback to simple heuristics
            question_lower = question.lower()
            intent = {
                "PRIMARY_DATA_NEED": "personal_only"
                if any(phrase in question_lower for phrase in ["my hive", "my bee", "which of my", "when did i"])
                else "documents_first",
                "SPECIFIC_FOCUS": "weight" if "weight" in question_lower else "general_advice",
                "URGENCY": "routine_check",
                "TOOL_STRATEGY": "user_data_first" if "my" in question_lower else "documents_first",
            }
        
        return intent
    
    def _classify_label_with_logprobs(self, question: str):
        """Classify intent label using logprobs for confidence scores.
        
        Returns (label, confidence, class_probabilities, token_usage) or (None, None, None, {}) on failure.
        """
        classification_tokens = {"input": 0, "output": 0}
        if not OPENROUTER_API_KEY:
            return None, None, None, classification_tokens
        
        labels = ["personal_only", "documents_only", "both_combined"]
        label_set = ", ".join(labels)
        
        import openai
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        model = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
        
        classification_tokens = {"input": 0, "output": 0}
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the user's question into EXACTLY one of these labels: "
                            f"{label_set}. Respond with only the label."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                temperature=0,
                max_tokens=3,
                logprobs=True,
                top_logprobs=20,
            )
            
            # Extract token usage from response
            if hasattr(resp, 'usage') and resp.usage:
                classification_tokens["input"] = resp.usage.prompt_tokens or 0
                classification_tokens["output"] = resp.usage.completion_tokens or 0
        except Exception as e:
            logging.warning(f"logprob classification failed: {e}")
            return None, None, None, classification_tokens
        
        choice = resp.choices[0]
        content = (choice.message.content or "").strip()
        
        def _norm(tok: str) -> str:
            t = (tok or "").lower().strip()
            t = t.replace("▁", "")
            t = re.sub(r"[^a-z0-9_]", "", t)
            return t
        
        def _match_label(tok_norm: str) -> str | None:
            for lbl, norm_lbl in labels_normalized.items():
                if tok_norm == norm_lbl:
                    return lbl
            if tok_norm.startswith("personal"):
                return "personal_only"
            if tok_norm.startswith("document"):
                return "documents_only"
            if "both" in tok_norm or "combined" in tok_norm:
                return "both_combined"
            return None
        
        labels_normalized = {lbl: _norm(lbl) for lbl in labels}
        label_logprobs = {}
        
        try:
            lp = getattr(choice, "logprobs", None)
            if lp and getattr(lp, "content", None):
                for idx, token_entry in enumerate(lp.content):
                    for top in token_entry.top_logprobs:
                        token_text = _norm(top.token or "")
                        label_match = _match_label(token_text)
                        if label_match:
                            label_logprobs[label_match] = max(
                                label_logprobs.get(label_match, float("-inf")), 
                                top.logprob
                            )
            else:
                return None, None, None, classification_tokens
        except Exception as e:
            logging.warning(f"Failed to parse logprobs: {e}")
            return None, None, None, classification_tokens
        
        if not label_logprobs:
            return None, None, None, classification_tokens
        
        # Convert to probabilities via softmax
        max_lp = max(label_logprobs.values())
        exps = {k: math.exp(v - max_lp) for k, v in label_logprobs.items()}
        total = sum(exps.values()) or 1.0
        probs = {k: exps[k] / total for k in exps}
        class_probabilities = {lbl: probs.get(lbl, 0.0) for lbl in labels}
        confidence = max(class_probabilities.values())
        
        label = max(class_probabilities, key=class_probabilities.get)
        return label, confidence, class_probabilities, classification_tokens
    
    def classify_user_intent(self, question: str, callbacks=None) -> Dict[str, Any]:
        """Analyze user question with optional confidence scores.
        
        Args:
            question: The user's question to classify
            callbacks: Optional callbacks for token tracking (used when called from tools)
        """
        label = None
        confidence = None
        class_probabilities = None
        
        # Try logprob-based classification
        label, confidence, class_probabilities, classification_tokens = self._classify_label_with_logprobs(question)
        
        # Get full intent structure (pass callbacks for token tracking)
        intent = self._classify_with_langchain(question, callbacks=callbacks)
        
        # Override with logprob label if available
        if label:
            intent["PRIMARY_DATA_NEED"] = label
        
        # Attach confidence fields
        if confidence is not None:
            intent["confidence"] = confidence
        if class_probabilities is not None:
            intent["class_probabilities"] = class_probabilities
        
        # Store token usage from classification
        if classification_tokens and (classification_tokens.get("input", 0) > 0 or classification_tokens.get("output", 0) > 0):
            intent["token_usage"] = classification_tokens
        
        return intent
    
    def query_with_simple_llm(
        self,
        question: str,
        user_id: int,
        routing: str,  # "personal_only", "documents_only", "both_combined"
        intent: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simple LLM call without agents - just fetch data and call LLM directly.
        
        Args:
            question: User's question
            user_id: User ID
            routing: "personal_only", "documents_only", or "both_combined"
            intent: Optional intent dict for metadata
            session_id: Optional session ID
            
        Returns:
            Dict with answer, sources, metadata
        """
        try:
            start_time = time.perf_counter()
            self._last_source_documents = []
            token_usage_by_model = {}
            
            # Fetch user data if needed
            user_data_text = None
            user_data_available = False
            if routing in ["personal_only", "both_combined"]:
                try:
                    user_data_tool = UserHiveDataTool(user_id)
                    user_context = user_data_tool._run()
                    if "No hives found" not in user_context and "error" not in user_context.lower():
                        user_data_text = user_context
                        user_data_available = True
                except Exception as e:
                    logging.warning(f"Failed to fetch user data: {e}")
            
            # Fetch documents if needed
            document_context = None
            if routing in ["documents_only", "both_combined"]:
                try:
                    result = self._run_retrieval(question)
                    document_context = result.get("result", "")
                    if "source_documents" in result:
                        self._last_source_documents = result["source_documents"]
                except Exception as e:
                    logging.warning(f"Failed to fetch documents: {e}")
            
            # Build prompt
            prompt_parts = []
            prompt_parts.append("You are a helpful beekeeping assistant. Answer the user's question based on the provided context.")
            prompt_parts.append("\nIMPORTANT FORMATTING GUIDELINES:")
            prompt_parts.append("- DO NOT use tables or table formatting in your response")
            prompt_parts.append("- Use bullet points, numbered lists, or simple paragraphs instead")
            prompt_parts.append("- Format content for mobile readability with clear line breaks")
            prompt_parts.append("- Keep responses concise and scannable")
            
            if user_data_available and user_data_text:
                max_chars = RAG_CONFIG.get('max_user_data_chars', 6000) if 'max_user_data_chars' in RAG_CONFIG else 6000
                if len(user_data_text) > max_chars:
                    user_data_text = user_data_text[:max_chars] + "\n\n[User data truncated]"
                prompt_parts.append(f"\nUSER'S HIVE DATA:\n{user_data_text}")
            
            if document_context:
                prompt_parts.append(f"\nBEELKEEPING DOCUMENTATION:\n{document_context}")
            
            prompt_parts.append(f"\n\nUSER QUESTION: {question}")
            prompt_parts.append("\n\nAnswer the question using the information provided above. Be specific and cite sources when making factual claims.")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Call LLM directly
            from langchain_core.callbacks import UsageMetadataCallbackHandler
            usage_callback = UsageMetadataCallbackHandler()
            
            model_name = getattr(self.llm, 'model_name', None) or RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
            llm_for_query = ChatOpenAI(
                model=model_name,
                temperature=getattr(self.llm, 'temperature', 0.3),
                max_tokens=getattr(self.llm, 'max_tokens', 5000),
                openai_api_key=getattr(self.llm, 'openai_api_key', OPENROUTER_API_KEY),
                openai_api_base=getattr(self.llm, 'openai_api_base', 'https://openrouter.ai/api/v1'),
                streaming=False
            )
            
            from langchain_core.runnables import RunnableConfig
            response = llm_for_query.invoke(
                full_prompt,
                config=RunnableConfig(callbacks=[usage_callback])
            )
            
            # Extract token usage from LLM call
            if hasattr(usage_callback, 'usage_metadata') and usage_callback.usage_metadata:
                for model_name, usage in usage_callback.usage_metadata.items():
                    normalized_name = model_name
                    if 'gpt-oss' in model_name.lower():
                        normalized_name = RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
                    elif 'gpt-4o' in model_name.lower() and 'gpt-4o-mini' not in model_name.lower():
                        normalized_name = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
                    
                    if normalized_name not in token_usage_by_model:
                        token_usage_by_model[normalized_name] = {"input": 0, "output": 0}
                    
                    token_usage_by_model[normalized_name]["input"] += usage.get('input_tokens', 0)
                    token_usage_by_model[normalized_name]["output"] += usage.get('output_tokens', 0)
            
            # Merge classification token usage from intent (if available)
            # This captures GPT-4o costs for the classification step
            if intent and intent.get("token_usage"):
                classification_model = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
                if classification_model not in token_usage_by_model:
                    token_usage_by_model[classification_model] = {"input": 0, "output": 0}
                
                classification_tokens = intent["token_usage"]
                token_usage_by_model[classification_model]["input"] += classification_tokens.get("input", 0)
                token_usage_by_model[classification_model]["output"] += classification_tokens.get("output", 0)
            
            # Extract answer
            raw_answer = response.content if hasattr(response, 'content') else str(response)
            
            def _extract_final_answer(text: str) -> str:
                """Extract the final answer from LLM output, filtering out intermediate thinking."""
                if not text:
                    return text
                
                text = text.strip()
                lowered = text.lower()
                
                # Skip if it looks like intermediate thinking/reasoning
                thinking_indicators = [
                    "i need to",
                    "we need to",
                    "we will",
                    "let me",
                    "i should",
                    "i'll",
                    "action:",
                    "thought:",
                    "observation:",
                ]
                if any(lowered.startswith(indicator) for indicator in thinking_indicators):
                    return ""
                
                # Extract final answer if prefixed
                if lowered.startswith("final answer:"):
                    return text[len("final answer:"):].lstrip()
                if lowered.startswith("final:"):
                    return text[len("final:"):].lstrip()
                if lowered.startswith("answer:"):
                    return text[len("answer:"):].lstrip()
                
                # Remove any remaining "Action:" or "Thought:" prefixes
                lines = text.split("\n")
                filtered_lines = []
                skip_next = False
                for line in lines:
                    line_lower = line.lower().strip()
                    if any(line_lower.startswith(indicator) for indicator in ["action:", "thought:", "observation:"]):
                        skip_next = True
                        continue
                    if skip_next and line.strip() == "":
                        skip_next = False
                        continue
                    skip_next = False
                    filtered_lines.append(line)
                
                result = "\n".join(filtered_lines).strip()
                return result if result else text
            
            answer = _extract_final_answer(raw_answer)
            
            # If extraction returned empty, use raw answer
            if not answer or answer.strip() == "":
                answer = raw_answer if raw_answer else "I couldn't process your question. Please try rephrasing it."
            
            # Clean up debug text
            answer = re.sub(r'\(search_[a-zA-Z0-9_]+\)', '', answer)
            answer = re.sub(r'\(get_user_[a-zA-Z0-9_]+\)', '', answer)
            answer = re.sub(r'\([a-zA-Z0-9_]+_[a-zA-Z0-9_]+\)', '', answer)
            answer = re.sub(r'\[search.*?\]', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'【[^】]*】', '', answer)
            answer = answer.strip()
            
            # Process sources
            sources = []
            if user_data_available:
                sources.append({
                    "source_type": "user_data",
                    "chunk_text": user_data_text[:200] + "..." if len(user_data_text) > 200 else user_data_text,
                    "description": "User's personal hive inspection data"
                })
            
            if self._last_source_documents:
                min_similarity = RAG_CONFIG.get('min_similarity_for_display', 0.3)
                max_sources = RAG_CONFIG.get('max_sources_display', 5)
                
                doc_pages = {}
                for doc in self._last_source_documents:
                    similarity = doc.metadata.get("similarity", 0.0)
                    if similarity < min_similarity:
                        continue
                    
                    doc_title = doc.metadata.get("document_title", "")
                    page_num = doc.metadata.get("page_number")
                    doc_key = (doc_title, doc.metadata.get("organization"), doc.metadata.get("publication_year"), doc.metadata.get("source_url"))
                    
                    if doc_key not in doc_pages:
                        doc_pages[doc_key] = {}
                    
                    if page_num not in doc_pages[doc_key] or similarity > doc_pages[doc_key][page_num]["similarity"]:
                        doc_pages[doc_key][page_num] = {
                            "document_title": doc_title,
                            "similarity": similarity,
                            "chunk_text": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                            "chunk_id": doc.metadata.get("chunk_id"),
                            "page_number": page_num,
                            "organization": doc.metadata.get("organization"),
                            "publication_year": doc.metadata.get("publication_year"),
                            "source_url": doc.metadata.get("source_url")
                        }
                
                # Consolidate sources
                for doc_key, pages_dict in doc_pages.items():
                    pages = list(pages_dict.values())
                    pages_with_nums = [p for p in pages if p["page_number"] is not None]
                    pages_without_nums = [p for p in pages if p["page_number"] is None]
                    
                    pages_with_nums.sort(key=lambda x: x["page_number"])
                    
                    if pages_with_nums:
                        ranges = []
                        current_range = [pages_with_nums[0]]
                        for page in pages_with_nums[1:]:
                            if page["page_number"] == current_range[-1]["page_number"] + 1:
                                current_range.append(page)
                            else:
                                ranges.append(current_range)
                                current_range = [page]
                        ranges.append(current_range)
                        
                        for page_range in ranges:
                            if len(page_range) == 1:
                                sources.append(page_range[0])
                            else:
                                consolidated = page_range[0].copy()
                                consolidated["page_number"] = f"{page_range[0]['page_number']}-{page_range[-1]['page_number']}"
                                sources.append(consolidated)
                    
                    for page in pages_without_nums:
                        sources.append(page)
                    
                    if len(sources) >= max_sources:
                        break
                
                sources = sources[:max_sources]
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            return {
                "answer": answer,
                "sources": sources,
                "metadata": {
                    "intent_classification": intent,
                    "token_usage_by_model": token_usage_by_model,
                },
                "latency_ms": latency_ms,
            }
        except Exception as e:
            logging.error(f"Error in query_with_simple_llm: {e}")
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "sources": [],
                "metadata": {},
                "latency_ms": 0,
            }
    
    def query_with_user_tools(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None,
        force_always_both: bool = False,
        force_agent_discretion: bool = False,
        force_personal_only: bool = False,
        force_documents_only: bool = False,
        # ADD YOUR CUSTOM PARAMETERS HERE FOR STRATEGY TESTING
        custom_intent: Optional[str] = None,
        custom_routing: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enhanced query using agent with intent classification.
        
        MODIFY THIS METHOD to test different routing strategies!
        Add custom parameters as needed for your experiments.
        """
        try:
            # Reset source documents
            self._last_source_documents = []
            
            # Initialize token usage tracker (no callbacks needed - we'll extract from results)
            token_usage_by_model = {}
            
            # Create user data tool
            user_data_tool = UserHiveDataTool(user_id)
            
            # Initialize tools list (will be filtered based on routing mode)
            tools = [self.document_search_tool, user_data_tool]
            
            # Determine intent and routing
            if force_personal_only:
                # Personal only mode - only user data tool
                intent = {"PRIMARY_DATA_NEED": "personal_only"}
                enhanced_question = question
                agent_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful beekeeping assistant. You have access to one tool:
1. get_user_hive_data - Retrieve the user's personal hive inspection data

Use this tool to answer the user's question about their personal hive data. Once you have the information, provide your answer immediately."""),
                    ("user", "{input}"),
                    ("placeholder", "{agent_scratchpad}")
                ])
            elif force_documents_only:
                # Documents only mode - only document search tool
                intent = {"PRIMARY_DATA_NEED": "documents_only"}
                enhanced_question = question
                agent_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful beekeeping assistant. You have access to one tool:
1. search_beekeeping_documents - Search authoritative beekeeping documents

Use this tool to answer the user's question about general beekeeping knowledge. Once you have the information, provide your answer immediately."""),
                    ("user", "{input}"),
                    ("placeholder", "{agent_scratchpad}")
                ])
            elif force_agent_discretion:
                # Agent discretion mode - agent decides which tools to use, no pre-fetching
                intent = None  # No intent classification in agent discretion mode
                enhanced_question = question  # No pre-fetching - agent decides what to fetch
                agent_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful beekeeping assistant. You have access to two tools:
1. search_beekeeping_documents - Search authoritative beekeeping documents for factual information.
   Use this for general beekeeping questions, best practices, measurements, or recommendations.
2. get_user_hive_data - Retrieve the user's personal hive inspection data.
   Use this when the user asks about "my hives", "which of my", or personal data.

WORKFLOW:
- Use your judgment to determine which tool(s) are needed based on the question
- If the question is clearly about personal data (e.g., "which of my hives"), use get_user_hive_data
- If the question is clearly general (e.g., "what is a queen excluder"), use search_beekeeping_documents
- If the question requires both personal data AND general knowledge, use both tools

IMPORTANT:
- Do NOT make redundant tool calls - call each tool at most once per query
- Do NOT call the same tool multiple times
- Once you have the necessary information, provide your answer immediately
- After getting information from tools, immediately provide your final answer
- Format your response naturally without mentioning tool names or execution details
- Be specific and cite sources when making factual claims
- If you have enough information to answer, STOP and provide the answer - do not call more tools"""),
                    ("user", "{input}"),
                    ("placeholder", "{agent_scratchpad}")
                ])
            elif force_always_both:
                # Always both mode - pre-fetch user data like normal path does
                intent = {"PRIMARY_DATA_NEED": "both_combined"}
                # Pre-fetch user data to include in enhanced question (same as normal path)
                try:
                    user_context = user_data_tool._run()
                    if "No hives found" not in user_context:
                        enhanced_question = f"""
INTENT ANALYSIS:
- Primary need: both_combined
- Focus area: user_data

USER QUESTION: {question}

USER DATA AVAILABLE: Use specific hive names, dates, and measurements from the user's data.
"""
                        max_chars = RAG_CONFIG.get('max_user_data_chars', 6000) if 'max_user_data_chars' in RAG_CONFIG else 6000
                        user_data_text = user_context
                        if max_chars and len(user_data_text) > max_chars:
                            user_data_text = user_data_text[:max_chars] + "\n\n[User data truncated]"
                        enhanced_question += f"\n\nUSER DATA CONTEXT:\n{user_data_text}\n"
                    else:
                        enhanced_question = question
                except Exception:
                    enhanced_question = question
                agent_prompt = self.agent_prompt
            elif custom_intent or custom_routing:
                # Custom routing mode (MODIFY THIS FOR YOUR STRATEGIES)
                intent = {"PRIMARY_DATA_NEED": custom_routing or custom_intent or "both_combined"}
                enhanced_question = question
                agent_prompt = self.agent_prompt
            else:
                # Normal LLM classifier mode
                intent = self.classify_user_intent(question)
                
                # Extract token usage from intent classification
                intent_token_usage = intent.get("token_usage", {})
                if intent_token_usage:
                    intent_model = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
                    if intent_model not in token_usage_by_model:
                        token_usage_by_model[intent_model] = {"input": 0, "output": 0}
                    token_usage_by_model[intent_model]["input"] += intent_token_usage.get("input", 0)
                    token_usage_by_model[intent_model]["output"] += intent_token_usage.get("output", 0)
                
                # Pre-fetch user data if needed
                user_data_available = False
                context = {}
                if intent.get('PRIMARY_DATA_NEED') in ['personal_only', 'both_combined']:
                    try:
                        user_context = user_data_tool._run()
                        if "No hives found" not in user_context and "error" not in user_context.lower():
                            context['user_data'] = user_context
                            user_data_available = True
                    except Exception as e:
                        context['user_data'] = f"Could not fetch user data: {str(e)}"
                
                # Enhanced question with intent context (matching backend format)
                enhanced_question = f"""
INTENT ANALYSIS:
- Primary need: {intent.get('PRIMARY_DATA_NEED', 'unknown')}
- Focus area: {intent.get('SPECIFIC_FOCUS', 'general')}
- Strategy: {intent.get('TOOL_STRATEGY', 'documents_first')}

USER QUESTION: {question}

{"USER DATA AVAILABLE: Use specific hive names, dates, and measurements from the user's data." if user_data_available else "NO USER DATA: Provide general guidance."}
                """
                
                if user_data_available:
                    max_chars = RAG_CONFIG.get('max_user_data_chars', 6000) if 'max_user_data_chars' in RAG_CONFIG else 6000
                    user_data_text = context['user_data']
                    if max_chars and len(user_data_text) > max_chars:
                        user_data_text = user_data_text[:max_chars] + "\n\n[User data truncated for prompt length]"
                    enhanced_question += f"\n\nUSER DATA CONTEXT (Last 90 days):\n{user_data_text}\n"
                
                agent_prompt = self.agent_prompt
            
            # Filter tools based on routing mode (tools already initialized above)
            if force_personal_only:
                tools = [user_data_tool]
            elif force_documents_only:
                tools = [self.document_search_tool]
            # else: tools already set to both tools above
            
            # Use LangChain's built-in UsageMetadataCallbackHandler for token tracking
            from langchain_core.callbacks import UsageMetadataCallbackHandler
            
            usage_callback = UsageMetadataCallbackHandler()
            
            # Create LLM instance
            model_name = getattr(self.llm, 'model_name', None) or RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
            llm_for_agent = ChatOpenAI(
                model=model_name,
                temperature=getattr(self.llm, 'temperature', 0.3),
                max_tokens=getattr(self.llm, 'max_tokens', 5000),
                openai_api_key=getattr(self.llm, 'openai_api_key', OPENROUTER_API_KEY),
                openai_api_base=getattr(self.llm, 'openai_api_base', 'https://openrouter.ai/api/v1'),
                streaming=False
            )
            
            # Create agent
            agent = create_openai_tools_agent(
                llm=llm_for_agent,
                tools=tools,
                prompt=agent_prompt
            )
            
            # Create executor with callback for token tracking
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                handle_parsing_errors=True,
                return_intermediate_steps=False,  # Match production configuration
                max_iterations=10
            )
            
            # Execute with callback to track token usage
            from langchain_core.runnables import RunnableConfig
            result = agent_executor.invoke(
                {"input": enhanced_question},
                config=RunnableConfig(callbacks=[usage_callback])
            )
            
            # Extract token usage from the callback's usage_metadata
            # The callback aggregates usage by model name
            # NOTE: This works independently of return_intermediate_steps because callbacks
            # fire during execution, not from the return value structure
            if hasattr(usage_callback, 'usage_metadata') and usage_callback.usage_metadata:
                for model_name, usage in usage_callback.usage_metadata.items():
                    # Normalize model name (callback might use full model name with version)
                    # Map to our standard format
                    normalized_name = model_name
                    # If it's the agent model, use our config name
                    if 'gpt-oss' in model_name.lower():
                        normalized_name = RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b')
                    elif 'gpt-4o' in model_name.lower() and 'gpt-4o-mini' not in model_name.lower():
                        normalized_name = RAG_CONFIG.get("intent_classification_model", "openai/gpt-4o")
                    
                    if normalized_name not in token_usage_by_model:
                        token_usage_by_model[normalized_name] = {"input": 0, "output": 0}
                    
                    # Extract from usage dict (has input_tokens, output_tokens, total_tokens)
                    token_usage_by_model[normalized_name]["input"] += usage.get('input_tokens', 0)
                    token_usage_by_model[normalized_name]["output"] += usage.get('output_tokens', 0)
            else:
                # Warn if callback didn't capture tokens - this shouldn't happen but is important for validation
                # This could indicate:
                # 1. No LLM calls were made (unlikely for agent execution)
                # 2. Callbacks didn't propagate to tool LLM calls (DocumentSearchTool makes LLM calls)
                # 3. Token metadata wasn't available in the response
                logging.warning(
                    f"Token tracking: UsageMetadataCallbackHandler did not capture tokens. "
                    f"Callback has usage_metadata: {hasattr(usage_callback, 'usage_metadata')}, "
                    f"usage_metadata value: {getattr(usage_callback, 'usage_metadata', None)}. "
                    f"This may indicate tool LLM calls (DocumentSearchTool) are not being tracked."
                )
            
            # Process sources
            # Documents are already chunked - we just need to serialize them for JSON storage
            # RAGAS needs the chunk text, so we include it here (it's already in doc.page_content)
            sources = []
            for doc in self._last_source_documents:
                sources.append({
                    "title": doc.metadata.get("document_title", "Unknown"),
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "page_number": doc.metadata.get("page_number"),
                    "similarity": doc.metadata.get("similarity", 0.0),
                    "chunk_text": doc.page_content if hasattr(doc, 'page_content') and doc.page_content else None,
                })
            
            # Token usage already extracted above from result metadata
            
            # Extract answer - agent executor returns dict with "output" key
            # When return_intermediate_steps=False (production config), it returns: {"output": "..."}
            # When return_intermediate_steps=True, it also includes "intermediate_steps": [...]
            
            def _extract_final_answer(text: str) -> str:
                """Extract the final answer from agent output, filtering out intermediate thinking."""
                if not text:
                    return text
                
                # Remove common agent thinking prefixes
                text = text.strip()
                lowered = text.lower()
                
                # Skip if it looks like intermediate thinking/reasoning
                # Match production exactly
                thinking_indicators = [
                    "i need to",
                    "we need to",
                    "let me",
                    "i should",
                    "i'll",
                    "action:",
                    "thought:",
                    "observation:",
                ]
                if any(lowered.startswith(indicator) for indicator in thinking_indicators):
                    # This looks like thinking, not a final answer - return empty to trigger error handling
                    return ""
                
                # Extract final answer if prefixed
                if lowered.startswith("final answer:"):
                    return text[len("final answer:"):].lstrip()
                if lowered.startswith("final:"):
                    return text[len("final:"):].lstrip()
                if lowered.startswith("answer:"):
                    return text[len("answer:"):].lstrip()
                
                # Remove any remaining "Action:" or "Thought:" prefixes (in case they appear mid-text)
                lines = text.split("\n")
                filtered_lines = []
                skip_next = False
                for line in lines:
                    line_lower = line.lower().strip()
                    if any(line_lower.startswith(indicator) for indicator in ["action:", "thought:", "observation:"]):
                        skip_next = True
                        continue
                    if skip_next and line.strip() == "":
                        skip_next = False
                        continue
                    skip_next = False
                    filtered_lines.append(line)
                
                result = "\n".join(filtered_lines).strip()
                return result if result else text  # Fallback to original if filtering removed everything
            
            # Match production service exactly: use result.get("output") with default, then apply _extract_final_answer
            # Production does: raw_answer = result.get("output", default), then raw_answer = _extract_final_answer(raw_answer)
            raw_answer = result.get("output", "I couldn't process your question. Please try rephrasing it.")
            
            # If agent hit max_iterations, treat as empty (this is an error condition)
            if raw_answer == "Agent stopped due to max iterations.":
                raw_answer = ""
            
            # Apply extraction function and overwrite raw_answer (same as production line 974)
            answer = _extract_final_answer(raw_answer)
            
            # Production then validates and potentially retries if answer is empty
            # For validation, if extraction returned empty, use the default message
            if not answer or answer.strip() == "":
                answer = "I couldn't process your question. Please try rephrasing it."
            
            # Clean up the final answer to remove any debug text and prefixes
            # Remove common prefixes that appear ONLY at the start of answers (^ anchor ensures start-of-string match)
            prefix_patterns = [
                r'^answer\.',           # "answer." at start
                r'^text\.',             # "text." at start
                r'^accordingly\.',      # "accordingly." at start
                r'^points\.',           # "points." at start
                r'^produce\.',          # "produce." at start
                r'^answer\*\*',         # "answer.**" at start
                r'^text\*\*',           # "text.**" at start
                r'^accordingly\*\*',    # "accordingly.**" at start
                r'^points\*\*',         # "points.**" at start
            ]
            for pattern in prefix_patterns:
                # ^ anchor ensures we only match at the start of the string (not MULTILINE, so ^ = start of entire string)
                answer = re.sub(pattern, '', answer, flags=re.IGNORECASE)
            
            # Remove debug text patterns (same as backend)
            answer = re.sub(r'\(search_[a-zA-Z0-9_]+\)', '', answer)  # Remove (search_beekeeping_documents_xyz)
            answer = re.sub(r'\(get_user_[a-zA-Z0-9_]+\)', '', answer)  # Remove (get_user_hive_data_xyz)
            answer = re.sub(r'\([a-zA-Z0-9_]+_[a-zA-Z0-9_]+\)', '', answer)  # Remove any (tool_name_id) patterns
            answer = re.sub(r'\[search.*?\]', '', answer, flags=re.IGNORECASE)  # Remove [search...] patterns
            answer = re.sub(r'【[^】]*】', '', answer)  # Remove 【search_beekeeping_documents】 patterns with Japanese brackets
            answer = answer.strip()
            
            # Log if answer is still empty but we have token usage (indicates execution happened)
            if not answer and token_usage_by_model:
                import sys
                error_msg = (
                    f"Agent executed (tokens used: {token_usage_by_model}) but answer is empty. "
                    f"Result type: {type(result)}, Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}"
                )
                logging.error(error_msg)
                # Also print to stderr for immediate visibility
                print(f"ERROR: {error_msg}", file=sys.stderr)
                if isinstance(result, dict):
                    print(f"  Result keys: {list(result.keys())}", file=sys.stderr)
                    for key in result.keys():
                        val = result[key]
                        if key == "intermediate_steps" and isinstance(val, list):
                            print(f"  {key}: list with {len(val)} steps", file=sys.stderr)
                            if val:
                                # Print details about each step to help debug parsing errors
                                for i, step in enumerate(val):
                                    print(f"    Step {i}: type={type(step)}", file=sys.stderr)
                                    if isinstance(step, tuple) and len(step) >= 2:
                                        action = step[0]
                                        observation = step[1]
                                        print(f"      Action type: {type(action)}", file=sys.stderr)
                                        if hasattr(action, 'tool'):
                                            print(f"      Action tool: {action.tool}", file=sys.stderr)
                                        if hasattr(action, 'log'):
                                            log_preview = str(action.log)[:300] if action.log else "None"
                                            print(f"      Action log: {log_preview}...", file=sys.stderr)
                                        if hasattr(action, 'return_values'):
                                            print(f"      Action return_values: {action.return_values}", file=sys.stderr)
                                        obs_preview = str(observation)[:200] if observation else "None"
                                        print(f"      Observation: {obs_preview}...", file=sys.stderr)
                                    else:
                                        print(f"      Step content: {str(step)[:200]}", file=sys.stderr)
                        else:
                            val_str = str(val)[:200] if not isinstance(val, (list, dict)) else f"{type(val)} (len={len(val) if hasattr(val, '__len__') else 'N/A'})"
                            print(f"  {key}: {type(val)} = {val_str}", file=sys.stderr)
                    # Also check if output exists but is empty string
                    if "output" in result:
                        output_val = result["output"]
                        print(f"  'output' key exists: type={type(output_val)}, value='{str(output_val)[:100]}'", file=sys.stderr)
            
            return {
                "answer": answer,
                "sources": sources,
                "metadata": {
                    "intent_classification": intent if not force_agent_discretion else None,
                    "token_usage_by_model": token_usage_by_model,  # Store per-model usage
                }
            }
        except Exception as e:
            logging.error(f"Error in query_with_user_tools: {e}")
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "sources": [],
                "metadata": {}
            }


# Singleton instance
_service_instance = None

def get_validation_rag_service() -> ValidationRAGService:
    """Get or create the validation RAG service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ValidationRAGService()
    return _service_instance

