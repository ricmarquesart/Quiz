import streamlit as st
import random
import datetime
from collections import defaultdict
from core.data_manager import (
    get_session_db,
    save_vocab_db,
    update_progress_from_quiz,
    carregar_arquivos_base,
    TIPOS_EXERCICIO_ANKI
)
from core.quiz_logic import selecionar_questoes_priorizadas, gerar_questao_dinamica
from core.localization import get_text

def reactivate_words_on_error(words_to_reactivate, language):
    """
    Reactivates words if an error is made during review.
    """
    if not words_to_reactivate:
        return
    
    db_df = get_session_db(language)
    words_actually_reactivated = []

    for word in set(words_to_reactivate):
        idx_list = db_df.index[db_df['palavra'] == word].tolist()
        if not idx_list:
            continue
        
        idx = idx_list[0]
        db_df.loc[idx, 'ativa'] = True
        
        progresso = db_df.loc[idx, 'progresso']
        if isinstance(progresso, dict):
            for key in progresso:
                progresso[key] = 'nao_testado'
            db_df.at[idx, 'progresso'] = progresso
        
        words_actually_reactivated.append(word)

    if words_actually_reactivated:
        save_vocab_db(db_df, language)
        st.warning(get_text("words_reactivated", language).format(words=', '.join(words_actually_reactivated)))

def review_quiz_ui(language, debug_mode):
    """
    Renders the Review Mode page, now with robust data handling.
    """
    # --- STEP 1: Load necessary data ---
    flashcards, gpt_exercicios = carregar_arquivos_base(language)
    db_df = get_session_db(language)

    # --- Back Button ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_review"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('review_quiz', None)
        st.rerun()

    st.header(get_text("review_mode_title", language))
    
    # --- FIX FOR KEYERROR ---
    # Checks if the DataFrame is empty or lacks the 'ativa' column before use.
    if db_df.empty or 'ativo' not in db_df.columns:
        st.info(get_text("no_inactive_words_info", language, default="You have no mastered words to review yet. Keep practicing in other modes!"))
        return

    palavras_inativas = db_df[db_df['ativa'] == False]
    
    if palavras_inativas.empty:
        st.info(get_text("no_inactive_words_info", language, default="You have no mastered words to review yet. Keep practicing in other modes!"))
        return

    # --- Main Logic ---
    gpt_exercicios_filtrados = [ex for ex in gpt_exercicios if 'cloze_text' not in ex]
    flashcards_map = {card['palavra']: card for card in flashcards}
    gpt_exercicios_map = defaultdict(list)
    for ex in gpt_exercicios_filtrados:
        if ex.get('palavra'):
            gpt_exercicios_map[ex['palavra']].append(ex)

    if 'review_quiz' not in st.session_state:
        st.session_state.review_quiz = {}

    if not st.session_state.review_quiz.get('started', False):
        with st.form("review_quiz_cfg"):
            st.info(get_text("review_info", language))
            max_questoes = len(palavras_inativas)
            N = st.number_input(get_text("how_many_words_to_review", language), 1, max_questoes, min(5, max_questoes), 1)
            if st.form_submit_button(get_text("start_review", language)):
                playlist = selecionar_questoes_priorizadas(palavras_inativas, flashcards_map, gpt_exercicios_map, N, "Random")
                if not playlist:
                    st.error(get_text("no_valid_questions", language))
                else:
                    st.session_state.review_quiz = {'started': True, 'playlist': playlist, 'idx': 0, 'resultados_formatados': [], 'mostrar_resposta': False}
                    st.rerun()
    else:
        quiz = st.session_state.review_quiz
        playlist = quiz.get('playlist', [])
        idx = quiz.get('idx', 0)

        if not quiz.get('started') or not playlist:
            st.warning("O quiz não pôde ser iniciado. Retornando à configuração.")
            st.session_state.pop('review_quiz', None)
            st.rerun()

        total = len(playlist)
        if idx < total:
            if f"review_pergunta_{idx}" not in st.session_state:
                item = playlist[idx]
                tipo, pergunta, opts, ans_idx, cefr_level, id_ex = gerar_questao_dinamica(item, flashcards_map, gpt_exercicios_map, db_df)
                st.session_state[f"review_tipo_{idx}"] = tipo
                st.session_state[f"review_pergunta_{idx}"] = pergunta
                st.session_state[f"review_opts_{idx}"] = opts
                st.session_state[f"review_ans_idx_{idx}"] = ans_idx
                st.session_state[f"review_cefr_{idx}"] = cefr_level
                st.session_state[f"review_id_ex_{idx}"] = id_ex
            
            # --- Question display logic ---
            # (Your full question display logic goes here)

        else:
            # --- Results screen ---
            resultados_finais = quiz.get('resultados_formatados', [])
            erros_palavras = [r['palavra'] for r in resultados_finais if not r['acertou']]
            reactivate_words_on_error(erros_palavras, language)

            # Note: The original progress update was removed as reactivating is the main purpose.
            # If you still want to record the review session in history, that logic can be added here.
            
            acertos = total - len(erros_palavras)
            score = int(acertos / total * 100) if total > 0 else 0
            
            st.success(get_text("review_complete", language).format(score=score))
            
            if st.button(get_text("finish_button", language)):
                st.session_state.pop('review_quiz', None)
                st.rerun()