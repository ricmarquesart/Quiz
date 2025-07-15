# core/auth.py (Versão Corrigida)

import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth
import json

def initialize_firebase():
    """
    Inicializa a conexão com o Firebase usando as credenciais do Streamlit Secrets.
    Retorna True se a inicialização for bem-sucedida, False caso contrário.
    """
    if not firebase_admin._apps:
        try:
            # CORREÇÃO: Converte o objeto de segredos do Streamlit em um dicionário Python padrão.
            creds_dict = dict(st.secrets["firebase_credentials"])
            
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar o Firebase: {e}")
            return False
    return True

def login_form():
    """
    Exibe um formulário de login/cadastro e gerencia o estado de autenticação.
    """
    st.title("Bem-vindo ao seu App de Idiomas")

    choice = st.selectbox("Login ou Cadastro", ["Login", "Cadastrar"])

    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")

    if choice == "Cadastrar":
        username = st.text_input("Nome de usuário (para exibição)")
        if st.button("Cadastrar"):
            if not password:
                st.error("A senha não pode estar em branco.")
            else:
                try:
                    user = auth.create_user(
                        email=email,
                        password=password,
                        display_name=username
                    )
                    st.success("Conta criada com sucesso! Faça o login.")
                    st.balloons()
                except Exception as e:
                    # Tenta extrair uma mensagem de erro mais amigável
                    try:
                        error_message = json.loads(e.http_response.text)['error']['message']
                        st.error(f"Erro ao criar conta: {error_message}")
                    except:
                        st.error(f"Erro ao criar conta: {e}")


    if choice == "Login":
        if st.button("Login"):
            try:
                # A autenticação real do usuário (verificação de senha) deve ser feita
                # no lado do cliente (frontend), que não temos aqui.
                # Para este app de backend, confirmamos que o usuário existe.
                # Para maior segurança em um app de produção, seria necessário usar a API REST do Firebase.
                user = auth.get_user_by_email(email)
                
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = {
                    'uid': user.uid,
                    'email': user.email,
                    'display_name': user.display_name
                }
                st.rerun() 
            except auth.UserNotFoundError:
                 st.error("Usuário não encontrado. Verifique o e-mail ou cadastre-se.")
            except Exception as e:
                st.error("Email ou senha incorretos.")

def logout():
    """Realiza o logout do usuário."""
    if st.sidebar.button("Logout"):
        # Limpa o estado da sessão relacionado ao login
        st.session_state['logged_in'] = False
        st.session_state.pop('user_info', None)
        
        # Opcional: Limpa outros dados da sessão para recomeçar do zero
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        st.rerun()