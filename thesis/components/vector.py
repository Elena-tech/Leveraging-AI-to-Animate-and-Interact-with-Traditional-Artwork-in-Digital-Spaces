from pinecone import Pinecone, ServerlessSpec, PodSpec
from sentence_transformers import SentenceTransformer
from flask import current_app
from utils import sanitize_string


class VectorDB:
    def __init__(self):
        # Load configuration from environment variable
        index_name=current_app.config['VECTOR_INDEX_NAME']
        embedding_model=current_app.config['VECTOR_EMBEDDING_MODEL']
        pinecone_api_key = current_app.config['PINECONE_API_KEY']

        if not pinecone_api_key:
            raise ValueError("Pinecone API key must be set in the PINECONE_API_KEY environment variable.")
        if current_app.config['USE_SERVERLESS']:
            spec = ServerlessSpec(cloud='aws', region='us-west-2')
        else:
            # if using a starter index, you should specify a pod_type too
            spec = PodSpec()
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index_name = index_name
        
        # Check if the index exists, create it if it doesn't
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=384,  # dimension for all-MiniLM-L6-v2
                metric='cosine',
                spec=spec
            )
        
        self.index = self.pc.Index(self.index_name)

        # Initialize the embedding model
        self.embedding_model = SentenceTransformer(embedding_model)

    def get_embedding(self, text):
        return self.embedding_model.encode(text).tolist()

    def store_artwork(self, long_summary, image_reference, artwork_name, artist):
        embedding = self.get_embedding(long_summary)
        
        metadata = {
            "long_summary": long_summary,
            "image_reference": image_reference,
            "artwork_name": artwork_name,
            "artist": artist
        }
        
        unique_id = sanitize_string(f"{artist}_{artwork_name}".replace(" ", "_").lower())
        
        self.index.upsert(vectors=[(unique_id, embedding, metadata)])

    def rag_query(self, query, top_k=3):
        query_embedding = self.get_embedding(query)
        
        results = self.index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
        
        context = [item['metadata']['long_summary'] for item in results['matches']]
        
        return context