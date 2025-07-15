import os
import json
import re
import streamlit as st
import pandas as pd
import datetime
from collections import Counter, defaultdict
import random
import requests
from firebase_admin import firestore
from io import StringIO

# --- Constantes ---
GITHUB_USER = "ricmarquesart"
GITHUB_REPO = "Quiz"
BRANCH = "main"
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/data/"

CARTOES_FILE_BASE = 'cartoes_validacao.txt'
GPT_FILE_BASE = 'Dados_Manual_output_GPT.txt'
CLOZE_FILE_BASE = 'Dados_Manual_Cloze_text.txt'
SENTENCE_WORDS_FILE = 'palavras_unicas_por_tipo.txt'
TIPOS_EXERCICIO_ANKI = {
    "MCQ Significado": "gerar_mcq_significado", "MCQ Tradução Inglês": "gerar_mcq_traducao_ingles",
    "MCQ Sinônimo": "gerar_mcq_sinonimo", "Fill": "gerar_fill_gap", "Reading": "gerar_reading_comprehension"
}

# --- Funções de Interação com Firestore ---
def get_firestore_db():
    return firestore.client()

def get_user_doc_ref(language):
    if 'user_info' not in st.session_state or not st.session_state.get('logged_in'):
        return None
    uid = st.session_state['user_info']['uid']
    collection_name = f'user_progress_{language}'
    return get_firestore_db().collection(collection_name).document(uid)

def get_user_data(language):
    doc_ref = get_user_doc_ref(language)
    if doc_ref:
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
    return {'vocab_database': [], 'historico': {}, 'writing_log': [], 'sentence_log': []}

def save_user_data(data_dict, language):
    doc_ref = get_user_doc_ref(language)
    if doc_ref:
        doc_ref.set(data_dict)

# --- Funções "Wrapper" de Dados ---
def get_vocab_db_list(language):
    return get_user_data(language).get('vocab_database', [])

def save_vocab_db_list(db_list, language):
    full_data = get_user_data(language)
    full_data['vocab_database'] = db_list
    save_user_data(full_data, language)

def get_history(language):
    return get_user_data(language).get('historico', {})

def save_history(historico, language):
    full_data = get_user_data(language)
    full_data['historico'] = historico
    save_user_data(full_data, language)

def clear_history(language):
    full_data = get_user_data(language)
    full_data['historico'] = {}
    save_user_data(full_data, language)
    st.success("Histórico de quizzes limpo com sucesso!")

def update_progress_from_quiz(quiz_results, language):
    db_df = get_session_db(language)
    if db_df.empty: return
    for result in quiz_results:
        palavra = result['palavra']
        idx_list = db_df.index[db_df['palavra'] == palavra].tolist()
        if not idx_list: continue
        idx = idx_list[0]
        progresso = db_df.loc[idx, 'progresso']
        if isinstance(progresso, dict):
            progresso[result['tipo_exercicio']] = 'acerto' if result['acertou'] else 'erro'
            db_df.at[idx, 'progresso'] = progresso
    save_vocab_db(db_df, language)
    st.session_state.pop(f"db_df_{language}", None)

# --- Carregamento de Arquivos e Sincronização ---
@st.cache_data
def carregar_arquivos_base(language):
    # A sua lógica de carregamento de ficheiros aqui...
    return [], []

def sync_database(language):
    flashcards, gpt_exercicios = carregar_arquivos_base(language)
    db_list = get_vocab_db_list(language)
    db_dict = {item['palavra']: item for item in db_list}
    all_source_words = {f.get('palavra') for f in flashcards if f.get('palavra')} | \
                       {g.get('palavra') for g in gpt_exercicios if g.get('palavra')}

    for palavra in all_source_words:
        if palavra not in db_dict:
            db_dict[palavra] = {
                'palavra': palavra, 'ativo': True, 'fonte': [], 'progresso': {},
                'contagem_maestria': 0, 'data_adicao': datetime.datetime.now().strftime("%Y-%m-%d"),
                'escrita_completa': False, 'cefr': 'N/A'
            }
    updated_list = list(db_dict.values())
    if updated_list:
        save_vocab_db_list(updated_list, language)
    
    expected_columns = ['palavra', 'ativo', 'fonte', 'progresso', 'contagem_maestria', 'data_adicao', 'escrita_completa', 'cefr']
    if not updated_list and not db_list:
        return pd.DataFrame(columns=expected_columns)
    
    df = pd.DataFrame(updated_list if updated_list else db_list)
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None
    return df

def get_session_db(language):
    session_key = f"db_df_{language}"
    expected_columns = ['palavra', 'ativo', 'fonte', 'progresso', 'contagem_maestria', 'data_adicao', 'escrita_completa', 'cefr']
    if 'user_info' not in st.session_state:
        return pd.DataFrame(columns=expected_columns)
    if session_key not in st.session_state:
        st.session_state[session_key] = sync_database(language)
    return st.session_state[session_key]

def save_vocab_db(df, language):
    db_list = df.where(pd.notnull(df), None).to_dict('records')
    save_vocab_db_list(db_list, language)
    st.session_state[f"db_df_{language}"] = df
    
def get_performance_summary(language):
    db_df = get_session_db(language)
    historico = get_history(language)
    summary = {
        'db_kpis': {'total': 0, 'ativas': 0, 'inativas': 0},
        'kpis': {'precisao': 'N/A', 'sessoes': 0}
    }
    if not db_df.empty and 'ativo' in db_df.columns:
        summary['db_kpis']['total'] = len(db_df)
        summary['db_kpis']['ativas'] = int(db_df['ativo'].sum())
        summary['db_kpis']['inativas'] = summary['db_kpis']['total'] - summary['db_kpis']['ativas']
    if historico:
        # Lógica para calcular precisão e sessões
        pass
    return summary