import streamlit as st
import random
import re
from collections import defaultdict
from core.data_manager import (
    get_session_db,
    update_progress_from_quiz,
    carregar_arquivos_base,
    TIPOS_EXERCICIO_ANKI
)
from core.quiz_logic import gerar_questao_dinamica, get_available_exercise_types_for_word
from core.localization import get_text

def focus_quiz_ui(language, debug_mode):
    """
    Renders the Focus Mode page, now with robust data handling for new users.
    """
    # --- STEP 1: Load necessary data ---
    flashcards, gpt_exercicios = carregar_arquivos_base(language)
    db_df = get_session_db(language)

    # --- Back Button ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_focus"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('focus_quiz', None)
        st.rerun()

    st.header(get_text("focus_mode_button", language))

    # --- FIX FOR KEYERROR ---
    # Checks if the DataFrame is empty or lacks the 'ativa' column before use.
    if db_df.empty or 'ativo' not in db_df.columns:
        st.warning(get_text("no_active_words", language))
        st.info("Please go to the 'Stats & Manager' page to activate some words for practice.")
        return

    palavras_ativas = sorted(db_df[db_df['ativa'] == True]['palavra'].tolist())

    if not palavras_ativas:
        st.warning(get_text("no_active_words", language))
        return

    # --- Main Logic ---
    flashcards_map = {card.get('palavra'): card for card in flashcards if card.get('palavra')}
    gpt_exercicios_map = defaultdict(list)
    for ex in gpt_exercicios:
        if ex.get('palavra'):
            gpt_exercicios_map[ex['palavra']].append(ex)

    if 'focus_quiz' not in st.session_state:
        st.session_state.focus_quiz = {}

    if not st.session_state.focus_quiz.get('started', False):
        st.info(get_text("focus_mode_info", language))
        
        palavra_selecionada = st.selectbox(get_text("choose_focus_word", language), palavras_ativas)
        
        if st.button(get_text("start_focus_button", language, word=palavra_selecionada)):
            st.session_state.pop('focus_quiz', None)
            
            exercicios_palavra = get_available_exercise_types_for_word(palavra_selecionada, flashcards_map, gpt_exercicios_map)
            
            playlist = [
                {'palavra': palavra_selecionada, 'tipo_exercicio': tipo, 'identificador': identificador}
                for identificador, tipo in exercicios_palavra.items() if tipo != 'cloze_text'
            ]
            
            if not playlist:
                st.error(f"Nenhum exercício válido encontrado para a palavra '{palavra_selecionada}'.")
            else:
                random.shuffle(playlist)
                st.session_state.focus_quiz = {'started': True, 'playlist': playlist, 'idx': 0, 'resultados_formatados': [], 'mostrar_resposta': False}
                st.rerun()
    else:
        # --- Quiz In Progress UI ---
        quiz = st.session_state.focus_quiz
        playlist = quiz.get('playlist', [])
        idx = quiz.get('idx', 0)

        if not quiz.get('started') or not playlist:
            st.warning("O quiz não pôde ser iniciado. Retornando à configuração.")
            st.session_state.pop('focus_quiz', None)
            st.rerun()

        total = len(playlist)
        if idx < total:
            if f"focus_pergunta_{idx}" not in st.session_state:
                item = playlist[idx]
                tipo, pergunta, opts, ans_idx, cefr_level, id_ex = gerar_questao_dinamica(item, flashcards_map, gpt_exercicios_map, db_df)
                st.session_state[f"focus_tipo_{idx}"] = tipo
                st.session_state[f"focus_pergunta_{idx}"] = pergunta
                st.session_state[f"focus_opts_{idx}"] = opts
                st.session_state[f"focus_ans_idx_{idx}"] = ans_idx
                st.session_state[f"focus_cefr_{idx}"] = cefr_level
                st.session_state[f"focus_id_ex_{idx}"] = id_ex
            
            # --- Question Display Logic ---
            # (Your full question display logic goes here)

        else:
            # --- Results Screen ---
            resultados_finais = quiz.get('resultados_formatados', [])
            update_progress_from_quiz(resultados_finais, language)
            
            acertos = sum(1 for r in resultados_finais if r['acertou'])
            erros = len(resultados_finais) - acertos
            score = int(acertos / total * 100) if total > 0 else 0
            
            st.success(get_text("final_result", language).format(correct_count=acertos, error_count=erros, score=score))
            
            if st.button(get_text("choose_another_word", language)):
                st.session_state.pop('focus_quiz', None)
                st.rerun()