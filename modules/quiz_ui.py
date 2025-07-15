import streamlit as st
import random
import datetime
from collections import defaultdict
from core.data_manager import get_session_db, update_progress_from_quiz, save_history, get_history, carregar_arquivos_base, TIPOS_EXERCICIO_ANKI
from core.quiz_logic import selecionar_questoes_priorizadas, gerar_questao_dinamica
from core.localization import get_text 

def quiz_ui(language, debug_mode):
    flashcards, gpt_exercicios = carregar_arquivos_base(language)
    db_df = get_session_db(language)

    if st.button(get_text("back_to_dashboard", language), key="back_from_anki"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('quiz_anki', None)
        st.rerun()

    st.header(get_text("anki_quiz_title", language))
    
    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if db_df.empty or 'ativo' not in db_df.columns:
        st.warning("A sua base de vocabulário está a ser sincronizada. Por favor, ative algumas palavras na página 'Estatísticas & Gerenciador' para começar.")
        return

    palavras_ativas = db_df[db_df['ativa'] == True]

    if debug_mode:
        # A sua lógica de depuração aqui...
        pass

    if palavras_ativas.empty:
        st.warning(get_text("no_active_words", language))
        return

    # O resto da sua lógica completa do quiz continua aqui...
        return

    baralho_map = {card['palavra']: card for card in flashcards if 'palavra' in card}
    gpt_map = defaultdict(list)
    for ex in gpt_exercicios:
        if ex.get('palavra'):
            gpt_map[ex['palavra']].append(ex)

    tipos_legenda = {
        "MCQ Significado": get_text("word_meaning_anki", language),
        "MCQ Tradução Inglês": get_text("translation_anki", language),
        "MCQ Sinônimo": get_text("synonym_anki", language),
        "Fill": get_text("gap_fill_anki", language),
        "Reading": get_text("reading_anki", language)
    }

    if 'quiz_anki' not in st.session_state:
        st.session_state.quiz_anki = {}

    if not st.session_state.quiz_anki.get('started', False):
        with st.form("anki_quiz_cfg"):
            tipos_disponiveis = list(TIPOS_EXERCICIO_ANKI.keys())
            tipos_exibidos = ["Random"] + [tipos_legenda.get(t, t) for t in tipos_disponiveis]
            
            tipo_escolhido_leg = st.selectbox(get_text("choose_exercise_type", language), tipos_exibidos)
            
            max_questoes = len(palavras_ativas) * len(tipos_disponiveis)
            N = st.number_input(get_text("how_many_questions", language), 1, max(1, max_questoes), min(10, max(1, max_questoes)), 1)
            
            if st.form_submit_button(get_text("start_quiz", language)):
                tipo_escolhido_interno = {v: k for k, v in tipos_legenda.items()}.get(tipo_escolhido_leg, "Random")
                playlist = selecionar_questoes_priorizadas(palavras_ativas, baralho_map, gpt_map, N, tipo_escolhido_interno)
                if not playlist:
                     st.error(get_text("no_valid_questions", language))
                else:
                    st.session_state.quiz_anki = {'started': True, 'idx': 0, 'total': len(playlist), 'playlist': playlist, 'resultados_formatados': []}
                    st.rerun()
    else:
        quiz = st.session_state.quiz_anki
        idx, total = quiz.get('idx', 0), quiz.get('total', 0)
        
        if not quiz.get('started') or not quiz.get('playlist'):
             st.warning("O quiz não pôde ser iniciado. Retornando à configuração.")
             st.session_state.pop('quiz_anki', None)
             st.rerun()

        if idx < total:
            if f"quiz_anki_pergunta_{idx}" not in st.session_state:
                item = quiz['playlist'][idx]
                tipo, pergunta, opts, ans_idx, cefr_level, id_ex = gerar_questao_dinamica(item, baralho_map, gpt_map, db_df)
                st.session_state[f"quiz_anki_tipo_{idx}"] = tipo
                st.session_state[f"quiz_anki_pergunta_{idx}"] = pergunta
                st.session_state[f"quiz_anki_opts_{idx}"] = opts
                st.session_state[f"quiz_anki_ans_idx_{idx}"] = ans_idx
                st.session_state[f"quiz_anki_cefr_{idx}"] = cefr_level
                st.session_state[f"quiz_anki_id_ex_{idx}"] = id_ex

            tipo_interno, pergunta, opts, ans_idx, cefr_level, id_ex = (
                st.session_state.get(f"quiz_anki_tipo_{idx}"),
                st.session_state.get(f"quiz_anki_pergunta_{idx}"),
                st.session_state.get(f"quiz_anki_opts_{idx}"),
                st.session_state.get(f"quiz_anki_ans_idx_{idx}"),
                st.session_state.get(f"quiz_anki_cefr_{idx}"),
                st.session_state.get(f"quiz_anki_id_ex_{idx}")
            )
            
            tipo_display = tipos_legenda.get(tipo_interno, tipo_interno)

            if not pergunta or opts is None:
                quiz['idx'] += 1
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
                resposta = st.radio("Selecione a resposta:", opts, key=f"quiz_radio_{idx}", label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                if 'mostrar_resposta' not in quiz or not quiz['mostrar_resposta']:
                    if st.button(get_text("check_button", language), key=f"quiz_check_{idx}"):
                        quiz['mostrar_resposta'] = True
                        quiz['ultimo_resultado'] = (opts.index(resposta) == ans_idx)
                        quiz['ultimo_correto'] = opts[ans_idx]
                        st.rerun()
                else:
                    if st.button(get_text("next_button", language), key=f"quiz_next_{idx}"):
                        resultado_dict = {
                            "palavra": quiz['playlist'][idx]['palavra'], 
                            "tipo_exercicio": id_ex,
                            "acertou": quiz['ultimo_resultado']
                        }
                        quiz.setdefault('resultados_formatados', []).append(resultado_dict)
                        quiz['idx'] += 1
                        quiz['mostrar_resposta'] = False
                        st.rerun()
                    if quiz['ultimo_resultado']: st.success(get_text("correct_answer", language))
                    else: st.error(get_text("incorrect_answer", language).format(correct=quiz['ultimo_correto']))
            with col_btn2:
                if st.button(get_text("cancel_quiz", language)):
                    st.session_state.pop('quiz_anki', None)
                    st.rerun()
        else:
            resultados_finais = quiz.get('resultados_formatados', [])
            update_progress_from_quiz(resultados_finais, language)
            
            if 'deactivated_words_notification' in st.session_state:
                deactivated_list = st.session_state['deactivated_words_notification']
                st.success(f"Parabéns! As seguintes palavras foram dominadas e desativadas: {', '.join(deactivated_list)}")
                del st.session_state['deactivated_words_notification']
            
            acertos = sum(1 for r in resultados_finais if r['acertou'])
            erros = len(resultados_finais) - acertos
            score = int(acertos / total * 100) if total > 0 else 0
            
            st.success(get_text("final_result", language).format(correct_count=acertos, error_count=erros, score=score))
            
            historico = get_history(language)
            historico.setdefault("quiz", []).append({
                "data": datetime.datetime.now().isoformat(), 
                "acertos": acertos, 
                "erros": erros,
                "palavras_erradas": [r['palavra'] for r in resultados_finais if not r['acertou']],
                "score": score, 
                "total": total
            })
            save_history(historico, language)
            
            if st.button(get_text("finish_button", language)):
                st.session_state.pop('quiz_anki', None)
                st.rerun()