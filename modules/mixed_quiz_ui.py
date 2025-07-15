import streamlit as st
import random
import datetime
import re
from collections import defaultdict
from core.data_manager import (
    get_session_db,
    get_history,
    save_history,
    update_progress_from_quiz,
    carregar_arquivos_base,
    TIPOS_EXERCICIO_ANKI
)
from core.quiz_logic import selecionar_questoes_priorizadas, gerar_questao_dinamica
from core.localization import get_text

def mixed_quiz_ui(language, debug_mode):
    """
    Renderiza a página do Quiz Misto, com tratamento de erros para novos utilizadores.
    """
    # --- Carregamento de Dados ---
    flashcards, gpt_exercicios = carregar_arquivos_base(language)
    db_df = get_session_db(language)

    # --- Botão de Voltar ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_mixed"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('mixed_quiz', None)
        st.rerun()

    st.header(get_text("mixed_quiz_button", language))

    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if db_df.empty or 'ativo' not in db_df.columns:
        st.warning("A sua base de vocabulário está a ser sincronizada. Por favor, ative algumas palavras na página 'Estatísticas & Gerenciador' para começar.")
        return

    # --- Lógica Principal ---
    gpt_exercicios_filtrados = [ex for ex in gpt_exercicios if 'cloze_text' not in ex]
    palavras_ativas = db_df[db_df['ativo'] == True]

    if palavras_ativas.empty:
        st.warning(get_text("no_active_words", language))
        return

    flashcards_map = {card['palavra']: card for card in flashcards if 'palavra' in card}
    gpt_exercicios_map = defaultdict(list)
    for ex in gpt_exercicios_filtrados:
        if ex.get('palavra'):
            gpt_exercicios_map[ex['palavra']].append(ex)

    if 'mixed_quiz' not in st.session_state:
        st.session_state.mixed_quiz = {}

    if not st.session_state.mixed_quiz.get('started', False):
        with st.form("mixed_quiz_cfg"):
            st.info(get_text("mixed_quiz_info", language))
            num_exercicios_disponiveis = len(palavras_ativas) * 8
            N = st.number_input(get_text("how_many_questions", language), 1, max(1, num_exercicios_disponiveis), min(10, max(1, num_exercicios_disponiveis)), 1, key="mixed_n_cards")
            if st.form_submit_button(get_text("start_quiz", language)):
                playlist = selecionar_questoes_priorizadas(palavras_ativas, flashcards_map, gpt_exercicios_map, N)
                if not playlist:
                    st.error(get_text("no_valid_questions", language))
                else:
                    st.session_state.mixed_quiz = {
                        'started': True, 'playlist': playlist, 'idx': 0,
                        'resultados_formatados': [], 'mostrar_resposta': False
                    }
                    st.rerun()
    else:
        quiz_state = st.session_state.mixed_quiz
        playlist = quiz_state.get('playlist', [])
        idx = quiz_state.get('idx', 0)

        if not quiz_state.get('started') or not playlist:
            st.warning("O quiz não pôde ser iniciado. Retornando à configuração.")
            st.session_state.pop('mixed_quiz', None)
            st.rerun()

        total = len(playlist)
        if idx < total:
            if f"mixed_pergunta_{idx}" not in st.session_state:
                item_playlist = playlist[idx]
                tipo, pergunta, opts, ans_idx, cefr_level, id_ex = gerar_questao_dinamica(item_playlist, flashcards_map, gpt_exercicios_map, db_df)
                st.session_state[f"mixed_tipo_{idx}"] = tipo
                st.session_state[f"mixed_pergunta_{idx}"] = pergunta
                st.session_state[f"mixed_opts_{idx}"] = opts
                st.session_state[f"mixed_ans_idx_{idx}"] = ans_idx
                st.session_state[f"mixed_cefr_{idx}"] = cefr_level
                st.session_state[f"mixed_id_ex_{idx}"] = id_ex

            tipo_interno, pergunta, opts, ans_idx, cefr_level, id_ex = (
                st.session_state.get(f"mixed_tipo_{idx}"),
                st.session_state.get(f"mixed_pergunta_{idx}"),
                st.session_state.get(f"mixed_opts_{idx}"),
                st.session_state.get(f"mixed_ans_idx_{idx}"),
                st.session_state.get(f"mixed_cefr_{idx}"),
                st.session_state.get(f"mixed_id_ex_{idx}")
            )
            
            if tipo_interno in TIPOS_EXERCICIO_ANKI.values():
                 tipos_legenda = {
                     "gerar_mcq_significado": get_text("word_meaning_anki", language),
                     "gerar_mcq_traducao_ingles": get_text("translation_anki", language),
                     "gerar_mcq_sinonimo": get_text("synonym_anki", language),
                     "gerar_fill_gap": get_text("gap_fill_anki", language),
                     "gerar_reading_comprehension": get_text("reading_anki", language)
                 }
                 nome_base = tipos_legenda.get(tipo_interno, tipo_interno)
                 tipo_display = f"{nome_base} (ANKI)"
            else:
                 tipo_display = f"{tipo_interno} (GPT)"

            if not pergunta or opts is None:
                quiz_state['idx'] += 1
                st.rerun()

            col1, col2 = st.columns([4, 1])
            with col1:
                st.progress(idx / total, get_text("quiz_progress", language).format(idx=idx, total=total))
                st.markdown(f'<div class="quiz-title">{tipo_display}</div>', unsafe_allow_html=True)
            with col2:
                if cefr_level:
                    st.markdown(f'<div style="text-align: right; font-weight: bold; font-size: 24px; color: #888;">{cefr_level}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="question-bg">{pergunta}</div>', unsafe_allow_html=True)
            with st.container():
                st.markdown('<div class="options-container">', unsafe_allow_html=True)
                resposta = st.radio("Selecione a resposta:", opts, key=f"mixed_radio_{idx}", label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                if not quiz_state.get('mostrar_resposta'):
                    if st.button(get_text("check_button", language), key=f"mixed_check_{idx}"):
                        quiz_state['mostrar_resposta'] = True
                        quiz_state['ultimo_resultado'] = (opts.index(resposta) == ans_idx)
                        quiz_state['ultimo_correto'] = opts[ans_idx]
                        st.rerun()
                else:
                    if st.button(get_text("next_button", language), key=f"mixed_next_{idx}"):
                        item_atual = playlist[idx]
                        resultado_dict = {
                            "palavra": item_atual['palavra'],
                            "tipo_exercicio": id_ex,
                            "acertou": quiz_state['ultimo_resultado']
                        }
                        quiz_state.setdefault('resultados_formatados', []).append(resultado_dict)
                        quiz_state['idx'] += 1
                        quiz_state['mostrar_resposta'] = False
                        st.rerun()
                    if quiz_state['ultimo_resultado']: st.success(get_text("correct_answer", language))
                    else: st.error(get_text("incorrect_answer", language).format(correct=quiz_state['ultimo_correto']))
            with col_btn2:
                if st.button(get_text("cancel_quiz", language)):
                    st.session_state.pop('mixed_quiz', None)
                    st.rerun()
        else:
            resultados_finais = quiz_state.get('resultados_formatados', [])
            update_progress_from_quiz(resultados_finais, language)
            
            acertos = sum(1 for r in resultados_finais if r['acertou'])
            erros = len(resultados_finais) - acertos
            score = int(acertos / total * 100) if total > 0 else 0
            
            st.success(get_text("final_result", language).format(correct_count=acertos, error_count=erros, score=score))
            
            historico = get_history(language)
            historico.setdefault("mixed_quiz", []).append({
                "data": datetime.datetime.now().isoformat(),
                "acertos": acertos,
                "erros": erros,
                "palavras_erradas": [r['palavra'] for r in resultados_finais if not r['acertou']],
                "score": score,
                "total": total
            })
            save_history(historico, language)
            
            if st.button(get_text("finish_button", language)):
                st.session_state.pop('mixed_quiz', None)
                st.rerun()