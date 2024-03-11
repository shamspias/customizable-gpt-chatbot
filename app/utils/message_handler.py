import httpx
import logging
from urllib.parse import urlparse
from operator import itemgetter
from langchain.schema import format_document
from langchain_pinecone import Pinecone
from langchain_openai import ChatOpenAI
from langchain_core.messages import get_buffer_string
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_groq.chat_models import ChatGroq
from langchain_community.chat_models import ChatFireworks
from langchain_community.chat_models import GigaChat
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import ConfigurableField, RunnablePassthrough, RunnableParallel, RunnableLambda
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory

from app.config import settings

logger = logging.getLogger(__name__)


class LangChainService:
    def __init__(self, session_id):
        if settings.PROXY_URLS:
            parsed_url = urlparse(settings.PROXY_URLS)
            if parsed_url.scheme and parsed_url.netloc:
                self.http_client = httpx.Client(proxies=settings.PROXY_URLS)
                self.http_async_client = httpx.AsyncClient(proxies=settings.PROXY_URLS)
            else:
                logger.warn("Invalid proxy URL provided. Proceeding without proxy.")
                self.http_client = None
                self.http_async_client = None
        else:
            self.http_client = None
            self.http_async_client = None

        self.embeddings = OpenAIEmbeddings(http_client=self.http_client,
                                           model=settings.OPENAI_EMBEDDED_MODEL,
                                           openai_api_key=settings.OPENAI_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.vectorstore = Pinecone.from_existing_index(
            embedding=self.embeddings,
            index_name=self.index_name,
            namespace=settings.PINECONE_NAMESPACE
        )
        self.retriever = self.vectorstore.as_retriever()

        self.message_history = RedisChatMessageHistory(url=settings.REDIS_CONVERSATION_MEMORY_URL, ttl=600,
                                                       session_id=session_id)

        self.memory = ConversationBufferWindowMemory(
            return_messages=True,
            output_key="answer",
            input_key="question",
            chat_memory=self.message_history,
            max_token_limit=4000
        )
        self.loaded_memory = RunnablePassthrough.assign(
            chat_history=RunnableLambda(self.memory.load_memory_variables) | itemgetter("history"),
        )

        self.default_document_prompt = PromptTemplate.from_template(template="{page_content}")

        self._template = """Given the following conversation and a follow up question, rephrase the follow up 
        question to be a standalone question, in its original language and change country name based on the country.

Chat History:
{chat_history}
Follow Up Input: {question}
Country: {country}
Standalone question:"""

        self.condense_question_prompt = PromptTemplate.from_template(self._template)

        self.template = settings.LLM_INSTRUCTION_PROMPT + """\nIf Context have any info then, Answer the question 
        based only on the following context: {context}

        Question: {question}
        """
        self.prompt = ChatPromptTemplate.from_template(self.template)
        self.model = self.setup_model()
        self.input_model = self.setup_model(optional=True)
        self.output_parser = StrOutputParser()

        self.retrieved_documents = self.get_retrieved_documents()

        self.standalone_question = RunnableParallel(
            standalone_question=RunnablePassthrough.assign(
                chat_history=lambda x: get_buffer_string(x["chat_history"]),
                country=lambda x: x["country"]
            ) | self.condense_question_prompt | self.input_model | self.output_parser,
        )

        self.final_chain = (
                self.loaded_memory
                | self.standalone_question
                | self.retrieved_documents
                | self.prompt
                | self.model
        )

    def _combine_documents(self, docs, document_separator="\n\n"):
        doc_strings = [format_document(doc, self.default_document_prompt) for doc in docs]
        return document_separator.join(doc_strings)

    def get_retrieved_documents(self):
        return {
            "context": itemgetter("standalone_question") | self.retriever | self._combine_documents,
            "question": lambda x: x["standalone_question"],
        }
        # return {
        #     "context": lambda x: "" if "none" in x["standalone_question"][:6].lower() else itemgetter(
        #         "standalone_question") | self.retriever | self._combine_documents,
        #     "question": lambda x: x["standalone_question"] if not (
        #             "none" in x["standalone_question"][:6].lower()) else x["standalone_question"][6:],
        # }

    def setup_model(self, optional: bool = False):
        groq_models = ChatGroq(model_name=settings.GROQ_MODEL,
                               http_client=self.http_async_client,
                               groq_api_key=settings.GROQ_API_KEY
                               )
        google_gemini = ChatGoogleGenerativeAI(model=settings.GOOGLE_MODEL,
                                               http_client=self.http_async_client,
                                               google_api_key=settings.GOOGLE_API_KEY
                                               )
        giga_chat = GigaChat(credentials=settings.GIGACHAT_API_KEY, verify_ssl_certs=False)
        chat_openai = ChatOpenAI(model=settings.OPENAI_MODEL_1,
                                 http_client=self.http_async_client,
                                 openai_api_key=settings.OPENAI_API_KEY
                                 )
        chat_openai_fallback = ChatOpenAI(model=settings.OPENAI_MODEL_2,
                                          http_client=self.http_async_client,
                                          openai_api_key=settings.OPENAI_API_KEY
                                          )
        mistral = ChatFireworks(model=settings.FIREWORK_MODEL, fireworks_api_key=settings.FIREWORKS_API_KEY)

        if optional:
            model = (
                chat_openai_fallback
                .with_fallbacks([mistral, groq_models, giga_chat])
                .configurable_alternatives(
                    ConfigurableField(id="model"),
                    default_key="chat_openai_fallback",
                    mistral=mistral,
                    giga_chat=giga_chat,
                    groq_models=groq_models
                )
            )
        else:
            model = (
                chat_openai
                .with_fallbacks([groq_models, chat_openai_fallback, mistral, giga_chat])
                .configurable_alternatives(
                    ConfigurableField(id="model"),
                    default_key="chat_openai",
                    chat_openai=chat_openai,
                    mistral=mistral,
                    giga_chat=giga_chat,
                    groq_models=groq_models
                )
            )
        return model

    async def get_response(self, question, country):
        inputs = {
            "question": question,
            "country": country,
        }
        content = ""
        async for chunk in self.final_chain.astream(inputs):
            yield chunk.content
            content += chunk.content

        self.memory.save_context({"question": question}, {"answer": content})
