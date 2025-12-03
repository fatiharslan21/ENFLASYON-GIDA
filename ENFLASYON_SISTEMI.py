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
st.set_page_config(page_title="ENFLASYON MONITORU", page_icon="💸", layout="wide", initial_sidebar_state="collapsed")

# --- WHITE THEME & ULTRA UI CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        /* GENEL SAYFA */
        .stApp {
            background-color: #f8f9fa; /* Hafif Gri/Beyaz */
            color: #1f2937;
            font-family: 'Inter', sans-serif;
        }

        /* GİZLEME */
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stToolbar"] {visibility: hidden !important;} 
        .stDeployButton {display:none !important;} 
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}

        /* MODERN TICKER (BEYAZ) */
        .ticker-wrap {
            width: 100%; overflow: hidden; 
            background: #ffffff;
            border-bottom: 3px solid #f59e0b; /* Amber Çizgi */
            white-space: nowrap;
            padding: 12px 0; margin-bottom: 30px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }
        .ticker { display: inline-block; animation: ticker 60s linear infinite; }
        .ticker-item { 
            display: inline-block; padding: 0 2rem; 
            font-weight: 600; font-size: 14px; color: #374151;
        }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* KARTLAR (BEYAZ & GÖLGELİ) */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.3s ease;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #f59e0b;
        }

        /* TABLOLAR & DATA */
        .stDataFrame { border-radius: 10px; border: 1px solid #e5e7eb; background: white; }

        /* ACTION BUTTON (EN ALTTAKI BUTON) */
        .action-btn button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: white !important;
            border: none !important;
            height: 80px;
            font-size: 24px !important;
            font-weight: 800 !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 25px rgba(37, 99, 235, 0.3);
            transition: all 0.3s ease;
            width: 100%;
            text-transform: uppercase;
        }
        .action-btn button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 35px rgba(37, 99, 235, 0.4);
            background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
        }

        /* SEKMELER */
        .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e5e7eb; gap: 30px; }
        .stTabs [data-baseweb="tab"] { font-weight: 600; color: #6b7280; font-size: 16px; }
        .stTabs [aria-selected="true"] { color: #2563eb; border-bottom-color: #2563eb; }

        /* BAŞLIK */
        .main-title {
            font-size: 42px; font-weight: 800; color: #111827; letter-spacing: -1px; text-align: center; margin-bottom: 5px;
        }
        .sub-title {
            font-size: 14px; font-weight: 500; color: #6b7280; text-align: center; margin-bottom: 40px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. AYARLAR ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


# --- GITHUB ENTEGRASYON ---
def get_github_repo():
    try:
        g = Github(st.secrets["github"]["token"])
        repo = g.get_repo(st.secrets["github"]["repo_name"])
        return repo
    except Exception as e:
        st.error(f"GitHub Bağlantı Hatası: {e}")
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

            yeni_tarih = df_yeni['Tarih'].iloc[0]
            mask_silinecek = (mevcut_df['Tarih'].astype(str) == str(yeni_tarih)) & (
                mevcut_df['Kod'].isin(df_yeni['Kod']))
            mevcut_df = mevcut_df[~mask_silinecek]

            final_df = pd.concat([mevcut_df, df_yeni], ignore_index=True)
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


# --- 🐢 MİGROS BOT ---
def migros_gida_botu(log_callback=None):
    if log_callback: log_callback("⚡ Bot Başlatılıyor...")
    install_browsers()

    try:
        df = github_excel_oku(EXCEL_DOSYASI, sayfa_adi=SAYFA_ADI)
        if df.empty: return "⚠️ Konfigürasyon Hatası"

        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()
        if takip.empty: return "⚠️ Liste Boş"
    except Exception as e:
        return f"Hata: {e}"

    veriler = []
    total = len(takip)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media",
                                                                                          "font"] else route.continue_())

        for i, row in takip.iterrows():
            urun_adi = str(row.get('Madde adı', 'Bilinmeyen'))[:25]
            url = row['URL']
            if log_callback: log_callback(f"🔍 {urun_adi} aranıyor...")
            fiyat = 0.0

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(1.0)
                try:
                    json_data = page.locator("script[type='application/ld+json']").first.inner_text()
                    data = json.loads(json_data)
                    if "offers" in data:
                        fiyat = float(data["offers"]["price"])
                    elif "hasVariant" in data:
                        fiyat = float(data["hasVariant"][0]["offers"]["price"])
                except:
                    pass

                if fiyat == 0:
                    try:
                        selectors = ["span:has(span.currency)", "#sale-price", ".sale-price",
                                     "sm-product-price .amount", ".product-price"]
                        for sel in selectors:
                            if page.locator(sel).count() > 0:
                                txt = page.locator(sel).first.inner_text()
                                val = temizle_fiyat(txt)
                                if val: fiyat = val; break
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
        if log_callback: log_callback("💾 Kaydediliyor...")
        sonuc = github_excel_guncelle(df_new, FIYAT_DOSYASI)
        return sonuc

    return "Veri Yok"


# --- 📊 DASHBOARD ---
def dashboard_modu():
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
        df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map)
        return df_f, df_s

    df_fiyat, df_sepet = veri_yukle()

    if df_fiyat is not None and not df_fiyat.empty and df_sepet is not None:
        if 'Zaman' in df_fiyat.columns:
            df_fiyat['Tam_Zaman'] = pd.to_datetime(df_fiyat['Tarih'].astype(str) + ' ' + df_fiyat['Zaman'].astype(str),
                                                   errors='coerce')
        else:
            df_fiyat['Tam_Zaman'] = df_fiyat['Tarih']
        df_fiyat = df_fiyat.sort_values('Tam_Zaman')
        df_fiyat['Gun'] = df_fiyat['Tarih'].dt.date
        pivot = df_fiyat.pivot_table(index='Kod', columns='Gun', values='Fiyat', aggfunc='last').ffill(axis=1).bfill(
            axis=1)

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
            else:
                gida_enflasyonu = 0

            # --- ARAYÜZ BAŞLIYOR ---

            # 1. TICKER
            ticker_html = ""
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(15).iterrows():
                val = r['Fark']
                color = "#dc2626" if val > 0 else "#16a34a"  # Kırmızı yükseliş (kötü), Yeşil düşüş (iyi)
                symbol = "▲" if val > 0 else "▼"
                ticker_html += f"<span style='color:{color}'>{r['Madde adı']} {symbol} %{val * 100:.1f}</span> &nbsp;&nbsp;&nbsp; "
            st.markdown(
                f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{ticker_html}</div></div></div>""",
                unsafe_allow_html=True)

            # 2. HEADER
            st.markdown('<div class="main-title">ENFLASYON MONİTÖRÜ</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sub-title">Son Veri: {son_gun} • Sistem: Aktif</div>', unsafe_allow_html=True)

            # 3. METRİKLER (CLEAN)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("GENEL ENDEKS", f"{son_endeks:.2f}", "Baz: 100 Puan")
            c2.metric("GENEL ENFLASYON", f"%{genel_enflasyon:.2f}", f"{(genel_enflasyon):.2f}%", delta_color="inverse")
            c3.metric("GIDA ENFLASYONU", f"%{gida_enflasyonu:.2f}", "Mutfak", delta_color="inverse")
            c4.metric("ZİRVEDEKİ ÜRÜN", f"{top_artis['Madde adı'][:15]}", f"%{top_artis['Fark'] * 100:.1f} Artış",
                      delta_color="inverse")

            st.markdown("<br>", unsafe_allow_html=True)

            # 4. TREND GRAFİĞİ (GÖSTERGE YOK)
            fig_area = px.area(df_trend, x='Tarih', y='TÜFE', color_discrete_sequence=['#f59e0b'])
            fig_area.update_layout(
                title="📈 Enflasyon Trendi",
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=40, b=0, l=0, r=0),
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#f3f4f6')
            )
            st.plotly_chart(fig_area, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # 5. YENİ GELİŞMİŞ SEKMELER
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["🗺️ SEKTÖR ISI HARİTASI", "🍏 GIDA DETAY", "📑 DETAYLI LİSTE", "🚀 EN ÇOK ARTANLAR", "🎲 SİMÜLASYON"])

            with tab1:  # YENİ: TREEMAP
                df_analiz['Etki_Puan'] = (df_analiz[son_gun] / df_analiz[baz_gun]) * df_analiz['Agirlik_2025']
                fig_tree = px.treemap(
                    df_analiz,
                    path=['Grup', 'Madde adı'],
                    values='Agirlik_2025',
                    color='Fark',
                    color_continuous_scale='RdYlGn_r',
                    title="Harcama Grupları ve Enflasyon Etkisi (Kırmızı: Yüksek Artış)"
                )
                fig_tree.update_layout(margin=dict(t=30, l=0, r=0, b=0))
                st.plotly_chart(fig_tree, use_container_width=True)

            with tab2:  # GIDA DETAY
                if not df_gida.empty:
                    col_baz = str(baz_gun)
                    col_son = str(son_gun)
                    df_gida_s = df_gida[['Madde adı', 'Fark', baz_gun, son_gun]].sort_values('Fark', ascending=False)
                    df_gida_s = df_gida_s.rename(columns={baz_gun: col_baz, son_gun: col_son})

                    st.dataframe(
                        df_gida_s,
                        column_config={
                            "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f%%", min_value=-0.5,
                                                                    max_value=0.5),
                            col_baz: st.column_config.NumberColumn(f"Başlangıç ({col_baz})", format="%.2f ₺"),
                            col_son: st.column_config.NumberColumn(f"Son ({col_son})", format="%.2f ₺"),
                        }, use_container_width=True
                    )
                else:
                    st.warning("Gıda verisi yok.")

            with tab3:  # DETAYLI LİSTE & EXCEL
                c_ex_1, c_ex_2 = st.columns([3, 1])
                with c_ex_1: st.markdown("##### Tüm Ürünlerin Detaylı Analizi")
                with c_ex_2:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_analiz.to_excel(writer, index=False)
                    st.download_button("📥 Excel İndir", output.getvalue(), f"Enflasyon_{son_gun}.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)

                col_baz = str(baz_gun)
                col_son = str(son_gun)
                df_full = df_analiz[['Grup', 'Madde adı', 'Fark', baz_gun, son_gun]].copy()
                df_full = df_full.rename(columns={baz_gun: col_baz, son_gun: col_son})

                st.dataframe(
                    df_full,
                    column_config={
                        "Fark": st.column_config.LineChartColumn("Trend", y_min=-0.5, y_max=0.5),
                        col_baz: st.column_config.NumberColumn("Baz Fiyat", format="%.2f ₺"),
                        col_son: st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                    }, use_container_width=True, height=500
                )

            with tab4:  # YENİ: ZİRVEDEKİLER (TOP RISERS)
                st.markdown("##### 🚀 Fiyatı En Çok Artan 10 Ürün")
                top_10 = df_analiz.sort_values('Fark', ascending=False).head(10)[['Madde adı', 'Grup', 'Fark']]
                st.table(top_10.assign(Fark=top_10['Fark'].apply(lambda x: f"%{x * 100:.2f}")))

            with tab5:  # SİMÜLASYON
                cols = st.columns(4)
                sim_inputs = {grp: cols[i % 4].number_input(f"{grp} (%)", -50.0, 100.0, 0.0) for i, grp in
                              enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in sim_inputs.items()])
                st.info(
                    f"Bu senaryoda enflasyon **%{etki:+.2f}** puan etkilenir. Yeni Tahmin: **%{(genel_enflasyon + etki):.2f}**")

    else:
        st.warning("Veri bulunamadı. Lütfen aşağıdan hesaplamayı başlatın.")

    # --- ACTION BUTTON ---
    st.markdown("---")
    st.markdown('<div class="action-btn">', unsafe_allow_html=True)
    if st.button("GIDAMI HESAPLA", type="primary", use_container_width=True):
        log_cont = st.empty()
        bar = st.progress(0, "Bağlanıyor...")

        def logger(msg):
            log_cont.info(msg)
            try:
                bar.progress(50, "Fiyatlar Toplanıyor...")
            except:
                pass

        sonuc = migros_gida_botu(logger)
        bar.progress(100, "Bitti!")
        if "OK" in sonuc:
            st.success("✅ Fiyatlar Güncellendi!")
            time.sleep(1);
            st.rerun()
        else:
            st.error(sonuc)
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Not: Bu işlem Sanal Market üzerinden anlık veri çeker. Ortalama 1-2 dakika sürer.")


if __name__ == "__main__":
    dashboard_modu()