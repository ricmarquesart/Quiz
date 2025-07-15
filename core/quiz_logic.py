import random
from collections import defaultdict
from core.data_manager import TIPOS_EXERCICIO_ANKI

def get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map):
    """
    Verifica e retorna todos os tipos de exercícios disponíveis para uma única palavra.
    """
    exercicios_disponiveis = {}
    
    # Verifica exercícios tipo ANKI
    if palavra in flashcards_map:
        for tipo_anki_id, tipo_anki_nome in TIPOS_EXERCICIO_ANKI.items():
            exercicios_disponiveis[tipo_anki_id] = tipo_anki_nome
            
    # Verifica exercícios tipo GPT
    if palavra in gpt_exercicios_map:
        for exercicio_gpt in gpt_exercicios_map[palavra]:
            for key in exercicio_gpt:
                # Uma heurística para identificar um sub-dicionário de exercício
                if isinstance(exercicio_gpt[key], dict) and 'pergunta' in exercicio_gpt[key]:
                     exercicios_disponiveis[key] = key

    return exercicios_disponiveis


def selecionar_questoes_priorizadas(palavras_df, flashcards_map, gpt_exercicios_map, num_questoes, tipo_exercicio="Random"):
    """
    Seleciona questões priorizando palavras com erros ou não testadas, agora de forma segura.
    """
    playlist = []
    candidatos = []

    # --- CORREÇÃO DEFINITIVA PARA KEYERROR ---
    if palavras_df.empty or 'ativo' not in palavras_df.columns:
        return [] # Retorna uma lista vazia se não houver dados para processar

    palavras_ativas = palavras_df[palavras_df['ativo'] == True].copy()
    
    if palavras_ativas.empty:
        return []

    for _, row in palavras_ativas.iterrows():
        palavra = row['palavra']
        progresso = row.get('progresso', {})
        
        exercicios_disponiveis = get_available_exercise_types_for_word(palavra, flashcards_map, gpt_exercicios_map)

        for id_exercicio, tipo_gen in exercicios_disponiveis.items():
            if tipo_exercicio == "Random" or tipo_gen == tipo_exercicio:
                status = progresso.get(id_exercicio, 'nao_testado')
                prioridade = {'erro': 0, 'nao_testado': 1, 'acerto': 2}.get(status, 2)
                candidatos.append({'palavra': palavra, 'tipo_exercicio': tipo_gen, 'identificador': id_exercicio, 'prioridade': prioridade})

    if not candidatos:
        return []
        
    candidatos.sort(key=lambda x: x['prioridade'])
    
    num_a_selecionar = min(num_questoes, len(candidatos))
    playlist = candidatos[:num_a_selecionar]
    random.shuffle(playlist)
    
    return playlist


def gerar_questao_dinamica(item_playlist, flashcards_map, gpt_map, db_df):
    """
    Gera uma pergunta e opções dinamicamente com base no tipo de exercício.
    """
    palavra = item_playlist['palavra']
    tipo = item_playlist['tipo_exercicio']
    id_ex = item_playlist['identificador']
    
    pergunta, opts, ans_idx, cefr = "", [], None, "N/A"
    
    word_info_series = db_df[db_df['palavra'] == palavra]
    if not word_info_series.empty:
        word_info = word_info_series.iloc[0]
        cefr = word_info.get('cefr', 'N/A')

    # Lógica para exercícios ANKI
    if tipo in TIPOS_EXERCICIO_ANKI.values():
        card = flashcards_map.get(palavra)
        if not card: return None, None, None, None, None, None

        outras_palavras = list(flashcards_map.keys())
        outras_palavras.remove(palavra)
        distracoes = random.sample(outras_palavras, min(3, len(outras_palavras)))
        
        resposta_correta = None
        opcoes_distracao = []

        if tipo == "gerar_mcq_significado":
            pergunta = f"Qual o significado de **{palavra}**?"
            resposta_correta = card.get('significado')
            opcoes_distracao = [flashcards_map[d].get('significado') for d in distracoes]
        elif tipo == "gerar_mcq_traducao_ingles":
            pergunta = f"Qual a tradução de **{palavra}**?"
            resposta_correta = card.get('tradução')
            opcoes_distracao = [flashcards_map[d].get('tradução') for d in distracoes]
        
        if resposta_correta:
            opts = [resposta_correta] + [opt for opt in opcoes_distracao if opt]
            opts = list(dict.fromkeys(opts)) # Garante que as opções são únicas
            while len(opts) < 4 and outras_palavras:
                palavra_extra = random.choice(outras_palavras)
                outras_palavras.remove(palavra_extra)
                distracao_extra = flashcards_map[palavra_extra].get('significado' if 'significado' in tipo else 'tradução')
                if distracao_extra and distracao_extra not in opts:
                    opts.append(distracao_extra)

            random.shuffle(opts)
            ans_idx = opts.index(resposta_correta)

    # Lógica para exercícios GPT
    else:
        exercicios_da_palavra = gpt_map.get(palavra, [])
        exercicio_especifico = next((ex.get(id_ex) for ex in exercicios_da_palavra if id_ex in ex), None)

        if exercicio_especifico:
            pergunta = exercicio_especifico.get('pergunta')
            opts = exercicio_especifico.get('opcoes', [])
            resposta_correta_str = exercicio_especifico.get('resposta')
            if resposta_correta_str and opts:
                try:
                    ans_idx = opts.index(resposta_correta_str)
                except ValueError:
                    ans_idx = None

    return tipo, pergunta, opts, ans_idx, cefr, id_ex

def selecionar_questoes_gpt(palavras_df, gpt_exercicios_map, tipo_exercicio, n_palavras, repetir_palavra):
    """
    Seleciona questões especificamente do pool GPT.
    """
    if palavras_df.empty or 'palavra' not in palavras_df.columns:
        return []

    palavras_disponiveis = [p for p in gpt_exercicios_map if p in set(palavras_df['palavra'].values)]
    if not palavras_disponiveis:
        return []

    palavras_selecionadas = random.sample(palavras_disponiveis, min(n_palavras, len(palavras_disponiveis)))
    
    playlist = []
    for palavra in palavras_selecionadas:
        exercicios_da_palavra = gpt_exercicios_map[palavra]
        
        exercicios_candidatos = []
        for ex in exercicios_da_palavra:
            if tipo_exercicio == "Random":
                for k, v in ex.items():
                    if isinstance(v, dict) and 'pergunta' in v:
                        exercicios_candidatos.append(v)
            else:
                 if tipo_exercicio in ex and isinstance(ex[tipo_exercicio], dict):
                     exercicios_candidatos.append(ex[tipo_exercicio])
        
        if not exercicios_candidatos:
            continue
            
        if repetir_palavra:
            playlist.extend(exercicios_candidatos)
        else:
            playlist.append(random.choice(exercicios_candidatos))
            
    random.shuffle(playlist)
    return playlist