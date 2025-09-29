import pandas as pd
import plotly.express as px
import streamlit as st 
import streamlit_authenticator as stauth
import os, requests, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import Flow
from google_auth_oauthlib.flow import InstalledAppFlow


OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')  # Use 'helloworld' para testes gratuitos


# --- 1. Carregamento e Limpeza dos Dados ---



def clean_currency(value):
    """Função para limpar e converter valores monetários para float."""
    if isinstance(value, str):
        # Remove 'R$', espaços, e o separador de milhar '.'
        value = value.replace('R$', '').strip().replace('.', '')
        # Substitui a vírgula decimal por ponto
        value = value.replace(',', '.')
        # Converte para float, tratando valores vazios ou inválidos
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    return float(value) if value else 0.0

@st.cache_data # Cache the data loading and processing
def load_and_process_data(excel_path, sheet_name, year):
    """Carrega, limpa e formata os dados de uma aba (ano) de um arquivo Excel."""
    try:
        # Lê uma aba específica do arquivo Excel. O nome da aba deve ser o ano.
        df = pd.read_excel(excel_path, sheet_name=sheet_name, skiprows=4, index_col=0)
    except FileNotFoundError:
        print(f"Aviso: O arquivo Excel não foi encontrado em '{excel_path}'")
        return None
    except ValueError as e: # Captura erro se a aba não for encontrada
        print(f"Aviso: A aba '{sheet_name}' não foi encontrada no arquivo. Erro: {e}")
        return None

    # Limpeza básica
    df.dropna(axis=1, how='all', inplace=True)
    df.dropna(axis=0, how='all', inplace=True)
    df = df.map(clean_currency)

    # Transpõe o DataFrame para ter os meses como linhas (índice)
    df_transposed = df.T
    df_transposed.index.name = 'Mês' # Define o nome do índice
    df_transposed.reset_index(inplace=True) # Converte o índice 'Mês' em uma coluna
    df_transposed['Ano'] = year
    
    # Cria uma coluna 'Periodo' para usar no eixo X dos gráficos (ex: 'JAN-2024')
    # Garante que o índice 'Mês' seja string para o fatiamento
    df_transposed['Período'] = df_transposed['Mês'].astype(str).str.slice(0, 3) + '-' + df_transposed['Ano'].astype(str)
    
    return df_transposed



# def upload_comprovante_google_drive(local_path, nome_arquivo, folder_id=None):
#     # Reconstrói o token a partir do base64
#     token_bytes = base64.b64decode(st.secrets["google_drive"]["token_b64"])
#     creds = pickle.loads(token_bytes)

#     service = build('drive', 'v3', credentials=creds)

#     file_metadata = {'name': nome_arquivo}
#     if folder_id:
#         file_metadata['parents'] = [folder_id]

#     media = MediaFileUpload(local_path, resumable=True)
#     file = service.files().create(
#         body=file_metadata,
#         media_body=media,
#         fields='id, webViewLink'
#     ).execute()

#     return file.get('webViewLink')


# Função auxiliar para formatar valores monetários em BRL
def format_currency_brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


import requests

def ocr_space_api(file_path, api_key='helloworld'):
    with open(file_path, 'rb') as f:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': f},
            data={'apikey': api_key, 'language': 'por'}
        )
        

    try:
        result = response.json()
    except Exception as e:
        raise Exception(f"Erro ao interpretar resposta da API: {e}")

    if isinstance(result, dict):
        if result.get("IsErroredOnProcessing"):
            raise Exception(result.get("ErrorMessage", "Erro desconhecido na API OCR"))
        return result['ParsedResults'][0]['ParsedText']
    else:
        raise Exception("Resposta inesperada da API OCR: não é um JSON válido")
    

def formatar_mes_em_portugues(data_obj):
    meses_pt = {
        "January": "Janeiro", "February": "Fevereiro", "March": "Março",
        "April": "Abril", "May": "Maio", "June": "Junho",
        "July": "Julho", "August": "Agosto", "September": "Setembro",
        "October": "Outubro", "November": "Novembro", "December": "Dezembro"
    }
    mes_en = data_obj.strftime("%B")
    return f"{meses_pt.get(mes_en, mes_en)} {data_obj.year}"






def upload_comprovante_google_drive(local_path, nome_arquivo, folder_id=None):
    st.write("🔄 Iniciando reconstrução do token...")
    token_bytes = base64.b64decode(st.secrets["google_drive"]["token_b64"])
    creds = pickle.loads(token_bytes)

    st.write("✅ Token reconstruído. Conectando ao Google Drive...")
    service = build('drive', 'v3', credentials=creds)

    st.write("📁 Preparando metadados do arquivo...")
    file_metadata = {'name': nome_arquivo}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    st.write("📤 Iniciando upload...")
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    st.write("✅ Upload concluído.")
    return file.get('webViewLink')

