import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import PIL.Image
import json
from datetime import datetime

# Configurações de Página
st.set_page_config(page_title="FGG.FinBot", page_icon="💰")

# --- CARREGAR SEGREDOS ---
try:
    GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GOOGLE_SHEETS_CREDENTIALS = st.secrets["gcp_service_account"]
    NOME_PLANILHA = st.secrets["nome_planilha"]
    genai.configure(api_key=GENAI_API_KEY)
    genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("Configure os Secrets no Streamlit Cloud.")
    st.stop()

CATEGORIAS = ["Alimentação", "Transporte", "Lazer", "Moradia", "Saúde", "Educação", "Trabalho", "Outros"]

def conectar_planilha():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_SHEETS_CREDENTIALS, scope)
    client_gs = gspread.authorize(creds)
    return client_gs.open(NOME_PLANILHA).sheet1

def salvar_gasto(dados):
    sheet = conectar_planilha()
    sheet.append_row([dados['data'], dados['descricao'], dados['categoria'], dados['tipo'], dados['valor']])
    return "✅ Lançado no FGG.FinBot!"

def consultar_dados():
    sheet = conectar_planilha()
    return sheet.get_all_records()

def processar_ia(conteudo, tipo_input="texto"):
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""
    Você é o FGG.FinBot, um assistente financeiro. Hoje é {data_hoje}.
    Se o usuário enviar um gasto ou ganho, retorne APENAS um JSON:
    {{"tipo_acao": "lancamento", "data": "DD/MM/AAAA", "descricao": "...", "categoria": "{CATEGORIAS}", "tipo": "Saída/Entrada", "valor": 0.00}}
    Se for uma pergunta sobre gastos, analise os dados e responda em:
    {{"tipo_acao": "pergunta", "mensagem": "sua resposta"}}
    """
    config = {"response_mime_type": "application/json"}
    
    if tipo_input == "imagem":
        response = model.generate_content([prompt, conteudo], generation_config=config)
    elif tipo_input == "audio":
        response = model.generate_content([prompt, {"mime_type": "audio/wav", "data": conteudo}], generation_config=config)
    else:
        if any(word in conteudo.lower() for word in ["quanto", "qual", "resumo", "total"]):
            dados = consultar_dados()
            conteudo = f"Dados da Planilha: {dados}. Pergunta: {conteudo}"
        response = model.generate_content([prompt, conteudo], generation_config=config)
    
    return json.loads(response.text)

# --- INTERFACE ---
st.title("💰 FGG.FinBot")
st.caption("Seu Assistente Financeiro Inteligente")

# Inputs
texto = st.chat_input("Diga o que gastou ou pergunte algo...")
col1, col2 = st.columns(2)
with col1:
    foto = st.file_uploader("📸 Nota Fiscal", type=["jpg", "png", "jpeg"])
with col2:
    audio = st.audio_input("🎤 Áudio")

input_atual = None
tipo_atual = None

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
    with st.spinner("Analisando..."):
        res = processar_ia(input_atual, tipo_atual)
        if res.get("tipo_acao") == "lancamento":
            with st.form("confirmar"):
                d = st.text_input("Data", res.get("data"))
                desc = st.text_input("Descrição", res.get("descricao"))
                cat = st.selectbox("Categoria", CATEGORIAS, index=0)
                val = st.number_input("Valor", value=float(res.get("valor")))
                t = st.radio("Tipo", ["Saída", "Entrada"])
                if st.form_submit_button("Confirmar no FGG.FinBot"):
                    salvar_gasto({"data": d, "descricao": desc, "categoria": cat, "tipo": t, "valor": val})
                    st.success("Lançado!")
        else:
            st.chat_message("assistant").write(res.get("mensagem"))
