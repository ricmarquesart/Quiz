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
    carregar_arquivos_base # <--- IMPORTANTE: Importamos a nova função
)
from core.quiz_logic import selecionar_questoes_gpt
from core.localization import get_text

def gpt_ex_ui(language, debug_mode): # <--- MUDANÇA 1: Assinatura da função simplificada
    """
    Renderiza a página do Quiz GPT, agora carregando seus próprios dados.
    """
    # --- PASSO 1: Carregar os dados necessários no início ---
    # Carrega a "biblioteca" de perguntas dos arquivos .txt
    _, gpt_exercicios = carregar_arquivos_base(language) # Usamos '_' para ignorar os flashcards que não são usados aqui
    # Carrega o "diário de progresso" do usuário a partir do Firestore
    db_df = get_session_db(language)

    # --- Botão de Voltar ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_gpt"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('gpt_ex_quiz', None)
        st.rerun()

    st.header(get_text("gpt_quiz_title", language))
    
    # --- Lógica Principal do Quiz (praticamente sem alterações) ---
    # O restante do seu código original permanece aqui, pois ele já utiliza
    # as variáveis gpt_exercicios e db_df que carregamos acima.
    
    # Filtra os exercícios para não incluir 'Cloze-Text'
    gpt_exercicios_filtrados = [ex for ex in gpt_exercicios if 'cloze_text' not in ex]

    palavras_ativas = db_df[db_df['ativo'] == True]
    
    # Mapeia os exercícios por palavra-chave
    gpt_exercicios_map = defaultdict(list)
    for ex in gpt_exercicios_filtrados:
        gpt_exercicios_map[ex['palavra']].append(ex)

    if debug_mode:
        st.subheader(f"Modo de Depuração Detalhado ({get_text('gpt_quiz_button', language)})")
        st.write("---")
        st.markdown(f"**1. Dados de Entrada:**")
        st.write(f"- Total de exercícios GPT (bruto, incluindo cloze): `{len(gpt_exercicios)}`")
        st.write(f"- Exercícios GPT (filtrados para quiz) recebidos: `{len(gpt_exercicios_filtrados)}`")
        
        parsing_errors = st.session_state.get(f'parsing_errors_{language}', [])
        if any("GPT" in error or "Cloze" in error for error in parsing_errors):
            st.error("Erros detectados durante o carregamento dos dados GPT:")
            for error in parsing_errors:
                if "GPT" in error or "Cloze" in error: st.code(error)
        
        palavras_ativas_debug = db_df[db_df['ativo']]
        st.markdown(f"**2. Palavras Ativas:**")
        st.write(f"- Total de palavras ativas encontradas: `{len(palavras_ativas_debug)}`")

        st.markdown(f"**3. Mapeamento de Exercícios:**")
        st.write(f"- Total de palavras com exercícios GPT mapeados: `{len(gpt_exercicios_map)}`")

        palavras_prontas = sorted([p for p in gpt_exercicios_map if p in set(palavras_ativas_debug['palavra'].values)])
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

    if 'gpt_ex_quiz' not in st.session_state:
        st.session_state.gpt_ex_quiz = {}

    if not st.session_state.gpt_ex_quiz.get('started', False):
        with st.form("gpt_ex_cfg"):
            # Lógica para obter tipos de exercício disponíveis do mapa
            tipos_disponiveis = set()
            for ex_list in gpt_exercicios_map.values():
                for ex in ex_list:
                    tipos_disponiveis.update(ex.keys())
            
            # Filtra para tipos de exercício conhecidos
            tipos_conhecidos = ["sinonimo_mcq", "antonym_mcq", "definition_mcq", "context_mcq", "fill_in_the_blank_1", "fill_in_the_blank_2"]
            tipos_disponiveis = sorted([t for t in tipos_disponiveis if t in tipos_conhecidos])

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
                        st.session_state.gpt_ex_quiz = {'started': True, 'playlist': playlist, 'idx': 0, 'resultados': [], 'show': False}
                        st.rerun()
    else:
        # A lógica de exibição do quiz permanece a mesma...
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
            
            # Extrair detalhes da questão
            id_exercicio = ex.get('id_exercicio')
            pergunta = ex.get('pergunta')
            opts_originais = ex.get('opcoes', [])
            correta = ex.get('resposta')
            keyword = ex.get('palavra')
            cefr_level = db_df[db_df['palavra'] == keyword]['cefr'].iloc[0] if 'cefr' in db_df.columns else 'N/A'

            # Lógica para garantir 4 opções e embaralhar
            # ... (seu código de manipulação de opções continua aqui)

            # Renderização da UI
            # ... (seu código de st.progress, st.markdown, st.radio, etc. continua aqui)
            
            # --- Bloco de exemplo para renderização (adapte com seu código real) ---
            frase_html = re.sub(rf'{re.escape(keyword)}', f'<span class="keyword-highlight">{keyword}</span>', pergunta, flags=re.IGNORECASE)
            st.markdown(f'<div class="question-bg">{frase_html}</div>', unsafe_allow_html=True)
            
            # O resto da sua lógica de botões 'Check' e 'Next' continua aqui...
            # A lógica de salvar resultados e histórico também continua a mesma.
            # O ponto crucial é que a variável `gpt_exercicios` já está preenchida.
        else:
            # Tela de resultados
            resultados_finais = quiz_state.get('resultados_formatados', [])
            update_progress_from_quiz(resultados_finais, language)

            acertos = sum(1 for r in resultados_finais if r['acertou'])
            erros = len(resultados_finais) - acertos
            score = int(acertos / total * 100) if total > 0 else 0

            st.success(get_text("final_result", language).format(correct_count=acertos, error_count=erros, score=score))
            
            historico = get_history(language)
            historico.setdefault("gpt_quiz", []).append({
                "data": datetime.datetime.now().isoformat(),
                "acertos": acertos,
                "erros": erros,
                "palavras_erradas": [r['palavra'] for r in resultados_finais if not r['acertou']],
                "score": score,
                "total": total
            })
            save_history(historico, language)
            
            if st.button(get_text("finish_button", language)):
                st.session_state.pop('gpt_ex_quiz', None)
                st.rerun()