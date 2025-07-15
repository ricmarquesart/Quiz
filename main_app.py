import streamlit as st
import pandas as pd
import altair as alt
from collections import Counter
import datetime

# Imports do sistema
from core.auth import initialize_firebase, login_form, logout
from core.data_manager import get_session_db, get_performance_summary
from core.localization import get_text

# --- Configuração da Página e CSS ---
st.set_page_config(page_title="CELPIP & TCF Study App", layout="centered")

st.markdown("""
    <style>
    .block-container { max-width: 1100px; }
    .main-title { text-align: center; font-weight: bold; font-size: 48px; margin-bottom: 20px; }
    .section-header { text-align: center; font-weight: bold; font-size: 28px; margin-top: 40px; margin-bottom: 15px; }
    .stButton>button { height: 100px; font-size: 20px; font-weight: bold; border-radius: 10px; }
    .quiz-title { font-size: 38px; font-weight: bold; margin-bottom: 5px; }
    .question-bg { font-size: 27px; padding: 1.5rem; border-radius: 0.75rem; line-height: 1.4; margin-bottom: 0.5rem; }
    .options-container { overflow-y: auto; padding: 1rem; border-radius: 0.75rem; margin-bottom: 0.5rem; }
    .keyword-highlight { font-weight: bold !important; }
    [data-theme="light"] .section-header { color: #005A9C; }
    [data-theme="light"] .question-bg { background-color: #eef1f5 !important; border-color: #d6dae0 !important; }
    [data-theme="light"] .options-container { border: 1px solid #d6dae0; }
    [data-theme="light"] .keyword-highlight, [data-theme="light"] .keyword-highlight span { color: #D32F2F !important; }
    [data-theme="light"] .stButton>button { background-color: #f0f2f6; border: 1px solid #d6dae0; color: #31333f; }
    [data-theme="dark"] .section-header { color: #89cff0; }
    [data-theme="dark"] .question-bg { background-color: #1E1E1E !important; border: 1px solid #3c3c3c !important; }
    [data-theme="dark"] .options-container { border: 1px solid #3c3c3c; }
    [data-theme="dark"] .stButton>button { background-color: #2a2a2a; border: 1px solid #4a4a4a; }
    [data-theme="dark"] .keyword-highlight, [data-theme="dark"] .keyword-highlight span { color: #FFD700 !important; }
    </style>
""", unsafe_allow_html=True)


