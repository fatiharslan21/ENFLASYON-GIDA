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

# CSS AYARLARI (ULTRA ŞOV MODU)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;500;700&display=swap');

        [data-testid="stSidebar"] {display: none;}
        [data-testid="stToolbar"] {visibility: hidden !important;} 
        .stDeployButton {display:none !important;} 
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}

        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            font-family: 'Roboto', sans-serif;
            color: #2c3e50;
        }

        /* Ticker - SİYAH VE MODERN */
        .ticker-wrap {
            width: 100%; overflow: hidden; background-color: #000000;
            color: #00ff00; border-bottom: 2px solid #ebc71d; white-space: nowrap;
            padding: 12px 0; box-shadow: 0 10px 20px rgba(0,0,0,0.3); margin-bottom: 25px;
        }
        .ticker { display: inline-block; animation: ticker 50s linear infinite; }
        .ticker-item { 
            display: inline-block; padding: 0 2rem; 
            font-family: 'Courier New', monospace; font-weight: 700; font-size: 16px; 
            letter-spacing: 1px;
        }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* Kartlar - Glassmorphism & Hover */
        div[data-testid="metric-container"] {
            background: rgba(255, 255, 255, 0.85); 
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 16px; padding: 25px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1); 
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
            border-color: #ebc71d;
        }

        /* Panel - Kontrol Merkezi */
        .admin-panel {
            background: #ffffff; border-top: 5px solid #2ecc71; padding: 40px;
            border-radius: 24px; margin-top: 60px; 
            box-shadow: 0 -15px 50px rgba(0,0,0,0.05);
            text-align: center;
        }

        /* DEV Buton */
        .big-btn button {
            background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%) !important;
            color: white !important;
            border: none !important;
            height: 75px;
            font-size: 24px !important;
            font-weight: 800 !important;
            border-radius: 50px !important;
            box-shadow: 0 10px 25px rgba(56, 239, 125, 0.4);
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .big-btn button:hover {
            box-shadow: 0 20px 40px rgba(56, 239, 125, 0.6);
            transform: translateY(-3px);
            background: linear-gradient(90deg, #38ef7d 0%, #11998e 100%) !important;
        }

        /* Başlık Stili */
        .main-title {
            font-size: 3rem; font-weight: 900; 
            background: -webkit-linear-gradient(#1e3c72, #2a5298);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
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

            # --- AKILLI KAYIT SİSTEMİ (DUPLICATE ENGELLEME) ---
            # Yeni gelen verilerin tarih ve kodunu al
            yeni_tarih = df_yeni['Tarih'].iloc[0]  # Hepsi aynı gün zaten

            # Mevcut veri setinden BUGÜNÜN verilerini temizle (Aynı kodlu olanları)
            # Mantık: Eğer bugün aynı kodla veri varsa, eskisi silinir, yenisi eklenir (update mantığı)
            mask_silinecek = (mevcut_df['Tarih'].astype(str) == str(yeni_tarih)) & (
                mevcut_df['Kod'].isin(df_yeni['Kod']))
            mevcut_df = mevcut_df[~mask_silinecek]

            # Şimdi birleştir
            final_df = pd.concat([mevcut_df, df_yeni], ignore_index=True)
            # --------------------------------------------------

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
    if log_callback: log_callback("🛡️ Güvenli Mod Başlatılıyor...")
    install_browsers()

    try:
        df = github_excel_oku(EXCEL_DOSYASI, sayfa_adi=SAYFA_ADI)
        if df.empty: return "⚠️ Konfigürasyon dosyası okunamadı veya boş!"

        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()
        if takip.empty: return "⚠️ Listede takip edilecek ürün yok!"
    except Exception as e:
        return f"Excel Hatası: {e}"

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

            if log_callback: log_callback(f"🔎 [{i + 1}/{total}] {urun_adi} aranıyor...")
            fiyat = 0.0

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(1.5)

                # 1. YÖNTEM: JSON-LD
                try:
                    page.wait_for_selector("script[type='application/ld+json']", timeout=2000)
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
                                     "sm-product-price .amount", ".product-price", "fe-product-price .amount",
                                     ".amount"]
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
                if log_callback: log_callback(f"✅ {urun_adi}: {fiyat} TL")
                veriler.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d"),
                    "Zaman": datetime.now().strftime("%H:%M"),
                    "Kod": row.get('Kod'),
                    "Madde_Adi": row.get('Madde adı'),
                    "Fiyat": fiyat,
                    "Kaynak": "Sanal Market",
                    "URL": url
                })
            else:
                if log_callback: log_callback(f"❌ {urun_adi}: Bulunamadı")

            time.sleep(1)
        browser.close()

    if veriler:
        df_new = pd.DataFrame(veriler)
        if log_callback: log_callback("💾 Veritabanına Güncellenerek Kaydediliyor...")
        sonuc = github_excel_guncelle(df_new, FIYAT_DOSYASI, mesaj=f"Otomatik Bot: {len(veriler)} Veri Güncellendi")
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
        emoji_map = {"01": "🍎", "02": "🍷", "03": "👕", "04": "🏠", "05": "🛋️", "06": "💊", "07": "🚗", "08": "📱", "09": "🎭",
                     "10": "🎓", "11": "🍽️", "12": "💅"}
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

            # --- ARAYÜZ ---

            # Ticker (Siyah Arkaplan)
            ticker_html = ""
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(10).iterrows():
                val = r['Fark']
                color = "#ff4d4d" if val > 0 else "#2ecc71" if val < 0 else "#ffffff"  # Kırmızı artış, Yeşil düşüş
                symbol = "▲" if val > 0 else "▼" if val < 0 else "•"
                ticker_html += f"<span style='color:{color}'>{symbol} {r['Madde adı']} %{val * 100:.1f}</span> &nbsp;&nbsp;&nbsp;&nbsp; "
            st.markdown(
                f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">CANLI PİYASA: &nbsp;&nbsp; {ticker_html}</div></div></div>""",
                unsafe_allow_html=True)

            st.markdown(f'<div class="main-title">ENFLASYON MONİTÖRÜ</div>', unsafe_allow_html=True)
            st.caption(f"📅 Son Veri: {son_gun} | Sistem Saati: {datetime.now().strftime('%H:%M')}")

            # Metricler
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("GENEL ENDEKS", f"{son_endeks:.2f}", "Baz: 100")
            c2.metric("GENEL ENFLASYON", f"%{genel_enflasyon:.2f}", delta_color="inverse")
            c3.metric("ZAM ŞAMPİYONU", f"{top_artis['Madde adı'][:15]}..", f"%{top_artis['Fark'] * 100:.1f}",
                      delta_color="inverse")
            c4.metric("VERİ SETİ", f"{len(gunler)} Gün", str(son_gun))

            st.markdown("---")

            # Ana Grafikler
            c_left, c_right = st.columns([2, 1])
            with c_left:
                fig_area = px.area(df_trend, x='Tarih', y='TÜFE', color_discrete_sequence=['#3498db'])
                fig_area.update_layout(
                    title="Enflasyon Trendi",
                    margin=dict(l=0, r=0, t=40, b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#2c3e50')
                )
                st.plotly_chart(fig_area, use_container_width=True)
            with c_right:
                val = min(max(0, abs(genel_enflasyon)), 50)
                fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=val,
                                                   gauge={'axis': {'range': [None, 50]}, 'bar': {'color': "#e74c3c"},
                                                          'bgcolor': "white"}))
                fig_gauge.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=250, paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_gauge, use_container_width=True)

            # Sekmeler
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["GENEL BAKIŞ", "🍏 GIDA ENFLASYONU", "SEKTÖRLER", "DETAYLI ANALİZ & EXCEL", "SİMÜLASYON"])

            with tab1:
                df_analiz['Grup_Degisim'] = df_analiz.groupby('Grup')['Fark'].transform('mean') * 100
                grp = df_analiz[['Grup', 'Grup_Degisim']].drop_duplicates().sort_values('Grup_Degisim')
                st.plotly_chart(go.Figure(go.Bar(y=grp['Grup'], x=grp['Grup_Degisim'], orientation='h',
                                                 marker=dict(color=grp['Grup_Degisim'], colorscale='RdYlGn_r'))),
                                use_container_width=True)

            with tab2:
                st.subheader("🍏 Mutfak Enflasyonu (Sanal Market Verisi)")
                if not df_gida.empty:
                    kg1, kg2 = st.columns(2)
                    kg1.metric("GIDA ENFLASYONU", f"%{gida_enflasyonu:.2f}", delta_color="inverse")
                    kg2.metric("Ortalama Ürün Artışı", f"%{gida_aylik:.2f}")
                    st.divider()

                    df_show = df_gida[['Madde adı', 'Fark', son_gun]].sort_values('Fark', ascending=False)
                    df_show = df_show.rename(columns={son_gun: "Son_Tutar"})
                    st.dataframe(df_show, column_config={
                        "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f%%", min_value=-0.5,
                                                                max_value=0.5),
                        "Son_Tutar": st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                    }, hide_index=True, use_container_width=True)
                else:
                    st.warning("Henüz gıda verisi yok.")

            with tab3:
                grup_katki = df_analiz.groupby('Grup')['Fark'].mean().sort_values(ascending=False).head(10) * 100
                st.plotly_chart(go.Figure(
                    go.Waterfall(orientation="v", measure=["relative"] * len(grup_katki), x=grup_katki.index,
                                 y=grup_katki.values)), use_container_width=True)

            with tab4:  # Excel İndirme ve Gelişmiş Liste
                c_dl_1, c_dl_2 = st.columns([3, 1])
                with c_dl_1:
                    st.subheader("📊 Detaylı Fiyat Analizi")
                with c_dl_2:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_analiz.to_excel(writer, index=False, sheet_name='Analiz')

                    st.download_button(
                        label="📥 Excel Olarak İndir",
                        data=output.getvalue(),
                        file_name=f"Enflasyon_Analiz_{son_gun}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="secondary"
                    )

                col_baz_str = str(baz_gun)
                col_son_str = str(son_gun)

                df_show_tab4 = df_analiz[['Emoji', 'Madde adı', 'Grup', 'Fark', baz_gun, son_gun]].copy()
                df_show_tab4 = df_show_tab4.rename(columns={baz_gun: col_baz_str, son_gun: col_son_str})

                st.dataframe(
                    df_show_tab4,
                    column_config={
                        "Fark": st.column_config.LineChartColumn("Değişim Trendi", y_min=-0.5, y_max=0.5),
                        # Burası LineChart oldu
                        col_baz_str: st.column_config.NumberColumn(f"Baz ({col_baz_str})", format="%.2f ₺"),
                        col_son_str: st.column_config.NumberColumn(f"Son ({col_son_str})", format="%.2f ₺"),
                    },
                    use_container_width=True,
                    height=500
                )

            with tab5:
                cols = st.columns(4)
                sim_inputs = {grp: cols[i % 4].number_input(f"{grp} (%)", -100.0, 100.0, 0.0) for i, grp in
                              enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in sim_inputs.items()])
                st.metric("Simüle Enflasyon", f"%{genel_enflasyon + etki:.2f}", f"{etki:+.2f}% Etki",
                          delta_color="inverse")

    else:
        st.info("⚠️ Veri Bulunamadı. Lütfen 'Botu Başlat' butonunu kullanarak veri çekin.")

    # --- YENİ YÖNETİM PANELİ ---
    st.markdown('<div class="admin-panel"><div class="admin-header">🚀 SİSTEM KONTROL MERKEZİ</div>',
                unsafe_allow_html=True)

    c_center = st.columns([1, 2, 1])[1]

    with c_center:
        st.markdown('<div class="big-btn">', unsafe_allow_html=True)
        if st.button("KAMPANYA BOTUNU BAŞLAT", type="primary", use_container_width=True):
            log_cont = st.empty()

            progress_text = "Veri kaynaklarına bağlanılıyor..."
            my_bar = st.progress(0, text=progress_text)

            def bot_logger(msg):
                log_cont.code(msg, language="yaml")
                try:
                    my_bar.progress(50, text="Fiyatlar Analiz Ediliyor...")
                except:
                    pass

            sonuc = migros_gida_botu(bot_logger)
            my_bar.progress(100, text="Tamamlandı!")

            if "OK" in sonuc:
                st.success("✅ Veritabanı Başarıyla Güncellendi!")
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                st.error(sonuc)
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Not: İşlem ürün sayısına bağlı olarak 1-2 dakika sürebilir.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="signature">Fatih Arslan Tarafından Geliştirilmiştir</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()