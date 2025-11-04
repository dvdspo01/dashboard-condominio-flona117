import pandas as pd
import plotly.express as px
import streamlit as st 
import streamlit_authenticator as stauth
import os, requests, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import Flow
from google_auth_oauthlib.flow import InstalledAppFlow
import requests, unicodedata


OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')  # Use 'helloworld' para testes gratuitos


# --- 1. Carregamento e Limpeza dos Dados ---



def clean_currency(value, default=0.0):
    """Limpa e converte um valor para float, tratando strings monetárias (R$)."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        # Converte para string para garantir que os métodos .replace funcionem
        cleaned_value = str(value).replace('R$', '').strip().replace('.', '').replace(',', '.')
        return float(cleaned_value)
    except (ValueError, TypeError):
        return default

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

    # 1. Limpeza básica no DataFrame original (remove apenas linhas/colunas TOTALMENTE vazias)
    df.dropna(axis=1, how='all', inplace=True) # Remove colunas (meses) totalmente vazias
    df.dropna(axis=0, how='all', inplace=True) # Remove linhas (categorias) totalmente vazias

    
    # Debut de tabelas de valores 
    # print("DataFrame original antes da transposição:")
    # print(df.head())

    # # 2. Transpõe o DataFrame para ter os meses como linhas
    df_transposed = df.T
    
    # print("DataFrame transposto:")
    # print(df_transposed.head())
    

    # 3. Aplica a conversão de moeda APÓS a transposição
    #df_transposed = df_transposed.map(clean_currency)
    # Identifica as colunas de valores (exclui 'index' e 'Mês')
    for col in df_transposed.columns:
        df_transposed[col] = df_transposed[col].apply(clean_currency)

    
    df_transposed.reset_index(inplace=True) # Converte o índice em uma coluna chamada 'index'
    df_transposed.rename(columns={'index': 'Mês'}, inplace=True) # Renomeia a coluna 'index' para 'Mês'
    df_transposed['Ano'] = year
    
    # --- Criação da Coluna 'Período' e 'sort_date' ---
    # Mapeia nomes de meses em português para número do mês para uma ordenação robusta
    meses_map = {
        'JANEIRO': 1, 'FEVEREIRO': 2, 'MARCO': 3, 'ABRIL': 4, 'MAIO': 5, 'JUNHO': 6,
        'JULHO': 7, 'AGOSTO': 8, 'SETEMBRO': 9, 'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12
    }
    # Extrai apenas o nome do mês da coluna 'Mês', ignorando qualquer coisa após '/'
    month_names_only = df_transposed['Mês'].apply(normalize_month_name)
    

    # 4. Tenta mapear os meses para números.
    df_transposed['month_num'] = month_names_only.map(meses_map)

    # 5. Identifica e avisa sobre meses inválidos que não puderam ser mapeados.
    invalid_months = df_transposed[df_transposed['month_num'].isna()]
    if not invalid_months.empty:
        invalid_month_names = invalid_months['Mês'].unique()
        st.warning(
            f"**Aviso de Dados:** Os seguintes meses na aba '{sheet_name}' não foram reconhecidos e serão ignorados: "
            f"`{', '.join(invalid_month_names)}`. Verifique se há erros de digitação ou colunas extras na planilha."
        )
        # Remove as linhas com meses inválidos para evitar que o app quebre.
        df_transposed.dropna(subset=['month_num'], inplace=True)

    # 6. Cria as colunas de data e período apenas com os dados válidos.
    df_transposed['sort_date'] = pd.to_datetime(df_transposed['Ano'].astype(str) + '-' + df_transposed['month_num'].astype(int).astype(str))
    df_transposed['Período'] = df_transposed['sort_date'].dt.strftime('%b-%Y').str.capitalize()
    
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

def normalize_month_name(name):
    name = str(name).split('/')[0].strip()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return name.upper()


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
