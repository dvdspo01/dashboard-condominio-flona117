import pandas as pd
import plotly.express as px
import streamlit as st 
import streamlit_authenticator as stauth


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
def load_and_process_data(file_path, year):
    """Carrega, limpa e formata os dados de um arquivo CSV para um ano específico."""
    try:
        df = pd.read_csv(file_path, skiprows=4, index_col=0, encoding='utf-8')
    except FileNotFoundError:
        print(f"Aviso: O arquivo para o ano {year} não foi encontrado em '{file_path}'")
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

# Função auxiliar para formatar valores monetários em BRL
def format_currency_brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

