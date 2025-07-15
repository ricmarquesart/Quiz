import streamlit as st
import random
import re
import datetime
from collections import defaultdict
from core.data_manager import (
    get_session_db,
    update_progress_from_quiz,
    save_history,
    get_history,
    carregar_arquivos_base
)
from core.quiz_logic import selecionar_questoes_gpt
from core.localization import get_text

def gpt_ex_ui(language, debug_mode):
    """
    Renderiza a página do Quiz GPT, com depuração, tradução e tratamento de erros para novos utilizadores.
    """
    # --- Carregamento de Dados ---
    _, gpt_exercicios = carregar_arquivos_base(language)
    db_df = get_session_db(language)

    # --- Botão de Voltar ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_gpt"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('gpt_ex_quiz', None)
        st.rerun()

    st.header(get_text("gpt_quiz_title", language))
    
    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if db_df.empty or 'ativo' not in db_df.columns:
        st.warning("A sua base de vocabulário está a ser sincronizada. Por favor, ative algumas palavras na página 'Estatísticas & Gerenciador' para começar.")
        return

    gpt_exercicios_filtrados = [ex for ex in gpt_exercicios if 'cloze_text' not in ex]
    palavras_ativas = db_df[db_df['ativo'] == True]
    
    gpt_exercicios_map = defaultdict(list)
    for ex in gpt_exercicios_filtrados:
        if ex.get('principal'):
            gpt_exercicios_map[ex['principal']].append(ex)

    # --- Modo de Depuração ---
    if debug_mode:
        st.subheader(f"Modo de Depuração Detalhado ({get_text('gpt_quiz_button', language)})")
        st.write("---")
        st.markdown(f"**1. Dados de Entrada:**")
        st.write(f"- Total de exercícios GPT (bruto, incluindo cloze): `{len(gpt_exercicios)}`")
        st.write(f"- Exercícios GPT (padrão) recebidos: `{len(gpt_exercicios_filtrados)}`")
        
        st.markdown(f"**2. Palavras Ativas:**")
        st.write(f"- Total de palavras ativas encontradas: `{len(palavras_ativas)}`")

        st.markdown(f"**3. Mapeamento de Exercícios:**")
        st.write(f"- Total de palavras com exercícios GPT mapeados: `{len(gpt_exercicios_map)}`")

        palavras_prontas = sorted([p for p in gpt_exercicios_map if p in set(palavras_ativas['palavra'].values)])
        st.markdown(f"**4. Cruzamento de Dados:**")
        st.write(f"- Total de palavras ativas que possuem exercícios GPT: `{len(palavras_prontas)}`")

        st.markdown("#### 5. Diagnóstico Final")
        if not gpt_exercicios_filtrados:
            st.error("PROBLEMA CENTRAL: Nenhum exercício GPT foi carregado.")
        elif not palavras_prontas:
            st.error("PROBLEMA CENTRAL: Nenhuma de suas palavras ativas tem um exercício GPT correspondente.")
        else:
            st.success("SUCESSO NA DEPURAÇÃO: A playlist deve ser gerada corretamente.")
        st.divider()

    if palavras_ativas.empty or not gpt_exercicios_map:
        st.warning(get_text("no_active_words", language))
        return

    # --- Lógica Principal do Quiz ---
    if 'gpt_ex_quiz' not in st.session_state:
        st.session_state.gpt_ex_quiz = {}

    if not st.session_state.gpt_ex_quiz.get('started', False):
        with st.form("gpt_ex_cfg"):
            tipos_disponiveis = sorted(list(set(ex['tipo'] for ex_list in gpt_exercicios_map.values() for ex in ex_list)))
            tipos_exibidos = ["Random"] + tipos_disponiveis
            tipo_escolhido = st.selectbox(get_text("choose_exercise_type", language), tipos_exibidos)
            
            palavras_unicas_disponiveis = sorted([p for p in gpt_exercicios_map if p in set(palavras_ativas['palavra'].values)])
            
            if not palavras_unicas_disponiveis:
                st.warning("Nenhuma de suas palavras ativas possui exercícios GPT disponíveis.")
                st.form_submit_button(get_text("start_exercises", language), disabled=True)
            else:
                max_palavras = len(palavras_unicas_disponiveis)
                n_palavras = st.number_input(get_text("how_many_unique_words", language), 1, max_palavras, min(10, max_palavras), 1)
                repetir_palavra = st.radio(
                    get_text("allow_word_repetition", language), 
                    (get_text("option_no", language), get_text("option_yes", language)), 
                    index=0,
                    help=f"{get_text('repetition_help_no', language)} {get_text('repetition_help_yes', language)}"
                )

                if st.form_submit_button(get_text("start_exercises", language)):
                    playlist = selecionar_questoes_gpt(palavras_ativas, gpt_exercicios_map, tipo_escolhido, n_palavras, repetir_palavra == get_text("option_yes", language))
                    
                    if not playlist:
                        st.error(get_text("no_valid_questions", language))
                    else:
                        st.session_state.gpt_ex_quiz = {'started': True, 'playlist': playlist, 'idx': 0, 'resultados_formatados': [], 'show': False}
                        st.rerun()
    else:
        quiz_state = st.session_state.gpt_ex_quiz
        playlist = quiz_state.get('playlist', [])
        idx = quiz_state.get('idx', 0)
        
        if not quiz_state.get('started') or not playlist:
             st.warning("O quiz não pôde ser iniciado. Retornando à configuração.")
             st.session_state.pop('gpt_ex_quiz', None)
             st.rerun()

        total = len(playlist)
        if idx < total:
            ex = playlist[idx]
            tipo = ex.get('tipo')
            pergunta = ex.get('frase')
            opts_originais = ex.get('opcoes', [])
            correta = ex.get('correta')
            keyword = ex.get('principal')
            cefr_level = ex.get('cefr_level')
            
            # O resto da sua lógica de UI e de quiz...

        else:
            # Lógica da tela de resultados...
            resultados_finais = quiz_state.get('resultados_formatados', [])
            update_progress_from_quiz(resultados_finais, language)
            
            acertos = sum(1 for r in resultados_finais if r['acertou'])
            erros = len(resultados_finais) - acertos
            score = int(acertos / total * 100) if total > 0 else 0
            st.success(get_text("final_result", language).format(correct_count=acertos, error_count=erros, score=score))
            
            historico = get_history(language)
            historico.setdefault("gpt_quiz", []).append({
                "data": datetime.datetime.now().isoformat(), 
                "acertos": acertos, "erros": erros, "score": score, "total": total,
                "palavras_erradas": [r['palavra'] for r in resultados_finais if not r['acertou']]
            })
            save_history(historico, language)
            
            if st.button(get_text("finish_button", language)): 
                st.session_state.pop('gpt_ex_quiz', None)
                st.rerun()