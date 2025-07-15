import os
import json
import re
import streamlit as st
import pandas as pd
import datetime
from collections import Counter, defaultdict
import random
import requests # Usado para baixar os arquivos do GitHub
from firebase_admin import firestore

# --- Constantes com a nova estrutura do GitHub (CORRIGIDO) ---
GITHUB_USER = "ricmarquesart" # CORRIGIDO
GITHUB_REPO = "Quiz"
BRANCH = "main" # Geralmente 'main' ou 'master'

# URL base para acessar os arquivos "crus" (raw) na sua pasta 'data'
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/data/"

CARTOES_FILE_BASE = 'cartoes_validacao.txt'
GPT_FILE_BASE = 'Dados_Manual_output_GPT.txt'
CLOZE_FILE_BASE = 'Dados_Manual_Cloze_text.txt'
SENTENCE_WORDS_FILE = 'palavras_unicas_por_tipo.txt'
TIPOS_EXERCICIO_ANKI = {
    "MCQ Significado": "gerar_mcq_significado", "MCQ Tradução Inglês": "gerar_mcq_traducao_ingles",
    "MCQ Sinônimo": "gerar_mcq_sinonimo", "Fill": "gerar_fill_gap", "Reading": "gerar_reading_comprehension"
}

# --- Interação com Firestore (Permanece igual) ---
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
    return {
        'vocab_database': [],
        'historico': {},
        'writing_log': [],
        'sentence_log': []
    }

def save_user_data(data_dict, language):
    doc_ref = get_user_doc_ref(language)
    if doc_ref:
        doc_ref.set(data_dict)

# --- Funções "Wrapper" de Dados (Completas e Restauradas) ---
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

def get_writing_log(language):
    return get_user_data(language).get('writing_log', [])

def add_writing_entry(entry, language):
    full_data = get_user_data(language)
    writing_log = full_data.get('writing_log', [])
    writing_log = [e for e in writing_log if e['palavra'] != entry['palavra']]
    writing_log.append(entry)
    full_data['writing_log'] = writing_log
    for word_data in full_data['vocab_database']:
        if word_data['palavra'] == entry['palavra']:
            word_data['escrita_completa'] = True
            break
    save_user_data(full_data, language)
    st.session_state.pop(f"db_df_{language}", None)

def delete_writing_entries(entries_to_delete, language):
    full_data = get_user_data(language)
    entries_to_delete_set = set((d['palavra'], d['texto']) for d in entries_to_delete)
    current_log = full_data.get('writing_log', [])
    new_log = [entry for entry in current_log if (entry['palavra'], entry['texto']) not in entries_to_delete_set]
    full_data['writing_log'] = new_log
    words_deleted = {entry['palavra'] for entry in entries_to_delete}
    for word_data in full_data.get('vocab_database', []):
        if word_data['palavra'] in words_deleted:
            if not any(entry['palavra'] == word_data['palavra'] for entry in new_log):
                word_data['escrita_completa'] = False
    save_user_data(full_data, language)
    st.session_state.pop(f"db_df_{language}", None)

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

def load_sentence_log(language):
    return get_user_data(language).get('sentence_log', [])

def save_sentence_log(log_data, language):
    full_data = get_user_data(language)
    full_data['sentence_log'] = log_data
    save_user_data(full_data, language)

def delete_sentence_log_entry(word_key, language):
    full_data = get_user_data(language)
    log = full_data.get('sentence_log', [])
    log = [entry for entry in log if entry.get('palavra_chave') != word_key]
    full_data['sentence_log'] = log
    save_user_data(full_data, language)

# --- Carregamento de Arquivos do GitHub ---
@st.cache_data
def carregar_arquivos_base():
    """Baixa e processa os arquivos de base do GitHub."""
    def baixar_e_processar(filename, process_func):
        url = BASE_URL + filename
        try:
            response = requests.get(url)
            response.raise_for_status()
            content = response.text
            return process_func(content)
        except requests.exceptions.RequestException as e:
            st.error(f"Falha ao baixar '{filename}' do GitHub: {e}")
            return []

    def processar_anki(content):
        # COLE AQUI SUA LÓGICA PARA PROCESSAR O CONTEÚDO DO cartoes_validacao.txt
        return []

    def processar_gpt(content):
        # COLE AQUI SUA LÓGICA PARA PROCESSAR O CONTEÚDO DO Dados_Manual_output_GPT.txt
        return []
    
    def processar_cloze(content):
        # COLE AQUI SUA LÓGICA PARA PROCESSAR O CONTEÚDO DO Dados_Manual_Cloze_text.txt
        return []

    flashcards = baixar_e_processar(CARTOES_FILE_BASE, processar_anki)
    gpt_exercicios = baixar_e_processar(GPT_FILE_BASE, processar_gpt)
    cloze_exercicios = baixar_e_processar(CLOZE_FILE_BASE, processar_cloze)

    return flashcards, gpt_exercicios + cloze_exercicios

@st.cache_data
def load_sentence_data(language):
    url = BASE_URL + SENTENCE_WORDS_FILE
    words_data = {}
    try:
        from io import StringIO
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text), sep=';')
        if 'idioma' in df.columns:
            df = df[df['idioma'] == language]
        for _, row in df.iterrows():
            key = f"{row['Palavra']}_{row['Classe']}_{row['Nível']}"
            words_data[key] = { 'palavra_base': row['Palavra'], 'Classe': row['Classe'], 'Nível': row['Nível'], 'Outra Frase': row['Frase'] }
    except Exception as e:
        st.error(f"Erro ao ler arquivo de frases do GitHub: {e}")
    return words_data

# --- Sincronização e Gerenciamento de BD ---
def sync_database(language):
    flashcards_raw, gpt_raw = carregar_arquivos_base()
    
    # IMPORTANTE: Adapte esta lógica para filtrar os dados por idioma
    flashcards = [f for f in flashcards_raw]
    gpt_exercicios = [g for g in gpt_raw]

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
    if not updated_list:
        return pd.DataFrame(columns=expected_columns)
    else:
        df = pd.DataFrame(updated_list)
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None
        return df

def get_session_db(language):
    session_key = f"db_df_{language}"
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
        total_sessoes = sum(len(v) for v in historico.values())
        total_acertos = sum(s.get('acertos', 0) for v in historico.values() for s in v)
        total_erros = sum(s.get('erros', 0) for v in historico.values() for s in v)
        if (total_acertos + total_erros) > 0:
            summary['kpis']['precisao'] = f"{total_acertos / (total_acertos + total_erros) * 100:.1f}%"
        summary['kpis']['sessoes'] = total_sessoes
    return summary