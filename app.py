import streamlit as st
import pandas as pd
import ssl
from datetime import datetime
import dateutil.parser

ssl._create_default_https_context = ssl._create_unverified_context

# URL of the CSV file
data_url = "https://raw.githubusercontent.com/DCruise1/DataPull/main/stocks.csv"

def robust_parse_date(date_str):
    try:
        # Try to parse with dateutil for flexibility
        return dateutil.parser.parse(date_str, dayfirst=True, fuzzy=True)
    except Exception:
        return pd.NaT

def load_data():
    # Use python engine to better handle malformed lines and embedded newlines
    df = pd.read_csv(data_url, on_bad_lines='skip', engine='python')
    # Fix possible whitespace and multi-line header issues
    df.columns = [col.strip().replace('\n', '').replace(' ', '') for col in df.columns]
    if 'Date' in df.columns:
        df['Date_Original'] = df['Date']
        # Try to parse the original date robustly
        df['Parsed_Date'] = df['Date_Original'].astype(str).apply(robust_parse_date)
        df['Parsed_Date'] = pd.to_datetime(df['Parsed_Date'], errors='coerce', dayfirst=True, infer_datetime_format=True)
    else:
        df['Parsed_Date'] = pd.NaT
    if 'Volume' in df.columns:
        df['Volume'] = pd.to_numeric(df['Volume'].astype(str).str.replace(',', ''), errors='coerce')
    # Ensure AM/PM column exists for logic below
    if 'AM/PM' not in df.columns:
        df['AM/PM'] = ''
    # Only keep necessary columns
    keep_cols = [col for col in ['Symbol', 'Date', 'AM/PM', 'Volume', 'Parsed_Date', 'Date_Original'] if col in df.columns]
    df = df[keep_cols]
    return df

st.set_page_config(page_title="Stock Volume Explorer", layout="centered")

st.title("📈 Stock Volume Explorer")
st.markdown("""
Easily explore stock volume trends for any ticker. Select a symbol to view its volume history and details. Data is always up-to-date from GitHub.
""")

# Add a refresh button
if 'df' not in st.session_state or st.button('🔄 Refresh Data'):
    st.session_state.df = load_data()

df = st.session_state.df

# Ensure correct types
if 'Parsed_Date' in df.columns:
    # Fix possible whitespace and multi-line header issues
    df.columns = [col.strip() for col in df.columns]
    if 'Parsed_Date' not in df.columns and any('Parsed_Date' in col for col in df.columns):
        # Try to fix split header
        df.columns = [col.replace('\n', '').replace(' ', '') for col in df.columns]
    if 'Parsed_Date' in df.columns:
        df['Parsed_Date'] = df['Parsed_Date'].astype(str).str.strip()
        df['Parsed_Date'] = pd.to_datetime(df['Parsed_Date'], errors='coerce', dayfirst=True, infer_datetime_format=True)
if 'Volume' in df.columns:
    df['Volume'] = pd.to_numeric(df['Volume'].astype(str).str.replace(',', ''), errors='coerce')

# Symbol filter (selectbox) - now only for raw data table
symbols = df['Symbol'].dropna().unique()
raw_symbol_options = ['All'] + sorted(symbols)
selected_raw_symbol = st.sidebar.selectbox("Filter Raw Data Table by Symbol", raw_symbol_options)

# --- SUMMARY TABLE: always show all symbols ---
summary_rows = []
for symbol in symbols:
    filtered_df = df[df['Symbol'] == symbol]
    if not filtered_df.empty:
        # Find the most recent date
        max_date = filtered_df['Parsed_Date'].max()
        recent_rows = filtered_df[filtered_df['Parsed_Date'] == max_date]
        # Prefer PM if available, else AM
        if 'PM' in recent_rows['AM/PM'].values:
            most_recent = recent_rows[recent_rows['AM/PM'] == 'PM'].iloc[0]
        else:
            most_recent = recent_rows.iloc[0]
        # Exclude the most recent row for averaging
        sorted_df = filtered_df.sort_values(['Parsed_Date', 'AM/PM'], ascending=[False, True])
        mask = ~((sorted_df['Parsed_Date'] == max_date) & (sorted_df['AM/PM'] == most_recent['AM/PM']))
        previous_volumes = sorted_df[mask]['Volume']
        num_previous = previous_volumes.count()
        avg_previous_volume = previous_volumes.sum() / num_previous if num_previous > 0 else None
        if avg_previous_volume is not None:
            avg_previous_volume = round(avg_previous_volume)
        most_recent_volume = most_recent['Volume']
        diff = most_recent_volume - avg_previous_volume if avg_previous_volume is not None else None
        summary_rows.append({
            'Symbol': symbol,
            'Avg Previous Volume': avg_previous_volume,
            'Most Recent Volume': most_recent_volume,
            'Difference': diff
        })
summary_df = pd.DataFrame(summary_rows)

st.title("📈 Stock Volume Comparison Table")
st.dataframe(summary_df, use_container_width=True)

# --- RAW DATA TABLE: filter by sidebar selection ---
st.subheader("Raw Data Table")
if selected_raw_symbol == 'All':
    display_df = df.copy()
else:
    display_df = df[df['Symbol'] == selected_raw_symbol].copy()
display_df['Date Used'] = display_df['Parsed_Date'].dt.date
columns_to_show = [col for col in display_df.columns if col not in ['Date_Original', 'Parsed_Date']]
if 'Date Used' not in columns_to_show:
    columns_to_show.append('Date Used')
sort_cols = [col for col in ['Symbol', 'Date Used'] if col in display_df.columns]
st.dataframe(display_df[columns_to_show].sort_values(sort_cols, ascending=[True, False][:len(sort_cols)]).reset_index(drop=True), use_container_width=True)

st.markdown("""
<style>
/* Make dataframes horizontally scrollable on small screens */
@media (max-width: 600px) {
  .stDataFrame, .stTable {
    overflow-x: auto !important;
    font-size: 15px !important;
  }
  .stButton>button, .stSelectbox label, .stSelectbox div[data-baseweb="select"] {
    font-size: 18px !important;
    min-height: 48px !important;
  }
  div.block-container {
    padding-top: 1rem !important;
    padding-left: 0.5rem !important;
    padding-right: 0.5rem !important;
  }
}

/* General style improvements */
div.block-container{padding-top:2rem;} .stDataFrame, .stTable {background: #f9f9f9; border-radius: 8px;} .stButton>button {background: #0066cc; color: white; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)
