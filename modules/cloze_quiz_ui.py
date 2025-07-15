import streamlit as st
import re
from core.data_manager import carregar_arquivos_base # <--- IMPORTANTE
from core.localization import get_text

def cloze_quiz_ui(language, debug_mode): # <--- MUDANÇA 1
    """
    Renderiza a página interativa do Cloze Quiz, agora carregando seus próprios dados.
    """
    # --- PASSO 1: Carregar os dados necessários ---
    _, gpt_exercicios = carregar_arquivos_base(language) # Ignora flashcards, usa apenas gpt_exercicios

    # --- Botão de Voltar ---
    if st.button(get_text("back_to_dashboard", language), key="back_from_cloze"):
        st.session_state.current_page = "Homepage"
        st.session_state.pop('cloze_quiz', None)
        st.rerun()

    st.header(get_text("cloze_quiz_button", language))

    # --- Lógica Principal (usa os dados carregados acima) ---
    cloze_exercises = [ex for ex in gpt_exercicios if 'texto_cloze' in ex]

    # --- MODO DE DEPURAÇÃO ROBUSTO ---
    if debug_mode:
        st.subheader(f"Modo de Depuração Detalhado ({get_text('cloze_quiz_button', language)})")
        st.write("---")
        st.markdown(f"**1. Dados de Entrada:**")
        st.write(f"- Total de exercícios GPT/Cloze recebidos (bruto): `{len(gpt_exercicios)}`")
        st.write(f"- Exercícios com 'texto_cloze' encontrados após o filtro: `{len(cloze_exercises)}`")
        
        parsing_errors = st.session_state.get(f'parsing_errors_{language}', [])
        if any("Cloze" in error for error in parsing_errors):
            st.error("Erros detectados durante o carregamento do arquivo Cloze:")
            for error in parsing_errors:
                if "Cloze" in error: st.code(error)

        st.markdown("#### 2. Diagnóstico Final")
        if not gpt_exercicios:
             st.error("PROBLEMA DE CARREGAMENTO: Nenhum exercício GPT ou Cloze foi carregado.")
        elif not cloze_exercises:
            st.error("PROBLEMA DE DADOS: Nenhum exercício com 'texto_cloze' foi encontrado nos dados carregados. Verifique o arquivo `Dados_Manual_Cloze_text.txt`.")
        else:
            st.success("SUCESSO NA DEPURAÇÃO: Pelo menos um exercício Cloze foi carregado corretamente.")
        st.divider()

    if not cloze_exercises:
        st.warning(get_text("no_cloze_exercises_found", language))
        return

    # A lógica de seleção e exibição do quiz permanece a mesma...
    nomes_exibicao = [ex.get('palavra', f"Texto Cloze #{i+1}") for i, ex in enumerate(cloze_exercises)]
    
    texto_selecionado_nome = st.selectbox(
        get_text("select_cloze_text", language),
        nomes_exibicao
    )
    
    exercicio_escolhido = next((ex for ex in cloze_exercises if ex.get('palavra') == texto_selecionado_nome), None)

    if not exercicio_escolhido:
        st.error("Não foi possível encontrar o exercício selecionado. Por favor, recarregue a página.")
        return

    # Extrai os dados do exercício escolhido
    texto_original = exercicio_escolhido.get('texto_cloze', '')
    
    # Extrai as respostas e as opções do texto
    respostas_corretas = re.findall(r'\[(.*?)\]', texto_original)
    opcoes_disponiveis = respostas_corretas.copy()
    random.shuffle(opcoes_disponiveis)
    
    # Prepara o texto com placeholders
    texto_com_gaps = re.sub(r'\[(.*?)\]', '[GAP]', texto_original)
    num_gaps = texto_com_gaps.count('[GAP]')

    # Inicializa o estado do quiz
    quiz_id = texto_selecionado_nome
    if 'cloze_quiz' not in st.session_state or st.session_state.cloze_quiz.get('id') != quiz_id:
        st.session_state.cloze_quiz = {
            'id': quiz_id,
            'texto_com_gaps': texto_com_gaps,
            'respostas_corretas': respostas_corretas,
            'opcoes': opcoes_disponiveis,
            'respostas_usuario': {}, 
            'submetido': False
        }
    
    quiz_state = st.session_state.cloze_quiz
    
    st.info(get_text("cloze_info", language))
    
    respostas_usuario = quiz_state.get('respostas_usuario', {})
    placeholder = "---"
    
    colunas_gaps = st.columns(num_gaps)
    
    for i in range(num_gaps):
        gap_key = f"gap_{i}"
        with colunas_gaps[i]:
            opcoes_usadas = [v for k, v in respostas_usuario.items() if k != gap_key and v != placeholder]
            opcoes_para_este_gap = [placeholder] + [opt for opt in quiz_state['opcoes'] if opt not in opcoes_usadas]
            
            selecao_atual = respostas_usuario.get(gap_key, placeholder)
            indice_selecao = opcoes_para_este_gap.index(selecao_atual) if selecao_atual in opcoes_para_este_gap else 0
            
            respostas_usuario[gap_key] = st.selectbox(f"GAP {i+1}", opcoes_para_este_gap, index=indice_selecao, key=f"cloze_select_{gap_key}")

    # Monta o texto para exibição
    texto_renderizado = quiz_state['texto_com_gaps']
    submetido = quiz_state.get('submetido', False)

    for i in range(num_gaps):
        gap_key = f"gap_{i}"
        resposta_selecionada = respostas_usuario.get(gap_key, placeholder)
        
        if submetido:
            if resposta_selecionada == quiz_state['respostas_corretas'][i]:
                texto_renderizado = texto_renderizado.replace('[GAP]', f"<span style='color: green; font-weight: bold;'>{resposta_selecionada}</span>", 1)
            else:
                texto_exibido = resposta_selecionada if resposta_selecionada != placeholder else f"[{quiz_state['respostas_corretas'][i]}]"
                texto_renderizado = texto_renderizado.replace('[GAP]', f"<span style='color: red; font-weight: bold;'>{texto_exibido}</span>", 1)
        else:
            if resposta_selecionada != placeholder:
                texto_renderizado = texto_renderizado.replace('[GAP]', f"<span style='color: blue; font-weight: bold;'>{resposta_selecionada}</span>", 1)
            else:
                texto_renderizado = texto_renderizado.replace('[GAP]', f"<span style='color: red;'>[GAP]</span>", 1)
    
    st.markdown(f"<div style='font-size: 1.2em; line-height: 2;'>{texto_renderizado}</div>", unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns(2)
    if col1.button(get_text("check_answers_button", language), type="primary", use_container_width=True, disabled=submetido):
        quiz_state['submetido'] = True
        st.rerun()
    if col2.button(get_text("clear_answers_button", language), use_container_width=True):
        quiz_state['respostas_usuario'] = {}
        quiz_state['submetido'] = False
        st.rerun()

    if submetido:
        acertos = sum(1 for i in range(num_gaps) if respostas_usuario.get(f"gap_{i}") == quiz_state['respostas_corretas'][i])
        score = (acertos / num_gaps * 100) if num_gaps > 0 else 0
        st.success(f"Resultado: {acertos}/{num_gaps} acertos ({score:.0f}%)")
        if st.button(get_text("practice_another_text_button", language)):
            st.session_state.pop('cloze_quiz', None)
            st.rerun()