from llama_cpp import Llama
import logging

logger = logging.getLogger(__name__)
import asyncio
from src.config import MODEL_N_CTX
import time

class AnswerGenerator:
    """
    Generates answers using LLM.
    """

    _instance = None
    _initialized = False

    def __init__(
        self,
        model_path: str,
        prompt_template: str | None = None,
        n_ctx: int = 2048,
        n_threads: int = 8,
        n_gpu_layers: int = 0,
        temperature: float = 0.1,
        n_batch:int=64,
        verbose:bool=False,
        max_token:int=200,
        repeat_penalty:int = 1.3
    ) -> None:
        """
        Initialize AnswerGenerator with llama.cpp model.
        
        Args:
            model_path: Path to the GGUF model file
            prompt_template: Custom prompt template (optional)
            n_ctx: Context window size
            n_threads: Number of CPU threads
            n_gpu_layers: Number of layers to offload to GPU [0 for only cpu (-1 for all gpu layers)]
            temperature: Default temperature for generation
            n_batch: ....
            verbose:...
            max_token:...
            repeat_penalty:...

        """
        self.model_path = model_path
        self.default_temperature = temperature
        self.max_tokens=max_token
        # llama.cpp model
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_batch=n_batch,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose
        )
        
        self.prompt_template = prompt_template or self.crear_prompt_llama()

    def crear_prompt_llama(self):
        """Create prompt for Llama 3.1 format."""
        
        system_message = """Eres un asistente técnico especializado en tecnología (móviles, PCs, electrónica).
    REGLAS ESTRICTAS:
    1. Responde SOLO con información del contexto proporcionado
    2. NO inventes datos ni uses conocimiento externo
    3. Responde SIEMPRE en español
    FORMATO DE RESPUESTA (selecciona el apropiado según la pregunta):

    SI ES RANKING O "MEJOR":
    1. [Producto] - [razón principal]
    2. [Producto] - [razón principal]
    3. [Producto] - [razón principal]
    SI ES DESCRIPCIÓN SIMPLE:
    - [Característica]: [valor]
    - [Característica]: [valor]
    SI EL CONTEXTO NO CONTIENE LA INFORMACIÓN:
    "No encuentro información en el contexto proporcionado sobre [tema]."""

        user_message = """CONTEXTO:
    {contexto}

    PREGUNTA DEL USUARIO:
    {pregunta}"""

        prompt = f"""<|start_header_id|>system<|end_header_id|>

    {system_message}<|eot_id|>
    <|start_header_id|>user<|end_header_id|>

    {user_message}<|eot_id|>
    <|start_header_id|>assistant<|end_header_id|>

    """
        
        return prompt

    def __new__(cls, model_path=None, prompt_template=None, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def _invoke_llm(self, prompt: str, temperature: float = None) -> str:
        """Internal method to invoke llama.cpp model."""
        temp = temperature if temperature is not None else self.default_temperature
        t= time.time()
        print(prompt)
        response = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=temp,
            repeat_penalty=1.3,
            stop=["<|eot_id|>", "<|end_of_text|>"]
        )
        print(time.time()-t,"segundos")
        return response["choices"][0]["message"]["content"]
    
    async def generate(self, context: str, question: str, temperature: float | None = None) -> str:
        """Generate answer with context."""
        logger.info(f"Geerando respuetsa....")
        
        
        print(f"Tamaño del prompt template: {len(self.prompt_template)} chars")
        
        # Check token counts
        token_count = await self.get_token_count(context)
        token_prompt = await self.get_token_count(self.prompt_template)
        token_question = await self.get_token_count(question)
        logger.info(f"tokens en el  prompt {token_prompt}")
        logger.info(f"tokens en la pregunta {token_question}")

        if token_count > MODEL_N_CTX - token_prompt - token_question:
            logger.warning(f"Contexto muy largo: {token_count+token_prompt+token_question} tokens (limit: {MODEL_N_CTX})")
            
            limite_tokens = MODEL_N_CTX - token_prompt - token_question
            
            # Truncate context..
            raw_tokens = self.llm.tokenize(context.encode("utf-8"))
            truncated_tokens = raw_tokens[:limite_tokens]
            logger.info(f"Contexto trucado de {len(raw_tokens)} a {len(truncated_tokens)} tokens")
            context = self.llm.detokenize(truncated_tokens).decode("utf-8")
            
        formatted_prompt = self.prompt_template.format(contexto=context,pregunta=question)
        print(f"Tamaño del Context: {len(context)} chars")
  
        return await asyncio.to_thread(self._invoke_llm, formatted_prompt, temperature)
        
    async def get_token_count(self, text: str) -> int:
        """Get token count for text using llama.cpp tokenizer."""
        try:
            tokens = await asyncio.to_thread(self.llm.tokenize, text.encode("utf-8"))
            return len(tokens)
        except Exception as e:
            logger.warning(f"Could not get token count, using estimation: {e}")
            return max(1, len(text) // 4)
    
    def __str__(self) -> str:
        return f"AnswerGenerator(model={self.model_path})"