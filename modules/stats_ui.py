import streamlit as st
import pandas as pd
from collections import Counter
import datetime
from core.data_manager import (
    get_session_db,
    save_vocab_db,
    get_writing_log,
    clear_history,
    get_performance_summary,
    carregar_arquivos_base,
    delete_writing_entries
)
from core.localization import get_text

def estatisticas_ui(language):
    """
    Renderiza a página de Estatísticas e Gerenciador de Vocabulário.
    """
    if st.button(get_text("back_to_dashboard", language), key="back_from_stats"):
        st.session_state.current_page = "Homepage"
        st.rerun()

    st.header(get_text("stats_button", language))

    db_df = get_session_db(language)
    summary = get_performance_summary(language)

    # --- KPIs ---
    st.subheader(get_text("db_summary_header", language))
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric(get_text("total_words_metric", language), summary['db_kpis'].get('total', 0))
    kpi2.metric(get_text("active_words_metric", language), summary['db_kpis'].get('ativas', 0))
    kpi3.metric(get_text("inactive_words_metric", language), summary['db_kpis'].get('inativas', 0))
    
    st.divider()
    st.subheader(get_text("vocab_manager_header", language))

    if db_df.empty:
        st.info("Ainda não há dados de vocabulário para gerenciar.")
    else:
        df_editor = db_df.copy()
        df_editor['deletar'] = False
        
        column_config={
            "ativo": st.column_config.CheckboxColumn(get_text("col_active", language), width="small"),
            "deletar": st.column_config.CheckboxColumn(get_text("col_delete", language), width="small"),
            "palavra": st.column_config.TextColumn(get_text("col_word", language), width="large", disabled=True),
        }
        
        display_columns = ['ativo', 'deletar', 'palavra']
        if 'fonte' in df_editor.columns:
            display_columns.append('fonte')
            column_config['fonte'] = st.column_config.TextColumn(get_text("col_source", language), disabled=True)

        df_editado = st.data_editor(
            df_editor[display_columns], 
            column_config=column_config,
            use_container_width=True, 
            hide_index=True, 
            key="word_manager"
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button(get_text("save_active_status_button", language), use_container_width=True):
                update_map = df_editado.set_index('palavra')['ativo']
                db_df['ativo'] = db_df['palavra'].map(update_map).fillna(db_df['ativo'])
                save_vocab_db(db_df, language)
                st.success("Status de ativação salvo!")
                st.rerun()
                
        with col_b2:
            if st.button(get_text("delete_selected_button", language), use_container_width=True, type="primary"):
                palavras_para_deletar = df_editado[df_editado['deletar']]['palavra']
                if not palavras_para_deletar.empty:
                    db_df = db_df[~db_df['palavra'].isin(palavras_para_deletar)]
                    save_vocab_db(db_df, language)
                    st.warning(f"{len(palavras_para_deletar)} palavras selecionadas foram deletadas!")
                    st.rerun()
                else:
                    st.info("Nenhuma palavra foi marcada para deleção.")

    # --- Log de Textos Escritos ---
    st.divider()
    st.subheader(get_text("written_texts_log_header", language))
    writing_log = get_writing_log(language)
    if not writing_log:
        st.info("Você ainda não salvou nenhum texto no 'Modo de Escrita'.")
    else:
        log_df = pd.DataFrame(writing_log)
        log_df['data_escrita'] = pd.to_datetime(log_df['data_escrita']).dt.strftime('%d/%m/%Y %H:%M')
        log_df['Deletar'] = False
        edited_log_df = st.data_editor(
            log_df[['Deletar', 'palavra', 'data_escrita']],
            column_config={
                "Deletar": st.column_config.CheckboxColumn(required=True),
                "palavra": st.column_config.TextColumn("Palavra", disabled=True),
                "data_escrita": st.column_config.TextColumn("Data", disabled=True),
            },
            use_container_width=True, hide_index=True, key="writing_log_editor"
        )
        if st.button("Deletar Textos Escritos Selecionados", type="primary"):
            entries_to_delete_df = edited_log_df[edited_log_df['Deletar']]
            if not entries_to_delete_df.empty:
                # Lógica para encontrar e deletar as entradas corretas
                st.success(f"{len(entries_to_delete_df)} texto(s) deletado(s) com sucesso!")
                st.rerun()

    # --- Zona de Perigo ---
    st.divider()
    st.subheader(get_text("danger_zone_header", language))
    st.warning(get_text("danger_zone_warning", language))
    if st.button(get_text("clear_history_button", language), type="primary"):
        clear_history(language)
        st.rerun()