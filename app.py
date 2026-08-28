import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import PIL.Image
import json
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="FGG.FinBot", page_icon="💰")

# Configuração das categorias
CATEGORIAS = ["Alimentação", "Transporte", "Lazer", "Moradia", "Saúde", "Educação", "Trabalho", "Outros"]

# --- 2. CARREGAR SEGREDOS E CONFIGURAR IA ---
# Definimos o modelo fora de funções para ele ser global
try:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GOOGLE_SHEETS_CREDENTIALS = st.secrets["gcp_service_account"]
    NOME_PLANILHA = st.secrets["nome_planilha"]
    
    genai.configure(api_key=GENAI_API_KEY)
    # Aqui está a correção que fizemos antes:
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Erro nos Secrets: {e}")
    st.stop()

# --- 3. FUNÇÕES DE APOIO ---

def conectar_planilha():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_SHEETS_CREDENTIALS, scope)
        client_gs = gspread.authorize(creds)
        return client_gs.open(NOME_PLANILHA).sheet1
    except Exception as e:
        st.error(f"Erro ao conectar na planilha: {e}")
        return None

def salvar_gasto(dados):
    sheet = conectar_planilha()
    if sheet:
        sheet.append_row([dados['data'], dados['descricao'], dados['categoria'], dados['tipo'], dados['valor']])
        return True
    return False

def consultar_dados():
    sheet = conectar_planilha()
    if sheet:
        return sheet.get_all_records()
    return []

def processar_ia(conteudo, tipo_input="texto"):
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    
    prompt = f"""
    Você é o FGG.FinBot, um assistente financeiro pessoal. Hoje é {data_hoje}.
    Se o usuário enviar um gasto ou ganho, analise e retorne APENAS um JSON no formato:
    {{
        "tipo_acao": "lancamento",
        "data": "DD/MM/AAAA",
        "descricao": "O que foi comprado ou recebido",
        "categoria": "Escolha uma de: {CATEGORIAS}",
        "tipo": "Saída" ou "Entrada",
        "valor": 0.00
    }}
    Se o usuário fizer uma pergunta sobre gastos, analise os dados e responda em:
    {{
        "tipo_acao": "pergunta",
        "mensagem": "Sua resposta amigável e detalhada aqui"
    }}
    Responda SEMPRE em JSON puro.
    """
    
    config = {"response_mime_type": "application/json"}
    
    try:
        if tipo_input == "imagem":
            response = model.generate_content([prompt, conteudo], generation_config=config)
        elif tipo_input == "audio":
            response = model.generate_content([prompt, {"mime_type": "audio/wav", "data": conteudo}], generation_config=config)
        else:
            # Se for pergunta, tenta buscar dados na planilha primeiro
            if any(palavra in conteudo.lower() for palavra in ["quanto", "qual", "resumo", "total", "meus"]):
                historico = consultar_dados()
                conteudo = f"Dados atuais da Planilha: {historico}. Pergunta: {conteudo}"
            response = model.generate_content([prompt, conteudo], generation_config=config)
        
        return json.loads(response.text)
    except Exception as e:
        return {"tipo_acao": "pergunta", "mensagem": f"Erro na IA: {e}"}

# --- 4. INTERFACE ---
st.title("💰 FGG.FinBot")
st.caption("Controle Financeiro com Inteligência Artificial")

# Inputs do Usuário
texto = st.chat_input("Ex: Gastei 45 reais no mercado agora")

col1, col2 = st.columns(2)
with col1:
    foto = st.file_uploader("📸 Nota Fiscal", type=["jpg", "png", "jpeg"])
with col2:
    audio = st.audio_input("🎤 Gravar Gasto")

input_atual = None
tipo_atual = None

# Prioridade de processamento
if foto:
    input_atual = PIL.Image.open(foto)
    tipo_atual = "imagem"
elif audio:
    input_atual = audio.read()
    tipo_atual = "audio"
elif texto:
    input_atual = texto
    tipo_atual = "texto"

if input_atual:
    with st.spinner("O FGG.FinBot está pensando..."):
        res = processar_ia(input_atual, tipo_atual)
        
        if res.get("tipo_acao") == "lancamento":
            st.subheader("Confirmar dados para a planilha:")
            with st.form("confirmar_form"):
                f_data = st.text_input("Data", res.get("data"))
                f_desc = st.text_input("Descrição", res.get("descricao"))
                f_cat = st.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(res.get("categoria")) if res.get("categoria") in CATEGORIAS else 0)
                f_valor = st.number_input("Valor", value=float(res.get("valor")))
                f_tipo = st.radio("Tipo", ["Saída", "Entrada"], index=0 if res.get("tipo") == "Saída" else 1)
                
                if st.form_submit_button("🚀 Salvar na Planilha"):
                    sucesso = salvar_gasto({
                        "data": f_data, "descricao": f_desc, 
                        "categoria": f_cat, "tipo": f_tipo, "valor": f_valor
                    })
                    if sucesso:
                        st.success("Pronto! Dados enviados para a planilha.")
                    else:
                        st.error("Erro ao salvar. Verifique se compartilhou a planilha com o e-mail da conta de serviço.")
        else:
            st.chat_message("assistant").write(res.get("mensagem"))

# Rodapé lateral
st.sidebar.title("Configurações")
if st.sidebar.button("Ver Histórico"):
    st.write(consultar_dados())
