
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import json

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using credentials from Streamlit's secrets.
    Returns the Firestore client.
    """
    if not firebase_admin._apps:
        # Get the credentials from Streamlit secrets
        firebase_creds_json = st.secrets.get("firebase_credentials")

        if not firebase_creds_json:
            st.error("Firebase credentials not found in Streamlit secrets.")
            return None

        try:
            # The secret is stored as a string, so we need to parse it as JSON
            creds_dict = json.loads(firebase_creds_json)
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Failed to initialize Firebase: {e}")
            return None

    return firestore.client()

def get_firestore_db():
    """
    Returns an instance of the Firestore database client.
    Initializes Firebase if it hasn't been initialized yet.
    """
    return initialize_firebase()

def get_collection_data(collection_name):
    """
    Fetches all documents from a specified Firestore collection.
    Returns a list of dictionaries, where each dictionary represents a document.
    """
    db = get_firestore_db()
    if not db:
        return []
    try:
        collection_ref = db.collection(collection_name)
        docs = collection_ref.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"Failed to fetch data from collection {collection_name}: {e}")
        return []

