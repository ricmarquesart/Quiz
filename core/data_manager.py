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
TIPOS_EXERCICIO_GPT = [
    "sinonimo_mcq", "antonym_mcq", "definition_mcq", "context_mcq",
    "fill_in_the_blank_1", "fill_in_the_blank_2", "cloze_text"
]

# --- Interação com Firestore (Completo) ---
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
        'historico': {"quiz": [], "gpt_quiz": [], "mixed_quiz": [], "review_quiz": [], "focus_quiz": [], "cloze_quiz": []},
        'writing_log': [],
        'sentence_log': []
    }

def save_user_data(data_dict, language):
    doc_ref = get_user_doc_ref(language)
    if doc_ref:
        doc_ref.set(data_dict)

# --- Funções "Wrapper" de Dados (Completo e Restaurado) ---
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
    full_data['historico'] = {k: [] for k in full_data.get('historico', {}).keys()}
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


# --- Carregamento de Arquivos e Sincronização ---
@st.cache_data
def carregar_arquivos_base(language):
    """
    Baixa o conteúdo do GitHub e DEPOIS filtra e processa para o idioma correto.
    """
    @st.cache_data
    def baixar_conteudo(filename):
        url = BASE_URL + filename
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            st.error(f"Falha ao baixar '{filename}' do GitHub: {e}")
            return None

    def processar_e_filtrar_anki(content, lang):
        flashcards_filtrados = []
        if not content: return flashcards_filtrados
        
        lang_map = {'en': 'English', 'fr': 'Francais'}
        target_lang_str = lang_map.get(lang)
        if not target_lang_str: return flashcards_filtrados

        blocos = re.split(r'\n\s*\n', content.strip())
        for bloco in blocos:
            if not bloco.strip(): continue
            linhas = [linha.strip() for linha in bloco.strip().split('\n')]
            header = linhas[0]

            if target_lang_str not in header:
                continue

            card = {'source': 'ANKI', 'idioma': lang}
            match = re.match(r"(.+?)\s*\((.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\):", header)
            if match:
                card['palavra'] = match.group(1).strip()
                card['classe'] = match.group(2).strip()
                card['cefr'] = match.group(3).strip()
            else:
                continue

            for linha in linhas[1:]:
                if ': ' in linha:
                    linha_limpa = re.sub(r'\\s*', '', linha).strip()
                    key, value = linha_limpa.split(': ', 1)
                    key = key.replace('- ', '').strip().lower().replace(' ', '_')
                    card[key] = value.strip()
            
            flashcards_filtrados.append(card)
        return flashcards_filtrados

    def processar_e_filtrar_gpt(content, lang):
        exercicios_filtrados = []
        if not content: return exercicios_filtrados
        for linha in content.strip().split('\n'):
            linha_limpa = re.sub(r'\\s*', '', linha).strip()
            partes = linha_limpa.strip().split(';')
            if not partes or len(partes) < 7 or partes[0] != lang:
                continue
            
            try:
                exercicio = {
                    'idioma': partes[0], 'tipo': partes[1], 'frase': partes[2],
                    'opcoes': [opt.strip() for opt in partes[3].split('|')],
                    'correta': partes[4], 'principal': partes[5], 'cefr_level': partes[6],
                    'source': 'GPT', 'palavra': partes[5]
                }
                exercicios_filtrados.append(exercicio)
            except IndexError:
                continue
        return exercicios_filtrados
    
    conteudo_anki = baixar_conteudo(CARTOES_FILE_BASE)
    conteudo_gpt = baixar_conteudo(GPT_FILE_BASE)
    
    flashcards = processar_e_filtrar_anki(conteudo_anki, language)
    gpt_exercicios = processar_e_filtrar_gpt(conteudo_gpt, language)
    
    return flashcards, gpt_exercicios


@st.cache_data
def load_sentence_data(language):
    url = BASE_URL + SENTENCE_WORDS_FILE
    words_data = {}
    try:
        response = requests.get(url)
        response.raise_for_status()
        col_names = ['Palavra', 'Classe', 'Nível', 'Frase', 'idioma']
        df = pd.read_csv(StringIO(response.text), sep=';', header=None, names=col_names, on_bad_lines='skip')
        df = df[df['idioma'] == language]
        for _, row in df.iterrows():
            key = f"{row['Palavra']}_{row['Classe']}_{row['Nível']}"
            words_data[key] = { 'palavra_base': row['Palavra'], 'Classe': row['Classe'], 'Nível': row['Nível'], 'Outra Frase': row['Frase'] }
    except Exception as e:
        st.error(f"Erro ao ler arquivo de frases do GitHub: {e}")
    return words_data

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
        total_sessoes = sum(len(v) for v in historico.values())
        total_acertos = sum(s.get('acertos', 0) for v in historico.values() for s in v)
        total_erros = sum(s.get('erros', 0) for v in historico.values() for s in v)
        if (total_acertos + total_erros) > 0:
            summary['kpis']['precisao'] = f"{total_acertos / (total_acertos + total_erros) * 100:.1f}%"
        summary['kpis']['sessoes'] = total_sessoes
    return summary