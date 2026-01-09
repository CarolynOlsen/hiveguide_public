"""
LangChain-based RAG service for the hive scribe application.
Migrated from the DIY RAG implementation to use LangChain components.
Now includes agent support for querying both documents and user personal data.
"""

from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks import (
    CallbackManagerForToolRun,
    AsyncCallbackManagerForToolRun,
)
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import numpy as np
import json
import re
from pathlib import Path

from .config import DATABASE_URL, OPENAI_API_KEY, OPENROUTER_API_KEY, RAG_CONFIG, PDF_SOURCES
from .models import DocumentChunk
from .user_data_tool import UserHiveDataTool



class PostgresVectorStore:
    """
    Custom vector store that uses the existing PostgreSQL schema.
    Works with the existing document_chunks table structure.
    """
    
    def __init__(self, connection_string: str, embedding_function):
        self.connection_string = connection_string
        self.embedding_function = embedding_function
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """Add documents to the vector store."""
        session = self.SessionLocal()
        try:
            # Generate embeddings for all documents
            texts = [doc.page_content for doc in documents]
            embeddings = self.embedding_function.embed_documents(texts)
            
            doc_ids = []
            for doc, embedding in zip(documents, embeddings):
                # Create DocumentChunk record
                chunk = DocumentChunk(
                    document_id=doc.metadata.get('document_id'),
                    chunk_text=doc.page_content,
                    embedding=json.dumps(embedding),
                    embedding_vector=embedding,
                    metadata_json=doc.metadata,
                    document_title=doc.metadata.get('document_title', ''),
                    publication_year=doc.metadata.get('publication_year'),
                    organization=doc.metadata.get('organization'),
                    source_url=doc.metadata.get('source_url'),
                    page_number=doc.metadata.get('page_number'),
                    section_title=doc.metadata.get('section_title'),
                    token_count=len(doc.page_content.split()),
                    chunk_position=doc.metadata.get('chunk_position', 0)
                )
                session.add(chunk)
                session.flush()
                doc_ids.append(str(chunk.id))
            
            session.commit()
            return doc_ids
        finally:
            session.close()
    
    def similarity_search(self, query: str, k: int = 4, **kwargs) -> List[Document]:
        """Perform similarity search using the existing database structure."""
        # Generate query embedding
        query_embedding = self.embedding_function.embed_query(query)
        
        session = self.SessionLocal()
        try:
            # Get all chunks with embeddings
            chunks = session.query(DocumentChunk).filter(
                DocumentChunk.embedding_vector.isnot(None)
            ).all()
            
            # Calculate similarities
            def cosine_similarity(vec1, vec2):
                return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            
            chunks_with_similarity = [
                (chunk, cosine_similarity(chunk.embedding_vector, query_embedding))
                for chunk in chunks
            ]
            
            # Sort by similarity and take top k
            chunks_with_similarity.sort(key=lambda x: x[1], reverse=True)
            top_chunks = chunks_with_similarity[:k]
            
            # Convert to LangChain Documents
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