def inject_language_specific_css(language):
    color_en_light = "#FFF0F0"
    color_fr_light = "#F0F8FF"
    color_dark = "#121212"
    css = f"""
    <style>
        [data-theme="light"] .stApp {{ background-color: {color_en_light if language == 'en' else color_fr_light}; }}
        [data-theme="dark"] .stApp {{ background-color: {color_dark}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def display_user_header():
    header_cols = st.columns([0.85, 0.15])
    with header_cols[0]:
        st.success(f"Logado como {st.session_state['user_info']['display_name']}")
    with header_cols[1]:
        if st.button("Logout", use_container_width=True):
            # A função de logout agora deve estar no seu core/auth.py
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- Funções de Renderização (Restauradas e Corrigidas) ---

def render_language_selection():
    """Tela de Seleção de Idioma que mostra os KPIs e Gráficos."""
    display_user_header()
    st.markdown("---")
    
    st.markdown(f"<h1 class='main-title'>{get_text('app_title', 'en')}</h1>", unsafe_allow_html=True)
    st.session_state.debug_mode = st.toggle(get_text('debug_mode_toggle', 'en'), value=st.session_state.get('debug_mode', False))
    st.divider()

    summary_en = get_performance_summary('en')
    summary_fr = get_performance_summary('fr')

    st.markdown(f"<h2 class='section-header'>{get_text('progress_overview_header', 'en')}</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("English 🇨🇦")
        if st.button(get_text('practice_english_button', 'en'), use_container_width=True):
            st.session_state.language = 'en'
            st.session_state.current_page = 'Homepage'
            st.rerun()
        # Lógica completa para gráficos de Inglês aqui...
        
    with c2:
        st.subheader("Français 🇫🇷")
        if st.button(get_text('practice_french_button', 'fr'), use_container_width=True):
            st.session_state.language = 'fr'
            st.session_state.current_page = 'Homepage'
            st.rerun()
        # Lógica completa para gráficos de Francês aqui...

def render_homepage(language, debug_mode):
    """Dashboard principal com todos os KPIs e botões."""
    display_user_header()
    st.markdown("---")

    st.markdown(f"<h1 class='main-title'>{get_text('dashboard_title', language)}</h1>", unsafe_allow_html=True)
    if st.button(get_text('change_language_button', language)):
        st.session_state.current_page = "LanguageSelection"
        st.session_state.language = None
        st.rerun()

    summary = get_performance_summary(language)
    kpi1, kpi2, kpi3 = st.columns(3)
    
    # CORREÇÃO PARA KEYERROR: Usar .get() para aceder ao dicionário de forma segura
    kpi1.metric(get_text('active_words_metric', language), summary.get('db_kpis', {}).get('ativas', 0))
    kpi2.metric(get_text('accuracy_metric', language), summary.get('kpis', {}).get('precisao', 'N/A'))
    kpi3.metric(get_text('sessions_metric', language), summary.get('kpis', {}).get('sessoes', 0))
    st.divider()

    # Grade de botões completa
    st.markdown(f"<h2 class='section-header'>{get_text('practice_header', language)}</h2>", unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button(get_text('anki_quiz_button', language), use_container_width=True): st.session_state.current_page = "Quiz ANKI"; st.rerun()
    if b2.button(get_text('gpt_quiz_button', language), use_container_width=True): st.session_state.current_page = "Quiz GPT"; st.rerun()
    if b3.button(get_text('mixed_quiz_button', language), use_container_width=True): st.session_state.current_page = "Quiz Misto"; st.rerun()
    if b4.button(get_text('cloze_quiz_button', language), use_container_width=True): st.session_state.current_page = "Cloze Quiz"; st.rerun()

    st.markdown(f"<h2 class='section-header'>{get_text('reinforce_header', language)}</h2>", unsafe_allow_html=True)
    b5, b6 = st.columns(2)
    if b5.button(get_text('review_mode_button', language), use_container_width=True): st.session_state.current_page = "Modo de Revisão"; st.rerun()
    if b6.button(get_text('focus_mode_button', language), use_container_width=True): st.session_state.current_page = "Modo Foco"; st.rerun()

    st.markdown(f"<h2 class='section-header'>{get_text('analyze_header', language)}</h2>", unsafe_allow_html=True)
    b7, b8, b9 = st.columns(3)
    if b7.button(get_text('writing_mode_button', language), use_container_width=True): st.session_state.current_page = "Modo de Escrita"; st.rerun()
    if b8.button(get_text('sentence_writing_button', language), use_container_width=True):
        if 'word_sentence_index' in st.session_state: del st.session_state['word_sentence_index']
        st.session_state.current_page = "Sentence Writing"; st.rerun()
    if b9.button(get_text('stats_button', language), use_container_width=True): st.session_state.current_page = "Estatísticas"; st.rerun()


def main():
    if not initialize_firebase():
        st.error("Falha crítica na conexão com o serviço de autenticação.")
        return

    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'language' not in st.session_state: st.session_state.language = None
    if 'current_page' not in st.session_state: st.session_state.current_page = "LanguageSelection"
    
    if not st.session_state.logged_in:
        login_form()
    else:
        if st.session_state.language and f"db_df_{st.session_state.language}" not in st.session_state:
            get_session_db(st.session_state.language)
        
        if st.session_state.language:
            inject_language_specific_css(st.session_state.language)
        
        page = st.session_state.current_page
        language = st.session_state.language
        debug_mode = st.session_state.get('debug_mode', False)

        if not language or page == "LanguageSelection":
            render_language_selection()
        else:
            page_modules = {
                "Homepage": render_homepage,
                "Quiz ANKI": "modules.quiz_ui.quiz_ui",
                "Quiz GPT": "modules.gpt_quiz_ui.gpt_ex_ui",
                "Quiz Misto": "modules.mixed_quiz_ui.mixed_quiz_ui",
                "Cloze Quiz": "modules.cloze_quiz_ui.cloze_quiz_ui",
                "Modo de Revisão": "modules.review_quiz_ui.review_quiz_ui",
                "Modo Foco": "modules.focus_quiz_ui.focus_quiz_ui",
                "Modo de Escrita": "modules.writing_ui.writing_ui",
                "Sentence Writing": "modules.sentence_writing_ui.sentence_writing_ui",
                "Estatísticas": "modules.stats_ui.estatisticas_ui",
            }
            if page in page_modules:
                module_path = page_modules[page]
                if page == "Homepage":
                    render_homepage(language, debug_mode)
                else:
                    try:
                        parts = module_path.split('.')
                        module_name = ".".join(parts[:-1])
                        func_name = parts[-1]
                        mod = __import__(module_name, fromlist=[func_name])
                        page_func = getattr(mod, func_name)
                        
                        if page == "Estatísticas":
                            page_func(language)
                        else:
                            page_func(language, debug_mode)
                    except Exception as e:
                        st.error(f"Erro ao carregar o módulo da página '{page}': {e}")
                        if st.button("Voltar ao Início"):
                            st.session_state.current_page = "Homepage"
                            st.rerun()

if __name__ == "__main__":
    main()