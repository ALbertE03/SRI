import os
from pathlib import Path
from typing import Optional


from src.config import DEFAULT_MODEL_FILE, MODELS_DIR,DEFAULT_MODEL_FILE
from src.errors.llm_errors import LLMModelNotFoundError
from src.utils.logger import get_logger

logger = get_logger("ModelDownloader")

DEFAULT_HF_REPO = "lm-kit/llama-3.1-8b-instruct-gguf"


class ModelDownloader:
    """Download LLM models from HuggingFace or other sources."""

    @staticmethod
    def download_default_model(force: bool = False) -> Path:
        """Download the default TinyLlama model if not already present."""
        model_path = MODELS_DIR / DEFAULT_MODEL_FILE

        if model_path.exists() and not force:
            logger.info(f"Model already exists: {model_path}")
            return model_path

        return ModelDownloader.download_from_huggingface(DEFAULT_HF_REPO, force=force)

    @staticmethod
    def download_from_huggingface(repo_id: str, force: bool = False) -> Path:
        """
        Download a GGUF model from HuggingFace.
        
        Parameters
        ----------
        repo_id : str
            HuggingFace repo ID (e.g., "google/gemma-2b-it" or "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF")
        force : bool
            Force re-download
            
        Returns
        -------
        Path
            Path to the downloaded model file
        """
        from huggingface_hub import hf_hub_download, list_repo_files
        from tqdm import tqdm  
        

        safe_name = repo_id.replace("/", "_")
        model_path = MODELS_DIR / f"{safe_name}.gguf"
        
        if model_path.exists() and not force:
            logger.info(f"Model already exists: {model_path}")
            return model_path
        
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            files = list(list_repo_files(repo_id))
            gguf_file = None
            for f in files:
                if f.lower().endswith('.gguf'):
                    gguf_file = f
                    break
            
            if not gguf_file:
                raise LLMModelNotFoundError(f"No GGUF file found in {repo_id}")
            
            gguf_file = DEFAULT_MODEL_FILE if DEFAULT_MODEL_FILE else gguf_file
     
            logger.info(f"Downloading  {gguf_file} from HuggingFace...")
       
            temp_path = hf_hub_download(repo_id, gguf_file)
            
            logger.info(f"Saving model to final destination...")
            file_size = os.path.getsize(temp_path)
            
            with open(temp_path, 'rb') as fsrc:
                with open(model_path, 'wb') as fdst:
                    with tqdm(total=file_size, unit='B', unit_scale=True, desc="Copying file") as pbar:
                        while True:
                      
                            buf = fsrc.read(1024 * 1024)
                            if not buf:
                                break
                            fdst.write(buf)
                            pbar.update(len(buf))
            
            logger.info(f"Model downloaded and saved: {model_path}")
            return model_path
            
        except Exception as exc:
            raise LLMModelNotFoundError(
                f"Failed to download model from {repo_id}: {exc}"
            ) from exc

    @staticmethod
    def ensure_model_exists(model_path: Optional[str] = None) -> Path:
        """
        Ensure a model file exists, downloading from HuggingFace if needed.

        Parameters
        ----------
        model_path : Optional[str]
            Custom model path. Can be:
            - Full path to local file
            - HuggingFace repo ID (e.g., "google/gemma-2b-it")
            - None to use default

        Returns
        -------
        Path
            Path to the model file.
        """
        if not model_path:
            return ModelDownloader.download_default_model()
        
        try:
            path = Path(model_path)
            if path.exists():
                return path
            
            if "/" in model_path and not model_path.startswith("/"):
                try:
                    logger.info("Downloading model from HuggingFace repo: %s", model_path)
                    return ModelDownloader.download_from_huggingface(model_path)
                except Exception as e:
                    logger.warning(f"Failed to download {model_path}: {e}")
            return ModelDownloader.download_default_model()
        except Exception as exc:
            logger.error(f"Error ensuring model exists: {exc}")
            return ModelDownloader.download_default_model()