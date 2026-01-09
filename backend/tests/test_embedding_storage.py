import os
from openai import OpenAI
import psycopg2
from urllib.parse import urlparse
import json

def test_embedding_storage():
    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set.")

    result = urlparse(database_url)
    db_name = result.path[1:]
    db_user = result.username
    db_password = result.password
    db_host = result.hostname
    db_port = result.port

    # Connect to the database
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cursor = conn.cursor()

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    model = "text-embedding-3-small"

    # Generate a sample embedding
    sample_text = "This is a test chunk."
    response = openai_client.embeddings.create(input=sample_text, model=model)
    embedding = response.data[0].embedding  # Access the embedding correctly

    # Serialize the embedding as JSON before storing
    embedding_json = json.dumps(embedding)

    # Insert the embedding into the database
    insert_query = """
    INSERT INTO document_chunks (chunk_text, embedding_vector, metadata)
    VALUES (%s, %s, %s)
    RETURNING id;
    """
    cursor.execute(insert_query, (sample_text, embedding_json, '{}'))  # Provide an empty JSON object for metadata
    inserted_id = cursor.fetchone()[0]
    conn.commit()

    # Verify the embedding was stored
    select_query = """
    SELECT embedding_vector FROM document_chunks WHERE id = %s;
    """
    cursor.execute(select_query, (inserted_id,))
    # Deserialize the embedding after retrieving
    stored_embedding_json = cursor.fetchone()[0]
    stored_embedding = json.loads(stored_embedding_json)

    # Close the connection
    cursor.close()
    conn.close()

    # Log the inserted and retrieved embeddings for debugging
    print("Inserted embedding:", embedding)
    print("Retrieved embedding:", stored_embedding)

    # Log the lengths of the embeddings
    print("Length of inserted embedding:", len(embedding))
    print("Length of retrieved embedding:", len(stored_embedding))

    # Compare embeddings with a tolerance
    tolerance = 1e-5
    differences = [abs(a - b) for a, b in zip(embedding, stored_embedding)]
    max_difference = max(differences)
    print("Max difference between embeddings:", max_difference)
    assert max_difference < tolerance, "Embedding was not stored correctly!"

if __name__ == "__main__":
    test_embedding_storage()
    print("Test passed: Embedding stored and retrieved successfully.")
