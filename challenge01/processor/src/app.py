import json
import os
import unicodedata          # Libreria para normalizar texto y eliminar caracteres no ASCII
from pathlib import Path
from typing import List, Dict, Any

from elasticsearch import Elasticsearch
from sentence_splitter import SentenceSplitter              # Libreria para dividir texto en oraciones
from sentence_transformers import SentenceTransformer       # Libreria para generar embeddings

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
INPUT_DIR = os.getenv("INPUT_DIR", "/app/input")
INDEX_NAME = os.getenv("INDEX_NAME", "documents")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Simple sentence embeddings model
model = SentenceTransformer(EMBEDDING_MODEL)

# Sentence Splitter
splitter = SentenceSplitter(language="en")  # Objeto que parte el texto en oraciones


def create_index(es: Elasticsearch, index_name: str) -> None:
    # Create the index if it does not exist.
    if es.indices.exists(index=index_name):
        return

    mapping = {     # "esquema" del indice, define los campos y sus tipos para los documentos que se indexaran
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                # TODO: Complete the mapping with the required fields and types.
                "title": {"type": "text"},
                "description": {"type": "text"},
                "authors": {"type": "keyword"},
                "first_published": {"type": "integer"},
                "subjects": {"type": "keyword"},
                "language": {"type": "keyword"},
                "openlibrary_url": {"type": "keyword"},

                "embedding": {
                    "type": "dense_vector",
                    "dims": 384 # Adjust the dimensions where required.
                }
            }
        }
    }

    es.indices.create(index=index_name, body=mapping)
    print(f"Created index: {index_name}")


def load_json_files(input_dir: str) -> List[Dict[str, Any]]:
    documents = []
    for path in Path(input_dir).glob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            documents.append(json.load(f))
    return documents


def split_into_chunks(text: str, max_sentences: int = 5) -> List[str]:
    # Split the text into small chunks.
    # Chunks de hasta 5 oraciones.
    sentences = splitter.split(text)
    chunks = []

    for i in range(0, len(sentences), max_sentences):
        chunk = " ".join(sentences[i:i + max_sentences]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def generate_embedding(text: str) -> List[float]:
    # TODO: Create the required code to generate text embeddings.
    embedding = model.encode(text).tolist()  # Genera el embedding y lo convierte a lista para ser compatible con Elasticsearch
    return embedding


def clean_non_ascii(text: str) -> str:

    replacements = {    # Reemplazos comunes de caracteres no ASCII por sus equivalentes ASCII (para no perder sentido)
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "—": "-",
        "–": "-",
        "…": "...",
        "\u00a0": " ",   # non-breaking space
    }

    for non_ascii, ascii_char in replacements.items():
        text = text.replace(non_ascii, ascii_char)

    # Remove non-ASCII characters from the text.
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text.strip()

def proccess_documents(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    # TODO: Complete the required code to process each document:
    # Split the document into chunks
    # Generate an embedding for each chunk
    # Add the embeddings to a new document along with the remaining fields
    # Filter and replace non-ASCII characters
    # Ensure that subjects are capitalized


    doc_id = document.get("id")
    title = document.get("title", "")
    description = document.get("description", "")
    authors = document.get("authors", [])
    first_published = document.get("first_published", "")
    subjects = document.get("subjects", [])
    language = document.get("language", "")
    openlibrary_url = document.get("openlibrary_url", "")

    if not doc_id or not description:
        raise ValueError("Document must contain at least 'id' and 'description'")

    chunks = split_into_chunks(description)
    result = []

    for idx, chunk in enumerate(chunks):
        clean_chunk = clean_non_ascii(chunk)  # Limpiar el texto del chunk para eliminar caracteres no ASCII
        embedding = generate_embedding(clean_chunk)  # Generar el embedding para el chunk limpio
        result.append({
            "doc_id": str(doc_id),
            "chunk_id": f"{doc_id}-{idx}",
            "title": title,
            "description": chunk,
            "authors": authors,
            "first_published": first_published,
            "subjects": [subject.capitalize() for subject in subjects],  # Capitalize subjects
            "language": language,
            "openlibrary_url": openlibrary_url,
            "embedding": embedding
        })

    return result


def index_documents(es: Elasticsearch, index_name: str, docs: List[Dict[str, Any]]) -> None:
    # TODO: Index documents into Elasticsearch
    return


def semantic_search(es: Elasticsearch, index_name: str, query_text: str, k: int = 3) -> Dict[str, Any]:
    # Query to perform semantic search
    query_vector = generate_embedding(query_text)

    body = {
        "knn": {
            "field": "embedding",   # Campo donde va a buscar el vector de consulta
            "query_vector": query_vector,
            "k": k,                 # Numero de resultados a devolver
            "num_candidates": 10    # Canttidad de cantidadtos a revisar antes de elegir los mejores resultados
        },
        "_source": ["doc_id", "chunk_id", "title", "description"]  # Campos que queremos que se devuelvan en los resultados
    }

    return es.search(index=index_name, body=body)


def main() -> None:
    es = Elasticsearch(ELASTICSEARCH_URL)
    create_index(es, INDEX_NAME)
    documents = load_json_files(INPUT_DIR)

    if not documents:
        print("No JSON files found.")
        return

    for document in documents:
        built_docs = proccess_documents(document)
        index_documents(es, INDEX_NAME, built_docs)

    print("Semantic search: examples")

    # TODO: Create several semantic search queries and print the results.
    # Use the function semantic_search()


if __name__ == "__main__":
    main()