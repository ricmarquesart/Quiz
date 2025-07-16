import os
import sys
import requests
import json
import pandas as pd

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.firebase_manager import initialize_firebase

def upload_data_from_github():
    """
    Downloads data files from a public GitHub repository and uploads them to Firestore.
    """
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Aborting.")
        return

    # Base URL for the raw content of the GitHub repository
    base_url = "https://raw.githubusercontent.com/ricmarquesart/Quiz/main/data/"

    files_to_process = {
        "cartoes_validacao.txt": "cartoes_validacao",
        "Dados_Manual_output_GPT.txt": "Dados_Manual_output_GPT",
        "Dados_Manual_Cloze_text.txt": "Dados_Manual_Cloze_text",
        "palavras_unicas_por_tipo.txt": "palavras_unicas_por_tipo"
    }

    for filename, collection_name in files_to_process.items():
        url = base_url + filename
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            print(f"Successfully downloaded {filename}")

            # Clear existing data in the collection
            delete_collection(db, collection_name, batch_size=100)
            print(f"Cleared existing data in collection '{collection_name}'.")

            # Process and upload new data
            if filename == "palavras_unicas_por_tipo.txt":
                # Special handling for the CSV-like file
                df = pd.read_csv(io.StringIO(response.text), sep=';')
                records = df.to_dict('records')
                for record in records:
                    db.collection(collection_name).add(record)
            else:
                # Handling for other text files (assuming one JSON object per line)
                for line in response.text.strip().split('\n'):
                    if line:
                        try:
                            data = json.loads(line)
                            db.collection(collection_name).add(data)
                        except json.JSONDecodeError:
                            print(f"Warning: Could not decode JSON from line in {filename}: {line}")
            
            print(f"Successfully uploaded data to collection '{collection_name}'.")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading {filename}: {e}")
        except Exception as e:
            print(f"An error occurred while processing {filename}: {e}")

def delete_collection(coll_ref, batch_size):
    """
    Deletes a collection from Firestore in batches.
    """
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size)

if __name__ == "__main__":
    # This script is now configured to use the firebase_credentials.json file
    # in the root of the project.
    import os
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "G:\\My Drive\\Anki_2.0\\GitHub\\Quiz\\firebase_credentials.json"
    initialize_firebase()
    
    print("Starting data upload to Firestore...")
    upload_data_from_github()
    print("Data upload finished.")
