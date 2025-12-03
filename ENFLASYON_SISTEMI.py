import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from playwright.sync_api import sync_playwright
import os
import re
from datetime import datetime
import time
import sys
import subprocess
import json
from github import Github
from io import BytesIO

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(page_title="PRO ENFLASYON TERMİNALİ", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

# --- ULTRA ŞOV CSS (DARK FINTECH THEME) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Montserrat:wght@400;600;800&display=swap');

        /* GENEL SAYFA YAPISI */
        .stApp {
            background: radial-gradient(circle at 10% 20%, rgb(15, 23, 42) 0%, rgb(0, 0, 0) 90%);
            color: #e2e8f0;
            font-family: 'Montserrat', sans-serif;
        }

        /* GİZLEME */
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stToolbar"] {visibility: hidden !important;} 
        .stDeployButton {display:none !important;} 
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}

        /* TICKER (BORSA BANDI) */
        .ticker-wrap {
            width: 100%; overflow: hidden; 
            background: rgba(0, 0, 0, 0.8);
            border-top: 1px solid #334155;
            border-bottom: 1px solid #334155;
            white-space: nowrap;
            padding: 10px 0; margin-bottom: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1);
        }
        .ticker { display: inline-block; animation: ticker 40s linear infinite; }
        .ticker-item { 
            display: inline-block; padding: 0 3rem; 
            font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14px; 
            color: #64748b;
        }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* ÖZEL METRİK KARTLARI (NEON GLASS) */
        .custom-card {
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }
        .custom-card::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, #00f260, transparent);
            transform: translateX(-100%); transition: 0.5s;
        }
        .custom-card:hover::before { transform: translateX(100%); }
        .custom-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 242, 96, 0.15);
            border-color: #00f260;
        }
        .card-title { font-size: 14px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
        .card-value { font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 800; color: #f8fafc; }
        .card-sub { font-size: 12px; color: #64748b; margin-top: 5px; }

        /* RENKLİ DEĞERLER */
        .val-up { color: #00f260; text-shadow: 0 0 10px rgba(0, 242, 96, 0.4); }
        .val-down { color: #ff0055; text-shadow: 0 0 10px rgba(255, 0, 85, 0.4); }
        .val-gold { color: #ffd700; text-shadow: 0 0 10px rgba(255, 215, 0, 0.4); }

        /* BAŞLIK */
        .main-header {
            font-size: 40px; font-weight: 900; text-align: center;
            background: linear-gradient(to right, #ffffff, #94a3b8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 5px; letter-spacing: -1px;
        }
        .sub-header { text-align: center; color: #64748b; font-family: 'JetBrains Mono', monospace; font-size: 12px; margin-bottom: 30px; }

        /* BUTON (CYBERPUNK) */
        .cyber-btn button {
            background: transparent !important;
            border: 1px solid #00f260 !important;
            color: #00f260 !important;
            font-family: 'JetBrains Mono', monospace !important;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: bold;
            height: 60px;
            border-radius: 4px;
            transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(0, 242, 96, 0.2);
        }
        .cyber-btn button:hover {
            background: #00f260 !important;
            color: #000 !important;
            box-shadow: 0 0 25px rgba(0, 242, 96, 0.6);
        }

        /* TABLOLAR */
        .stDataFrame { border: 1px solid #334155; border-radius: 8px; }

        /* TABS */
        .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 1px solid #334155; }
        .stTabs [data-baseweb="tab"] {
            height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; color: #94a3b8;
        }
        .stTabs [aria-selected="true"] { background-color: rgba(255,255,255,0.05); color: #00f260; border-bottom: 2px solid #00f260; }

    </style>
""", unsafe_allow_html=True)

# --- 2. AYARLAR ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


# --- GITHUB ENTEGRASYON FONKSİYONLARI ---
def get_github_repo():
    try:
        g = Github(st.secrets["github"]["token"])
        repo = g.get_repo(st.secrets["github"]["repo_name"])
        return repo
    except Exception as e:
        st.error(f"GitHub Bağlantı Hatası: {e}. Lütfen secrets.toml ayarlarını kontrol edin.")
        return None


def github_excel_oku(dosya_adi, sayfa_adi=None):
    repo = get_github_repo()
    if not repo: return None
    try:
        contents = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        if sayfa_adi:
            df = pd.read_excel(BytesIO(contents.decoded_content), sheet_name=sayfa_adi, dtype={'Kod': str})
        else:
            df = pd.read_excel(BytesIO(contents.decoded_content))
        return df
    except Exception as e:
        return pd.DataFrame()


def github_excel_guncelle(df_yeni, dosya_adi, mesaj="Veri Güncellemesi"):
    repo = get_github_repo()
    if not repo: return "Repo Bulunamadı"
    try:
        try:
            contents = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            mevcut_df = pd.read_excel(BytesIO(contents.decoded_content))

            # --- AKILLI KAYIT (GÜN İÇİNDE GÜNCELLEME) ---
            # Aynı gün ve aynı koda sahip veri varsa eskisi silinir, yenisi yazılır.
            # Böylece veri seti şişmez.
            yeni_tarih = df_yeni['Tarih'].iloc[0]
            mask_silinecek = (mevcut_df['Tarih'].astype(str) == str(yeni_tarih)) & (
                mevcut_df['Kod'].isin(df_yeni['Kod']))
            mevcut_df = mevcut_df[~mask_silinecek]

            final_df = pd.concat([mevcut_df, df_yeni], ignore_index=True)
            # --------------------------------------------

        except:
            contents = None
            final_df = df_yeni

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Fiyat_Log')
        data = output.getvalue()

        if contents:
            repo.update_file(contents.path, mesaj, data, contents.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, mesaj, data, branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return f"GitHub Yazma Hatası: {e}"


# --- YARDIMCI FONKSİYONLAR ---
def kod_standartlastir(kod):
    try:
        return str(kod).replace('.0', '').strip().zfill(7)
    except:
        return "0000000"


def temizle_fiyat(text):
    if not text: return None
    text = str(text)
    text = re.sub('<[^<]+?>', '', text)
    text = text.replace('TL', '').replace('₺', '').replace('TRY', '').strip()
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    text = re.sub(r'[^\d.]', '', text)
    try:
        val = float(text)
        return val if val > 0.5 else None
    except:
        return None


def install_browsers():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "firefox"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps", "firefox"], check=False)
    except:
        pass


# --- 🐢 GÜVENLİ BOT (SAFE MODE) 🐢 ---
def migros_gida_botu(log_callback=None):
    if log_callback: log_callback("⚡ BAĞLANTI KURULUYOR...")
    install_browsers()

    try:
        df = github_excel_oku(EXCEL_DOSYASI, sayfa_adi=SAYFA_ADI)
        if df.empty: return "⚠️ Konfigürasyon Hatası"

        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()
        if takip.empty: return "⚠️ Ürün Listesi Boş"
    except Exception as e:
        return f"Hata: {e}"

    veriler = []
    total = len(takip)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media",
                                                                                          "font"] else route.continue_())
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for i, row in takip.iterrows():
            urun_adi = str(row.get('Madde adı', 'Bilinmeyen'))[:25]
            url = row['URL']

            if log_callback: log_callback(f"SCANNING [{i + 1}/{total}] >> {urun_adi}")
            fiyat = 0.0

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(1.0)  # Biraz daha hızlı

                # 1. YÖNTEM: JSON-LD
                try:
                    page.wait_for_selector("script[type='application/ld+json']", timeout=1500)
                    json_data = page.locator("script[type='application/ld+json']").first.inner_text()
                    data = json.loads(json_data)
                    if "offers" in data and "price" in data["offers"]:
                        fiyat = float(data["offers"]["price"])
                    elif "hasVariant" in data:
                        fiyat = float(data["hasVariant"][0]["offers"]["price"])
                except:
                    pass

                # 2. YÖNTEM: CSS
                if fiyat == 0:
                    try:
                        selectors = ["span:has(span.currency)", "#sale-price", ".sale-price",
                                     "sm-product-price .amount", ".product-price", ".amount"]
                        for sel in selectors:
                            if page.locator(sel).count() > 0:
                                txt = page.locator(sel).first.inner_text()
                                val = temizle_fiyat(txt)
                                if val: fiyat = val; break
                    except:
                        pass

                # 3. YÖNTEM: Regex
                if fiyat == 0:
                    try:
                        body_txt = page.locator("body").inner_text()
                        bulunanlar = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', body_txt)
                        vals = [temizle_fiyat(x) for x in bulunanlar if temizle_fiyat(x)]
                        if vals: fiyat = vals[0]
                    except:
                        pass
            except:
                pass

            if fiyat > 0:
                veriler.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d"),
                    "Zaman": datetime.now().strftime("%H:%M"),
                    "Kod": row.get('Kod'),
                    "Madde_Adi": row.get('Madde adı'),
                    "Fiyat": fiyat,
                    "Kaynak": "Sanal Market",
                    "URL": url
                })
            time.sleep(0.5)
        browser.close()

    if veriler:
        df_new = pd.DataFrame(veriler)
        if log_callback: log_callback("💾 VERİTABANI GÜNCELLENİYOR...")
        sonuc = github_excel_guncelle(df_new, FIYAT_DOSYASI, mesaj=f"Terminal Update: {len(veriler)} Items")
        return sonuc

    return "Veri Yok"


# --- 📊 ANA DASHBOARD 📊 ---
def dashboard_modu():
    # Veri Yükleme
    def veri_yukle():
        df_f = github_excel_oku(FIYAT_DOSYASI)
        if df_f.empty: return pd.DataFrame(), None

        df_f['Tarih'] = pd.to_datetime(df_f['Tarih'])
        df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
        df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
        df_f = df_f[df_f['Fiyat'] > 0]

        df_s = github_excel_oku(EXCEL_DOSYASI, sayfa_adi=SAYFA_ADI)
        if df_s.empty: return df_f, None

        df_s['Kod'] = df_s['Kod'].astype(str).apply(kod_standartlastir)
        grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık",
                    "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta", "12": "Çeşitli"}
        emoji_map = {"01": "🍔", "02": "🍷", "03": "👔", "04": "🏠", "05": "🛋️", "06": "💊", "07": "🚗", "08": "📱", "09": "🎭",
                     "10": "🎓", "11": "🍽️", "12": "💎"}
        df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map)
        df_s['Emoji'] = df_s['Kod'].str[:2].map(emoji_map).fillna("📦")
        return df_f, df_s

    df_fiyat, df_sepet = veri_yukle()

    if df_fiyat is not None and not df_fiyat.empty and df_sepet is not None:
        # --- HESAPLAMALAR ---
        if 'Zaman' in df_fiyat.columns:
            df_fiyat['Tam_Zaman'] = pd.to_datetime(df_fiyat['Tarih'].astype(str) + ' ' + df_fiyat['Zaman'].astype(str),
                                                   errors='coerce')
        else:
            df_fiyat['Tam_Zaman'] = df_fiyat['Tarih']

        df_fiyat = df_fiyat.sort_values('Tam_Zaman')
        df_fiyat['Gun'] = df_fiyat['Tarih'].dt.date

        pivot = df_fiyat.pivot_table(index='Kod', columns='Gun', values='Fiyat', aggfunc='last')
        pivot = pivot.ffill(axis=1).bfill(axis=1)

        if not pivot.empty:
            df_analiz = pd.merge(df_sepet, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])
            gunler = sorted(pivot.columns)
            baz_gun, son_gun = gunler[0], gunler[-1]

            trend_data = []
            for g in gunler:
                temp = df_analiz.dropna(subset=[g, baz_gun])
                if not temp.empty:
                    temp['Puan'] = (temp[g] / temp[baz_gun]) * temp['Agirlik_2025']
                    endeks_degeri = (temp['Puan'].sum() / temp['Agirlik_2025'].sum()) * 100
                    trend_data.append({"Tarih": g, "TÜFE": endeks_degeri})
            df_trend = pd.DataFrame(trend_data)
            son_endeks = df_trend['TÜFE'].iloc[-1]
            genel_enflasyon = ((son_endeks / 100) - 1) * 100

            df_analiz['Fark'] = (df_analiz[son_gun] / df_analiz[baz_gun]) - 1
            top_artis = df_analiz.sort_values('Fark', ascending=False).iloc[0]

            df_gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            if not df_gida.empty:
                df_gida['Etki'] = (df_gida[son_gun] / df_gida[baz_gun]) * df_gida['Agirlik_2025']
                gida_endeks = df_gida['Etki'].sum() / df_gida['Agirlik_2025'].sum()
                gida_enflasyonu = (gida_endeks - 1) * 100
                gida_aylik = df_gida['Fark'].mean() * 100
            else:
                gida_enflasyonu = 0;
                gida_aylik = 0

            # --- ARAYÜZ (ŞOV ZAMANI) ---

            # 1. TICKER
            ticker_html = ""
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(12).iterrows():
                val = r['Fark'] * 100
                color = "#00f260" if val < 0 else "#ff0055" if val > 0 else "#94a3b8"
                symbol = "▼" if val < 0 else "▲" if val > 0 else "•"
                ticker_html += f"<span style='color:{color}'>{r['Madde adı']} {symbol} %{abs(val):.1f}</span> &nbsp;|&nbsp; "
            st.markdown(
                f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{ticker_html}</div></div></div>""",
                unsafe_allow_html=True)

            # 2. HEADER
            st.markdown('<div class="main-header">ENFLASYON TERMİNALİ v3.0</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="sub-header">SYSTEM ONLINE | DATASET: {son_gun} | SERVER TIME: {datetime.now().strftime("%H:%M:%S")}</div>',
                unsafe_allow_html=True)

            # 3. METRIK KARTLARI (CUSTOM HTML)
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(f"""
                <div class="custom-card">
                    <div class="card-title">Genel Endeks</div>
                    <div class="card-value val-gold">{son_endeks:.2f}</div>
                    <div class="card-sub">Baz: 100 Puan</div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                renk = "val-down" if genel_enflasyon > 0 else "val-up"
                st.markdown(f"""
                <div class="custom-card">
                    <div class="card-title">Enflasyon</div>
                    <div class="card-value {renk}">%{genel_enflasyon:.2f}</div>
                    <div class="card-sub">Kümülatif Değişim</div>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div class="custom-card">
                    <div class="card-title">Gıda Şoku</div>
                    <div class="card-value val-down">%{gida_enflasyonu:.2f}</div>
                    <div class="card-sub">Mutfak Enflasyonu</div>
                </div>
                """, unsafe_allow_html=True)

            with col4:
                st.markdown(f"""
                <div class="custom-card">
                    <div class="card-title">Risk Lideri</div>
                    <div class="card-value val-down" style="font-size:20px; padding-top:8px;">{top_artis['Madde adı'][:15]}</div>
                    <div class="card-sub">Artış: %{top_artis['Fark'] * 100:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # 4. ANA GRAFİKLER (DARK PLOTLY)
            c_left, c_right = st.columns([2, 1])
            with c_left:
                fig_area = px.area(df_trend, x='Tarih', y='TÜFE', template='plotly_dark')
                fig_area.update_traces(line_color='#00f260', fill='tozeroy', fillcolor='rgba(0, 242, 96, 0.1)')
                fig_area.update_layout(
                    title={'text': "📈 ENDEKS TRENDİ", 'font': {'size': 16, 'color': '#94a3b8'}},
                    margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                )
                st.plotly_chart(fig_area, use_container_width=True)

            with c_right:
                val = min(max(0, abs(genel_enflasyon)), 50)
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=val,
                    number={'font': {'color': '#e2e8f0'}},
                    gauge={
                        'axis': {'range': [None, 50], 'tickcolor': "#94a3b8"},
                        'bar': {'color': "#ff0055"},
                        'bgcolor': "rgba(255,255,255,0.1)",
                        'bordercolor': "rgba(255,255,255,0.2)"
                    }
                ))
                fig_gauge.update_layout(
                    title={'text': "🔥 ISINMA GÖSTERGESİ", 'font': {'size': 16, 'color': '#94a3b8'}},
                    margin=dict(l=20, r=20, t=60, b=20), height=300,
                    template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

            # 5. TABLAR
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["📊 SEKTÖRLER", "🍏 GIDA DETAY", "📁 VERİ ANALİZİ", "🤖 BOT KONTROL", "🎲 SİMÜLASYON"])

            with tab1:
                df_analiz['Grup_Degisim'] = df_analiz.groupby('Grup')['Fark'].transform('mean') * 100
                grp = df_analiz[['Grup', 'Grup_Degisim']].drop_duplicates().sort_values('Grup_Degisim')
                fig_bar = go.Figure(go.Bar(
                    y=grp['Grup'], x=grp['Grup_Degisim'], orientation='h',
                    marker=dict(color=grp['Grup_Degisim'], colorscale='Redor_r', showscale=False)
                ))
                fig_bar.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)',
                                      plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=0, b=0))
                st.plotly_chart(fig_bar, use_container_width=True)

            with tab2:
                if not df_gida.empty:
                    col_baz_str = str(baz_gun)
                    col_son_str = str(son_gun)

                    df_gida_show = df_gida[['Madde adı', 'Fark', baz_gun, son_gun]].sort_values('Fark', ascending=False)
                    df_gida_show = df_gida_show.rename(columns={baz_gun: col_baz_str, son_gun: col_son_str})

                    st.dataframe(
                        df_gida_show,
                        column_config={
                            "Fark": st.column_config.LineChartColumn("Trend Analizi", y_min=-0.5, y_max=0.5),
                            col_baz_str: st.column_config.NumberColumn("Başlangıç", format="%.2f ₺"),
                            col_son_str: st.column_config.NumberColumn("Son Durum", format="%.2f ₺"),
                            "Madde adı": st.column_config.TextColumn("Ürün", width="medium")
                        },
                        use_container_width=True, height=500
                    )
                else:
                    st.warning("Veri bekleniyor...")

            with tab3:  # Excel & Full Liste
                c_dl_1, c_dl_2 = st.columns([3, 1])
                with c_dl_1: st.info("Tüm veritabanı analizi ve Excel dökümü.")
                with c_dl_2:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_analiz.to_excel(writer, index=False, sheet_name='Analiz')
                    st.download_button("📥 RAPORU İNDİR", data=output.getvalue(),
                                       file_name=f"Enflasyon_Rapor_{son_gun}.xlsx", use_container_width=True)

                col_baz_str = str(baz_gun)
                col_son_str = str(son_gun)
                df_show_tab3 = df_analiz[['Emoji', 'Madde adı', 'Grup', 'Fark', baz_gun, son_gun]].copy()
                df_show_tab3 = df_show_tab3.rename(columns={baz_gun: col_baz_str, son_gun: col_son_str})

                st.dataframe(
                    df_show_tab3,
                    column_config={
                        "Fark": st.column_config.LineChartColumn("Trend", y_min=-0.5, y_max=0.5),
                        col_baz_str: st.column_config.NumberColumn("Baz Fiyat", format="%.2f ₺"),
                        col_son_str: st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                    },
                    use_container_width=True, height=600
                )

            with tab4:  # BOT KONTROL (Admin Panelini buraya aldım, daha temiz)
                st.markdown('<div class="admin-panel">', unsafe_allow_html=True)
                c_bot, c_log = st.columns([1, 2])

                with c_bot:
                    st.markdown("### 🚀 SİSTEM KONTROL")
                    st.markdown('<div class="cyber-btn">', unsafe_allow_html=True)
                    if st.button("TERMİNALİ BAŞLAT", key="bot_start", use_container_width=True):
                        log_cont = st.empty()
                        progress_text = "Veri akışı başlatılıyor..."
                        my_bar = st.progress(0, text=progress_text)

                        def bot_logger(msg):
                            log_cont.code(f">_ {msg}", language="bash")
                            try:
                                my_bar.progress(50, text="Processing...")
                            except:
                                pass

                        sonuc = migros_gida_botu(bot_logger)
                        my_bar.progress(100, text="Tamamlandı!")

                        if "OK" in sonuc:
                            st.success("SYSTEM UPDATED SUCCESSFULLY")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(sonuc)
                    st.markdown('</div>', unsafe_allow_html=True)

                with c_log:
                    st.markdown("### 📟 TERMİNAL ÇIKTISI")
                    st.code("Waiting for command...\n>_ Ready to scan...", language="bash")
                st.markdown('</div>', unsafe_allow_html=True)

            with tab5:
                cols = st.columns(4)
                sim_inputs = {grp: cols[i % 4].number_input(f"{grp} (%)", -100.0, 100.0, 0.0) for i, grp in
                              enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in sim_inputs.items()])

                new_val = genel_enflasyon + etki
                renk_sim = "#ff0055" if new_val > genel_enflasyon else "#00f260"

                st.markdown(f"""
                <div style="text-align:center; padding:20px; border:1px solid #334155; border-radius:12px; margin-top:20px;">
                    <div style="font-size:14px; color:#94a3b8;">SİMÜLE EDİLEN ENFLASYON</div>
                    <div style="font-size:40px; font-weight:bold; color:{renk_sim};">%{new_val:.2f}</div>
                    <div style="font-size:12px; color:#e2e8f0;">Etki: {etki:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.warning("⚠️ SİSTEM BEKLEMEDE. LÜTFEN 'BOT KONTROL' SEKMESİNDEN VERİ AKIŞINI BAŞLATIN.")


if __name__ == "__main__":
    dashboard_modu()