class LangChainRAGService:
    """
    LangChain-based RAG service that replaces the DIY implementation.
    Uses the existing PostgreSQL schema and adds conversation memory.
    """
    
    def __init__(self):
        # Initialize embeddings model
        self.embeddings = OpenAIEmbeddings(
            model=RAG_CONFIG.get('embedding_model', 'text-embedding-3-small'),
            openai_api_key=OPENAI_API_KEY
        )
        
        # Initialize LLM with OpenRouter
        self.llm = ChatOpenAI(
            model=RAG_CONFIG.get('llm_model', 'openai/gpt-oss-120b'),
            temperature=0.3,
            max_tokens=5000,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1"
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CONFIG.get('chunk_size_tokens', 600),
            chunk_overlap=RAG_CONFIG.get('chunk_overlap_tokens', 100),
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Initialize vector store with existing database
        self.vector_store = PostgresVectorStore(
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings
        )
        
        # Initialize simple chat history storage
        self.chat_history = []
        self.max_history = 10  # Keep last 10 messages
        
        # Create custom prompt template for conversational RAG
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a helpful beekeeping expert. Answer questions based on the provided context about beekeeping practices.

IMPORTANT FORMATTING GUIDELINES:
- DO NOT use tables or table formatting in your response
- Use bullet points, numbered lists, or simple paragraphs instead
- Format content for mobile readability with clear line breaks
- Keep responses concise and scannable

Context from beekeeping documents:
{context}

Question: {question}

Answer: """
        )
        
        # Initialize retriever and response chain compatible with LangChain 0.3+
        self.retriever = self._create_retriever()
        self.response_chain = (
            self.prompt_template
            | self.llm
            | StrOutputParser()
        )
        
        # Initialize agent components for user data integration
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
    
    def _format_documents(self, documents: List[Document]) -> str:
        """Format retrieved documents into a context string."""
        if not documents:
            return "No relevant documents found."

        formatted_sections = []
        for index, doc in enumerate(documents, start=1):
            metadata = doc.metadata or {}
            title = metadata.get('document_title') or metadata.get('source_file') or f"Document {index}"
            page = metadata.get('page_number')
            header_parts = [f"[Source {index}] {title}"]
            if page is not None:
                header_parts.append(f"(Page {page})")
            header = " ".join(header_parts)
            formatted_sections.append(f"{header}\n{doc.page_content}")

        return "\n\n".join(formatted_sections)

    def _run_retrieval(self, query: str) -> Dict[str, Any]:
        """Execute retrieval and LLM response generation for a query."""
        documents = self.retriever.invoke(query)
        context_text = self._format_documents(documents)
        answer_text = self.response_chain.invoke({
            "context": context_text,
            "question": query
        })

        return {
            "result": answer_text,
            "source_documents": documents
        }
    
    def process_pdfs(self, pdf_directory: Path) -> None:
        """
        Process PDFs and store chunks in the database using LangChain.
        Replaces the manual PDF processing in rag_processor.py.
        """
        documents = []
        
        for pdf_path in pdf_directory.glob("*.pdf"):
            print(f"Processing {pdf_path.name}...")
            
            # Get metadata from PDF_SOURCES configuration
            pdf_metadata = PDF_SOURCES.get(pdf_path.name, {})
            
            # Load PDF using LangChain loader
            loader = PyMuPDFLoader(str(pdf_path))
            pdf_documents = loader.load()
            
            # Split documents into chunks
            chunks = self.text_splitter.split_documents(pdf_documents)
            
            # Add metadata to each chunk
            for i, chunk in enumerate(chunks):
                # Extract page number from PyMuPDF metadata (if available)
                page_number = chunk.metadata.get('page', None)
                if page_number is not None:
                    page_number = page_number + 1  # PyMuPDF uses 0-based indexing, we want 1-based
                
                # Extract section title from chunk content (simple heuristic)
                section_title = self._extract_section_title(chunk.page_content)
                
                # Update chunk metadata with complete information
                chunk.metadata.update({
                    'document_title': pdf_metadata.get('title', pdf_path.stem),
                    'publication_year': pdf_metadata.get('year'),
                    'organization': pdf_metadata.get('organization'),
                    'source_url': pdf_metadata.get('url'),
                    'page_number': page_number,
                    'section_title': section_title,
                    'chunk_position': i,
                    'source_file': pdf_path.name
                })
            
            documents.extend(chunks)
        
        if documents:
            print(f"Adding {len(documents)} chunks to vector store...")
            self.vector_store.add_documents(documents)
            print("PDF processing completed.")
    
    def _extract_section_title(self, text: str) -> str:
        """
        Extract section title from chunk text using simple heuristics.
        Looks for lines that appear to be headings (short, capitalized, etc.)
        """
        lines = text.strip().split('\n')
        if not lines:
            return None
            
        first_line = lines[0].strip()
        
        # Simple heuristic: if first line is short and looks like a title
        if (len(first_line) < 100 and 
            len(first_line) > 5 and
            first_line.isupper() or 
            (first_line[0].isupper() and not first_line.endswith('.'))):
            return first_line
        
        # Look for other potential headings in first few lines
        for line in lines[:3]:
            line = line.strip()
            if (len(line) < 80 and len(line) > 5 and 
                (line.isupper() or 
                 (line[0].isupper() and not line.endswith('.') and 
                  sum(c.isupper() for c in line) / len(line) > 0.5))):
                return line
        
        return None
    
    def generate_embeddings_for_existing_chunks(self) -> None:
        """
        Generate embeddings for existing chunks that don't have them.
        This helps migrate from the old system.
        """
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            # Find chunks without embeddings
            chunks_without_embeddings = session.query(DocumentChunk).filter(
                DocumentChunk.embedding_vector.is_(None)
            ).all()
            
            if not chunks_without_embeddings:
                print("All chunks already have embeddings.")
                return
            
            print(f"Generating embeddings for {len(chunks_without_embeddings)} existing chunks...")
            
            # Process in batches
            batch_size = RAG_CONFIG.get('batch_size', 10)
            for i in range(0, len(chunks_without_embeddings), batch_size):
                batch = chunks_without_embeddings[i:i + batch_size]
                texts = [chunk.chunk_text for chunk in batch]
                
                # Generate embeddings
                embeddings = self.embeddings.embed_documents(texts)
                
                # Update chunks
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = json.dumps(embedding)
                    chunk.embedding_vector = embedding
                
                session.commit()
                print(f"Processed batch {i//batch_size + 1}/{(len(chunks_without_embeddings) + batch_size - 1)//batch_size}")
            
            print("Embedding generation completed.")
        finally:
            session.close()
    
    def classify_user_intent(self, question: str) -> Dict[str, Any]:
        """Analyze user question to determine data requirements and response strategy."""
        try:
            classification_prompt = f"""
            Analyze this beekeeping question and classify the user's intent:
            
            Question: {question}
            
            Determine:
            1. PRIMARY_DATA_NEED: personal_only (asking about their own hives), documents_only (general knowledge), or both_combined (personal + general)
            2. SPECIFIC_FOCUS: weight, queen_status, disease, general_advice, inspection_patterns, feeding, seasonal_prep, equipment, etc.
            3. URGENCY: immediate_action_needed, routine_check, informational
            4. TOOL_STRATEGY: user_data_first (get personal data first), documents_first (search documents first), parallel_search (use both simultaneously)
            
            Look for these indicators:
            - "my hives", "my bees", "which of my", "when did I last" = personal_only
            - "what should", "how to", "what are signs of", specific measurements = documents_first
            - "which of my hives need" + factual criteria = both_combined
            
            Respond in JSON format only.
            """
            
            result = self.llm.invoke(classification_prompt)
            
            # Try to parse JSON, fallback to heuristics if parsing fails
            try:
                import json
                intent = json.loads(result.content)
            except:
                # Fallback to simple heuristics
                question_lower = question.lower()
                intent = {
                    "PRIMARY_DATA_NEED": "personal_only" if any(phrase in question_lower for phrase in ["my hive", "my bee", "which of my", "when did i"]) else "documents_first",
                    "SPECIFIC_FOCUS": "weight" if "weight" in question_lower else "general_advice",
                    "URGENCY": "routine_check",
                    "TOOL_STRATEGY": "user_data_first" if "my" in question_lower else "documents_first"
                }
            
            return intent
            
        except Exception as e:
            # Fallback intent classification
            question_lower = question.lower()
            return {
                "PRIMARY_DATA_NEED": "personal_only" if "my" in question_lower else "documents_first",
                "SPECIFIC_FOCUS": "general_advice",
                "URGENCY": "routine_check", 
                "TOOL_STRATEGY": "user_data_first" if "my" in question_lower else "documents_first"
            }
    
    def validate_response(self, question: str, response: str, user_data_available: bool) -> str:
        """Quick validation to catch common mistakes."""
        
        question_lower = question.lower()
        response_lower = response.lower()
        
        # If user asked about "my/their" data but response is generic
        personal_indicators = ['my', 'which of my', 'my hives', 'my bees', 'when did i']
        asked_personal = any(indicator in question_lower for indicator in personal_indicators)
        
        if asked_personal and user_data_available:
            # Check if response includes actual user-specific data
            specific_indicators = ['franksville', 'hillcrest', 'your inspection', 'your hive', 'on 20', 'your most recent']
            has_specific_data = any(indicator in response_lower for indicator in specific_indicators)
            
            if not has_specific_data and len(response) > 100:
                return "ERROR: User asked about their specific hives but got generic advice. Please use their actual hive data to provide specific recommendations with hive names, dates, and measurements."
        
        # Check for factual claims without sources when documents should be searched
        factual_patterns = [r'\b\d+\s*(?:pounds?|lbs?|degrees?|°[fc]?)\b', r'\b\d+\s*to\s*\d+\s*(?:pounds?|lbs?)\b']
        has_numbers = any(re.search(pattern, response_lower) for pattern in factual_patterns)
        
        if has_numbers and 'source' not in response_lower and 'document' not in response_lower:
            return "ERROR: Response contains specific measurements but no source citations. Please search documents first for any factual claims with numbers."
        
        return response  # Valid response
    
    def _init_agent_components(self):
        """Initialize the agent components for combined document and user data queries."""
        
        # Storage for source documents found during tool execution
        self._last_source_documents = []
        
        # Create a document search tool from the existing QA chain
        class DocumentSearchTool(BaseTool):
            name: str = "search_beekeeping_documents"
            description: str = """Search through beekeeping documents and educational materials for factual information.
            
            USE THIS WHEN:
            - User asks for specific numbers, measurements, or weights (e.g., "how much should a hive weigh")
            - User wants best practices or recommendations (e.g., "what should I do for winter prep")
            - User asks "what are signs of" or "how to" questions
            - Making any factual claims about beekeeping practices
            - Need to verify information with authoritative sources
            
            DO NOT USE FOR:
            - Questions purely about the user's personal hive data (use user data tool instead)
            - Questions asking "which of my hives" without needing factual criteria
            
            ALWAYS search documents BEFORE stating any specific measurements, weights, temperatures, or timing.
            This tool searches authoritative beekeeping publications and returns reliable, citable information."""
            
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
            ) -> str:
                try:
                    result = self._retrieval_fn(query)
                    # Store source documents for later citation processing
                    if "source_documents" in result:
                        self._parent_service._last_source_documents.extend(result["source_documents"])
                    return result.get("result", "No information found in documents.")
                except Exception as e:
                    return f"Error searching documents: {str(e)}"

            async def _arun(
                self,
                query: str,
                run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
            ) -> str:
                return self._run(query)
        
        self.document_search_tool = DocumentSearchTool(self._run_retrieval, self)
        
        # Create the agent prompt with structured thinking
        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a smart beekeeping assistant. For every question, follow this exact process:

STEP 1 - ANALYZE THE QUESTION:
- What specific information is the user requesting?
- Do they want info about THEIR hives ("my hives", "which of my", "when did I last") or GENERAL beekeeping knowledge?
- Are they asking for measurements, comparisons, recommendations, or personal hive analysis?

STEP 2 - DETERMINE DATA STRATEGY:
- If asking about "my hives/my data": Use get_user_hive_data tool FIRST to get their specific hive information
- If asking for specific facts/measurements (weights, temperatures, timing): Use search_beekeeping_documents FIRST for authoritative sources
- If combining personal analysis with factual standards: Use BOTH tools - documents for criteria, user data for specific hive details

STEP 3 - BE PRECISE AND SPECIFIC:
- For personal questions: Give specific hive names, exact dates, and actual measurements from their data
- For factual claims: Always cite the documented sources you found
- Don't give generic advice when specific data is available
- Combine their personal data with general knowledge appropriately

CRITICAL RULES:
1. NEVER include tool execution details or debug information in your response
2. Your response should read naturally and professionally
3. When making factual claims about measurements, weights, or timing, you MUST search documents first
4. When users ask about "my hives", provide specific hive names and inspection details
5. If you find user data, use actual hive names, dates, and measurements rather than generic advice

EXAMPLE GOOD RESPONSE FOR "Which of my hives need winter weight?":
"Based on your recent inspections, Franksville 4 (74 lbs) and Franksville 5 (68 lbs) are below the recommended 80-100 lb range for winter survival according to beekeeping literature."

EXAMPLE BAD RESPONSE:
"Generally, hives need 80-100 pounds for winter. You should weigh your hives and check if they meet this threshold."

Formatting Requirements:
- NO tables or table formatting
- Use bullet points, numbered lists, or simple paragraphs
- Format for mobile readability with clear line breaks
- Be concise and scannable
- Your response should contain only the answer, no tool references or debug information"""),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
    
    def query_with_user_tools(self, question: str, user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Enhanced query using the agent with intent classification and validation.
        
        Args:
            question: The user's question
            user_id: The authenticated user's ID for data access
            session_id: Optional session ID for conversation memory
        
        Returns:
            Dict containing answer and sources
        """
        try:
            # Step 1: Classify user intent to optimize tool usage
            intent = self.classify_user_intent(question)
            
            # Reset source documents collection
            self._last_source_documents = []
            
            # Step 2: Pre-fetch relevant context based on intent
            context = {}
            user_data_available = False
            
            # Create user-specific hive data tool
            user_data_tool = UserHiveDataTool(user_id)
            
            # Pre-fetch user data if intent suggests it's needed
            if intent.get('PRIMARY_DATA_NEED') in ['personal_only', 'both_combined']:
                try:
                    user_context = user_data_tool._run()
                    if "No hives found" not in user_context and "error" not in user_context.lower():
                        context['user_data'] = user_context
                        user_data_available = True
                except Exception as e:
                    context['user_data'] = f"Could not fetch user data: {str(e)}"
            
            # Step 3: Enhanced question with intent context
            enhanced_question = f"""
INTENT ANALYSIS:
- Primary need: {intent.get('PRIMARY_DATA_NEED', 'unknown')}
- Focus area: {intent.get('SPECIFIC_FOCUS', 'general')}
- Strategy: {intent.get('TOOL_STRATEGY', 'documents_first')}

USER QUESTION: {question}

{"USER DATA AVAILABLE: Use specific hive names, dates, and measurements from the user's data." if user_data_available else "NO USER DATA: Provide general guidance."}
            """

            if user_data_available:
                max_chars = RAG_CONFIG.get('max_user_data_chars', 6000)
                user_data_text = context['user_data']
                if max_chars and len(user_data_text) > max_chars:
                    truncated_user_data = user_data_text[:max_chars] + "\n\n[User data truncated for prompt length]"
                else:
                    truncated_user_data = user_data_text

                enhanced_question += f"\n\nUSER DATA CONTEXT (Last 90 days):\n{truncated_user_data}\n"
            
            # Combine tools
            tools = [self.document_search_tool, user_data_tool]
            
            # Create agent
            agent = create_openai_tools_agent(
                llm=self.llm,
                tools=tools,
                prompt=self.agent_prompt
            )
            
            # Create agent executor
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                handle_parsing_errors=True,
                return_intermediate_steps=False,  # Don't return debug info
                max_iterations=5  # Increased from 3 to allow more complex reasoning and tool usage
            )
            
            # Execute the agent with enhanced question
            result = agent_executor.invoke({
                "input": enhanced_question
            })
            
            # Process sources using the existing citation logic
            sources = []
            if self._last_source_documents:
                # Use the same citation processing logic as the original query method
                min_similarity = RAG_CONFIG.get('min_similarity_for_display', 0.3)
                max_sources = RAG_CONFIG.get('max_sources_display', 5)
                
                # Collect and deduplicate sources
                doc_pages = {}  # doc_key -> {page_num: source}
                
                for doc in self._last_source_documents:
                    similarity = doc.metadata.get("similarity", 0.0)
                    
                    # Skip sources below minimum similarity threshold
                    if similarity < min_similarity:
                        continue
                    
                    doc_title = doc.metadata.get("document_title", "")
                    page_num = doc.metadata.get("page_number")
                    
                    # Create document key for grouping
                    doc_key = (doc_title, doc.metadata.get("organization"), doc.metadata.get("publication_year"), doc.metadata.get("source_url"))
                    
                    if doc_key not in doc_pages:
                        doc_pages[doc_key] = {}
                    
                    # Only keep the highest similarity for each page
                    if page_num not in doc_pages[doc_key] or similarity > doc_pages[doc_key][page_num]["similarity"]:
                        doc_pages[doc_key][page_num] = {
                            "document_title": doc_title,
                            "similarity": similarity,
                            "chunk_text": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                            "page_number": page_num,
                            "organization": doc.metadata.get("organization"),
                            "publication_year": doc.metadata.get("publication_year"),
                            "source_url": doc.metadata.get("source_url")
                        }
                
                # Create consolidated sources with page ranges (same logic as original)
                consolidated_sources = []
                
                for doc_key, pages_dict in doc_pages.items():
                    # Get sorted list of pages (handle None)
                    pages = list(pages_dict.values())
                    pages_with_nums = [p for p in pages if p["page_number"] is not None]
                    pages_without_nums = [p for p in pages if p["page_number"] is None]
                    
                    # Sort pages with numbers
                    pages_with_nums.sort(key=lambda x: x["page_number"])
                    
                    # Group contiguous pages
                    if pages_with_nums:
                        ranges = []
                        current_range = [pages_with_nums[0]]
                        
                        for page in pages_with_nums[1:]:
                            # Check if contiguous
                            if page["page_number"] == current_range[-1]["page_number"] + 1:
                                current_range.append(page)
                            else:
                                ranges.append(current_range)
                                current_range = [page]
                        
                        # Add final range
                        ranges.append(current_range)
                        
                        # Create consolidated entries
                        for page_range in ranges:
                            if len(page_range) == 1:
                                # Single page
                                consolidated_sources.append(page_range[0])
                            else:
                                # Page range
                                consolidated_source = page_range[0].copy()
                                first_page = page_range[0]["page_number"]
                                last_page = page_range[-1]["page_number"]
                                consolidated_source["page_range"] = f"{first_page}-{last_page}"
                                consolidated_sources.append(consolidated_source)
                            
                            if len(consolidated_sources) >= max_sources:
                                break
                    
                    # Add pages without numbers
                    for page in pages_without_nums:
                        if len(consolidated_sources) >= max_sources:
                            break
                        consolidated_sources.append(page)
                    
                    if len(consolidated_sources) >= max_sources:
                        break
                
                # Sort sources by similarity score (highest first) to ensure most relevant sources appear first
                consolidated_sources.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
                sources = consolidated_sources[:max_sources]
            
            # Get the raw answer
            raw_answer = result.get("output", "I couldn't process your question. Please try rephrasing it." )

            def _extract_final_answer(text: str) -> str:
                if not text:
                    return text
                lowered = text.lower().strip()
                # Only match "final" at the beginning of the response, not in words like "finally"
                if lowered.startswith("final answer:"):
                    return text[len("final answer:"):].lstrip()
                if lowered.startswith("final:"):
                    return text[len("final:"):].lstrip()
                if lowered.startswith("analysis"):
                    return text[len("analysis"):].lstrip()
                return text

            raw_answer = _extract_final_answer(raw_answer)
            
            # Step 4: Validate the response for common issues
            validated_answer = self.validate_response(question, raw_answer, user_data_available)
            
            # If validation failed, try to provide better guidance
            if validated_answer.startswith("ERROR:"):
                # Extract the error message and provide better response
                error_msg = validated_answer[6:]  # Remove "ERROR: "
                
                if "generic advice" in error_msg:
                    # Re-run with more specific instructions for personal data
                    specific_question = f"Answer this question using the user's specific hive data with exact hive names, dates, and measurements: {question}"
                    retry_result = agent_executor.invoke({"input": specific_question})
                    answer = _extract_final_answer(retry_result.get("output", raw_answer))
                elif "no source citations" in error_msg:
                    # Re-run with emphasis on document search
                    factual_question = f"First search documents for authoritative information, then answer: {question}"
                    retry_result = agent_executor.invoke({"input": factual_question})
                    answer = _extract_final_answer(retry_result.get("output", raw_answer))
                else:
                    answer = raw_answer
            else:
                answer = validated_answer
            
            # Clean up the final answer to remove any debug text
            answer = re.sub(r'\(search_[a-zA-Z0-9_]+\)', '', answer)  # Remove (search_beekeeping_documents_xyz)
            answer = re.sub(r'\(get_user_[a-zA-Z0-9_]+\)', '', answer)  # Remove (get_user_hive_data_xyz)
            answer = re.sub(r'\([a-zA-Z0-9_]+_[a-zA-Z0-9_]+\)', '', answer)  # Remove any (tool_name_id) patterns
            answer = re.sub(r'\[search.*?\]', '', answer, flags=re.IGNORECASE)  # Remove [search...] patterns
            answer = re.sub(r'【[^】]*】', '', answer)  # Remove 【search_beekeeping_documents】 patterns with Japanese brackets
            answer = answer.strip()
            
            # Return in the expected format with enhanced metadata
            return {
                "answer": answer,
                "sources": sources,
                "metadata": {
                    "session_id": session_id,
                    "used_agent": True,
                    "user_id": user_id,
                    "intent_classification": intent,
                    "user_data_available": user_data_available,
                    "enhanced_processing": True
                }
            }
            
        except Exception as e:
            # Fallback to document-only search if agent fails
            try:
                fallback_result = self.query(question, session_id)
                fallback_result["metadata"] = {
                    "session_id": session_id,
                    "used_agent": False,
                    "fallback_reason": str(e),
                    "user_id": user_id
                }
                return fallback_result
            except Exception as fallback_error:
                return {
                    "answer": f"I encountered an error processing your question. Please try again. Error: {str(e)}",
                    "sources": [],
                    "metadata": {
                        "session_id": session_id,
                        "error": str(e),
                        "fallback_error": str(fallback_error),
                        "user_id": user_id
                    }
                }
    
    def query(self, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the RAG system with conversation memory.
        
        Args:
            question: The user's question
            session_id: Optional session ID for conversation memory
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        try:
            # Format question with chat history context if available
            contextualized_question = question
            if self.chat_history:
                history_parts = []
                for q, a in self.chat_history[-3:]:  # Last 3 exchanges for better context
                    history_parts.append(f"Q: {q}")
                    # Keep more of the answer for better context, especially for numbered lists
                    if len(a) > 800:
                        history_parts.append(f"A: {a[:800]}...")
                    else:
                        history_parts.append(f"A: {a}")
                    history_parts.append("---")
                
                history_context = "\n".join(history_parts)
                contextualized_question = f"Based on our previous conversation:\n{history_context}\n\nUser's current question: {question}\n\nPlease answer considering the conversation context above."
            
            # Query the retrieval pipeline
            result = self._run_retrieval(contextualized_question)
            
            # Add to chat history (keep last max_history messages)
            self.chat_history.append((question, result["result"]))
            if len(self.chat_history) > self.max_history:
                self.chat_history = self.chat_history[-self.max_history:]
            
            # Format response
            response = {
                "answer": result["result"],
                "sources": [],
                "metadata": {
                    "session_id": session_id,
                    "has_chat_history": len(self.chat_history) > 0
                }
            }
            
            # Add source information with filtering, deduplication, and page range consolidation
            min_similarity = RAG_CONFIG.get('min_similarity_for_display', 0.3)
            max_sources = RAG_CONFIG.get('max_sources_display', 5)
            
            # Collect and deduplicate sources
            doc_pages = {}  # doc_key -> {page_num: source}
            
            for doc in result.get("source_documents", []):
                similarity = doc.metadata.get("similarity", 0.0)
                
                # Skip sources below minimum similarity threshold
                if similarity < min_similarity:
                    continue
                
                doc_title = doc.metadata.get("document_title", "")
                page_num = doc.metadata.get("page_number")
                
                # Create document key for grouping
                doc_key = (doc_title, doc.metadata.get("organization"), doc.metadata.get("publication_year"), doc.metadata.get("source_url"))
                
                if doc_key not in doc_pages:
                    doc_pages[doc_key] = {}
                
                # Only keep the highest similarity for each page
                if page_num not in doc_pages[doc_key] or similarity > doc_pages[doc_key][page_num]["similarity"]:
                    doc_pages[doc_key][page_num] = {
                        "document_title": doc_title,
                        "similarity": similarity,
                        "chunk_text": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        "page_number": page_num,
                        "organization": doc.metadata.get("organization"),
                        "publication_year": doc.metadata.get("publication_year"),
                        "source_url": doc.metadata.get("source_url")
                    }
            
            # Create consolidated sources with page ranges
            consolidated_sources = []
            
            for doc_key, pages_dict in doc_pages.items():
                # Get sorted list of pages (handle None)
                pages = list(pages_dict.values())
                pages_with_nums = [p for p in pages if p["page_number"] is not None]
                pages_without_nums = [p for p in pages if p["page_number"] is None]
                
                # Sort pages with numbers
                pages_with_nums.sort(key=lambda x: x["page_number"])
                
                # Group contiguous pages
                if pages_with_nums:
                    ranges = []
                    current_range = [pages_with_nums[0]]
                    
                    for page in pages_with_nums[1:]:
                        # Check if contiguous
                        if page["page_number"] == current_range[-1]["page_number"] + 1:
                            current_range.append(page)
                        else:
                            ranges.append(current_range)
                            current_range = [page]
                    
                    # Add final range
                    ranges.append(current_range)
                    
                    # Create consolidated entries
                    for page_range in ranges:
                        if len(page_range) == 1:
                            # Single page
                            consolidated_sources.append(page_range[0])
                        else:
                            # Page range
                            consolidated_source = page_range[0].copy()
                            first_page = page_range[0]["page_number"]
                            last_page = page_range[-1]["page_number"]
                            consolidated_source["page_range"] = f"{first_page}-{last_page}"
                            consolidated_sources.append(consolidated_source)
                        
                        if len(consolidated_sources) >= max_sources:
                            break
                
                # Add pages without numbers
                for page in pages_without_nums:
                    if len(consolidated_sources) >= max_sources:
                        break
                    consolidated_sources.append(page)
                
                if len(consolidated_sources) >= max_sources:
                    break
            
            response["sources"] = consolidated_sources[:max_sources]
            
            return response
            
        except Exception as e:
            print(f"Error during RAG query: {e}")
            return {
                "answer": "I apologize, but I encountered an error while processing your question. Please try again.",
                "sources": [],
                "metadata": {"error": str(e)}
            }
    
    def clear_memory(self) -> None:
        """Clear the conversation memory."""
        self.chat_history = []
    
    def get_chat_history(self) -> List[Dict[str, str]]:
        """Get the current chat history."""
        messages = []
        for question, answer in self.chat_history:
            messages.append({"type": "human", "content": question})
            messages.append({"type": "ai", "content": answer})
        return messages


# Global instance
_langchain_service = None

def get_langchain_service() -> LangChainRAGService:
    """Get the global LangChain RAG service instance."""
    global _langchain_service
    if _langchain_service is None:
        _langchain_service = LangChainRAGService()
    return _langchain_service