import streamlit as st
import pandas as pd
import ssl
from datetime import datetime
import dateutil.parser

ssl._create_default_https_context = ssl._create_unverified_context

# URL of the CSV file
data_url = "https://raw.githubusercontent.com/DCruise1/DataPull/main/stocks.csv"

# Only load needed columns
COLUMNS = ['Symbol', 'Date', 'AM/PM', 'Volume']

def robust_parse_date(date_str):
    try:
        # Try to parse with dateutil for flexibility
        return dateutil.parser.parse(date_str, dayfirst=True, fuzzy=True)
    except Exception:
        return pd.NaT

@st.cache_data(show_spinner=False)
def load_data():
    # Only load needed columns
    df = pd.read_csv(data_url, usecols=lambda c: c.strip() in COLUMNS, on_bad_lines='skip', engine='python')
    df.columns = [col.strip().replace('\n', '').replace(' ', '') for col in df.columns]
    if 'Date' in df.columns:
        df['Date_Original'] = df['Date']
        df['Parsed_Date'] = df['Date_Original'].astype(str).apply(robust_parse_date)
        df['Parsed_Date'] = pd.to_datetime(df['Parsed_Date'], errors='coerce', dayfirst=True, infer_datetime_format=True)
    else:
        df['Parsed_Date'] = pd.NaT
    if 'Volume' in df.columns:
        df['Volume'] = pd.to_numeric(df['Volume'].astype(str).str.replace(',', ''), errors='coerce')
    if 'AM/PM' not in df.columns:
        df['AM/PM'] = ''
    # Use efficient dtypes
    if 'Symbol' in df.columns:
        df['Symbol'] = df['Symbol'].astype('category')
    if 'AM/PM' in df.columns:
        df['AM/PM'] = df['AM/PM'].astype('category')
    keep_cols = [col for col in ['Symbol', 'Date', 'AM/PM', 'Volume', 'Parsed_Date', 'Date_Original'] if col in df.columns]
    df = df[keep_cols]
    return df

@st.cache_data(show_spinner=False)
def get_summary_table(df):
    symbols = df['Symbol'].dropna().unique()
    summary_rows = []
    for symbol in symbols:
        symbol_df = df[df['Symbol'] == symbol]
        if not symbol_df.empty:
            max_date = symbol_df['Parsed_Date'].max()
            recent_rows = symbol_df[symbol_df['Parsed_Date'] == max_date]
            if 'PM' in recent_rows['AM/PM'].values:
                most_recent = recent_rows[recent_rows['AM/PM'] == 'PM'].iloc[0]
            else:
                most_recent = recent_rows.iloc[0]
            sorted_df = symbol_df.sort_values(['Parsed_Date', 'AM/PM'], ascending=[False, True])
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
    return pd.DataFrame(summary_rows)

st.set_page_config(page_title="Stock Volume Explorer", layout="centered")

# --- Custom CSS for minimal, professional look and mobile polish ---
st.markdown("""
<style>
body, .stApp { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; background: #f7f9fa; }
.stDataFrame, .stTable { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); }
.stButton>button { background: #0056b3; color: white; border-radius: 5px; font-size: 1.1em; }
.stSelectbox label, .stSelectbox div[data-baseweb="select"] { font-size: 1.1em; }
@media (max-width: 600px) {
  .stDataFrame, .stTable { font-size: 15px !important; }
  .stButton>button, .stSelectbox label, .stSelectbox div[data-baseweb="select"] { font-size: 18px !important; min-height: 48px !important; }
  div.block-container { padding-top: 0.5rem !important; padding-left: 0.2rem !important; padding-right: 0.2rem !important; }
}
div.block-container{padding-top:1.2rem;} .stDataFrame, .stTable {background: #fff; border-radius: 10px;}
.stDataFrame table tr:hover {background: #f0f4f8;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center; font-weight:700; margin-bottom:0.2em;'>📈 Stock Volume Explorer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#555; margin-bottom:1.5em;'>Quickly compare and explore stock volume trends. Data updates automatically.</p>", unsafe_allow_html=True)

# --- Data Loading & Refresh ---
refresh = st.button('🔄 Refresh Data')
if 'df' not in st.session_state or refresh:
    if refresh:
        load_data.clear()
        get_summary_table.clear()
    with st.spinner('Loading data...'):
        st.session_state.df = load_data()
df = st.session_state.df

# --- Data Cleaning (robust) ---
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

# --- Symbol Selection (top, unified) ---
symbols = df['Symbol'].dropna().unique()
symbol_options = ['All'] + sorted(symbols)
selected_symbol = st.selectbox("Select Stock Symbol", symbol_options, index=0, help="Filter raw data table by stock symbol")

# --- SUMMARY TABLE (always all symbols, precomputed) ---
summary_df = get_summary_table(df)
st.markdown("<h3 style='margin-top:1.5em;'>Volume Comparison</h3>", unsafe_allow_html=True)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# --- RAW DATA TABLE (filtered) ---
st.markdown("<h3 style='margin-top:1.5em;'>Raw Data</h3>", unsafe_allow_html=True)
if selected_symbol == 'All':
    filtered_df = df.copy()
else:
    filtered_df = df[df['Symbol'] == selected_symbol].copy()
if not filtered_df.empty:
    filtered_df['Date Used'] = filtered_df['Parsed_Date'].dt.date
    columns_to_show = [col for col in filtered_df.columns if col not in ['Date_Original', 'Parsed_Date']]
    if 'Date Used' not in columns_to_show:
        columns_to_show.append('Date Used')
    sort_cols = [col for col in ['Symbol', 'Date Used'] if col in filtered_df.columns]
    st.dataframe(filtered_df[columns_to_show].sort_values(sort_cols, ascending=[True, False][:len(sort_cols)]).reset_index(drop=True), use_container_width=True, hide_index=True)
else:
    st.info("No data available for the selected symbol.")

# For even more speed, consider pre-processing and hosting a smaller, already-cleaned CSV, or using a database or API for large datasets.
