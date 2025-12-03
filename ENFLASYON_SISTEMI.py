import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from playwright.sync_api import sync_playwright
import os
import re
from urllib.parse import urlparse
from datetime import datetime
import time
import sys
import subprocess
import numpy as np
import random
import shutil
import json

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(page_title="ENFLASYON MONITORU", page_icon="Hz", layout="wide", initial_sidebar_state="collapsed")

# --- CSS (ESKİ HAVALI TASARIM + YENİ MİGROS STİLİ) ---
st.markdown("""
    <style>
        /* Temel Gizlemeler */
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stToolbar"] {visibility: hidden !important;} 
        [data-testid="stHeader"] {visibility: hidden !important;}
        .stDeployButton {display:none !important;} 
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}

        .stApp {background-color: #F8F9FA; color: #212529;}

        /* Ticker (Kayan Yazı) */
        .ticker-wrap {
            width: 100%; overflow: hidden; background-color: #FFFFFF;
            border-bottom: 2px solid #ebc71d; white-space: nowrap;
            padding: 12px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
        }
        .ticker { display: inline-block; animation: ticker 60s linear infinite; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-family: 'Segoe UI', sans-serif; font-weight: 600; font-size: 14px; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* Metrik Kartları */
        div[data-testid="metric-container"] {
            background: #FFFFFF; border: 1px solid #EAEDF0; border-radius: 12px; padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.02); transition: all 0.3s ease;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); border-color: #ebc71d;
        }

        /* Alt Yönetim Paneli */
        .admin-panel {
            background-color: #FFFFFF; border-top: 4px solid #ebc71d; padding: 30px;
            border-radius: 15px; margin-top: 50px; box-shadow: 0 -5px 25px rgba(0,0,0,0.05);
        }

        /* Terminal Log Görünümü */
        .stCodeBlock {
            border: 2px solid #ebc71d !important;
            border-radius: 5px;
        }

        /* Migros Butonu İçin Stil */
        .migros-btn button {
            background-color: #f68b1f !important;
            color: white !important;
            border: none !important;
        }
        .migros-btn button:hover {
            background-color: #d67616 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. AYARLAR ---
BASE_DIR = os.getcwd()
TXT_DOSYASI = "URL VE CSS.txt"
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


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


def sistemi_sifirla():
    if os.path.exists(FIYAT_DOSYASI):
        try:
            shutil.copy(FIYAT_DOSYASI, f"YEDEK_{datetime.now().strftime('%Y%m%d')}.xlsx")
        except:
            pass
        df = pd.DataFrame(columns=["Tarih", "Zaman", "Kod", "Madde_Adi", "Fiyat", "Kaynak", "URL"])
        with pd.ExcelWriter(FIYAT_DOSYASI, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Fiyat_Log', index=False)
        return True
    return False


# --- 🔥 OTOMATİK TARAYICI KURULUMU 🔥 ---
def install_browsers():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "firefox"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps", "firefox"], check=False)
    except Exception as e:
        print(f"Browser install warning: {e}")


# --- 🤖 ÖZEL MİGROS GIDA BOTU 🤖 ---
def migros_gida_botu(log_callback=None):
    if log_callback: log_callback("🍏 Migros Gıda Botu Hazırlanıyor...")
    install_browsers()

    # Listeyi Oku
    try:
        df = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)

        # --- FİLTRELEME MANTIĞI ---
        # 1. Kod '01' ile başlamalı (GIDA)
        # 2. URL içinde 'migros' geçmeli
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()

        if takip.empty:
            return "⚠️ Listede '01' kodlu MİGROS ürünü bulunamadı!"

    except Exception as e:
        return f"Excel Hatası: {e}"

    veriler = []
    total = len(takip)

    if log_callback: log_callback(f"🚀 {total} GIDA Ürünü Taranacak (Sadece Migros)...")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        )
        page = context.new_page()
        # Webdriver gizleme
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for i, row in takip.iterrows():
            urun_adi = str(row.get('Madde adı', 'Bilinmeyen'))[:30]
            url = row['URL']

            log_msg = f"🛒 [{i + 1}/{total}] {urun_adi}..."
            if log_callback: log_callback(log_msg)

            fiyat = 0.0
            kaynak = ""

            try:
                # Migros SPA olduğu için networkidle beklemek iyidir
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                time.sleep(2)  # Garanti olsun diye kısa bekleme

                # --- MİGROS "SECRET WEAPON" (JSON-LD) ---
                # Görsel yüklenmese bile arka plandaki veriyi okur
                try:
                    json_data = page.locator("script[type='application/ld+json']").first.inner_text()
                    data = json.loads(json_data)

                    if "offers" in data and "price" in data["offers"]:
                        fiyat = float(data["offers"]["price"])
                        kaynak = "Migros (Metadata)"
                    elif "hasVariant" in data:
                        fiyat = float(data["hasVariant"][0]["offers"]["price"])
                        kaynak = "Migros (Metadata-V)"
                except:
                    # JSON başarısızsa klasik yöntemi dene
                    selectors = ["sm-product-price", ".product-price", "fe-product-price .amount", "#price-value"]
                    for sel in selectors:
                        if page.locator(sel).count() > 0:
                            el = page.locator(sel).first
                            val = temizle_fiyat(el.inner_text() or el.text_content())
                            if val: fiyat = val; kaynak = "Migros (CSS)"; break

            except Exception as e:
                if log_callback: log_callback(f"{log_msg}\n❌ Hata: {str(e)[:50]}")

            if fiyat and fiyat > 0:
                if log_callback: log_callback(f"{log_msg}\n✅ Fiyat: {fiyat:.2f} TL ({kaynak})")
                veriler.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d"),
                    "Zaman": datetime.now().strftime("%H:%M"),
                    "Kod": row.get('Kod'),
                    "Madde_Adi": row.get('Madde adı'),
                    "Fiyat": fiyat,
                    "Kaynak": kaynak,
                    "URL": url
                })
            else:
                if log_callback: log_callback(f"{log_msg}\n⚠️ Fiyat Bulunamadı")

            # Migros'u kızdırmamak için bekleme
            time.sleep(random.uniform(1.0, 2.0))

        browser.close()

    # Verileri Kaydet
    if veriler:
        df_new = pd.DataFrame(veriler)
        try:
            if not os.path.exists(FIYAT_DOSYASI):
                with pd.ExcelWriter(FIYAT_DOSYASI, engine='openpyxl') as writer:
                    df_new.to_excel(writer, sheet_name='Fiyat_Log', index=False)
            else:
                with pd.ExcelWriter(FIYAT_DOSYASI, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                    try:
                        start = writer.book['Fiyat_Log'].max_row
                    except:
                        start = 0
                    df_new.to_excel(writer, sheet_name='Fiyat_Log', index=False, header=False, startrow=start)
            return f"🍏 {len(veriler)} Gıda Ürünü Güncellendi!"
        except Exception as e:
            return f"Kayıt Hatası: {e}"

    return "❌ Veri Bulunamadı"


# --- DASHBOARD MODU ---
def dashboard_modu():
    # Veri Yükleme
    def veri_yukle():
        if not os.path.exists(FIYAT_DOSYASI): return None, None
        try:
            df_f = pd.read_excel(FIYAT_DOSYASI, sheet_name="Fiyat_Log")
            if df_f.empty: return pd.DataFrame(), None
            df_f['Tarih'] = pd.to_datetime(df_f['Tarih'])
            df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
            df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
            df_f.loc[df_f['Fiyat'] <= 0, 'Fiyat'] = np.nan

            df_s = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
            df_s['Kod'] = df_s['Kod'].astype(str).apply(kod_standartlastir)
            grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık",
                        "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta",
                        "12": "Çeşitli"}
            df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map)
            emoji_map = {"01": "🍎", "02": "🍷", "03": "👕", "04": "🏠", "05": "🛋️", "06": "💊", "07": "🚗", "08": "📱",
                         "09": "🎭", "10": "🎓", "11": "🍽️", "12": "💅"}
            df_s['Emoji'] = df_s['Kod'].str[:2].map(emoji_map).fillna("📦")
            return df_f, df_s
        except:
            return None, None

    df_fiyat, df_sepet = veri_yukle()

    # --- PIVOT VE ANALİZ ---
    if df_fiyat is not None and not df_fiyat.empty:
        df_fiyat['Gun'] = df_fiyat['Tarih'].dt.date
        df_fiyat['Is_Manuel'] = df_fiyat['Kaynak'].astype(str).str.contains('Manuel', na=False)

        def oncelik(x):
            return x[x['Is_Manuel']] if x['Is_Manuel'].any() else x

        df_clean = df_fiyat.groupby(['Kod', 'Gun']).apply(oncelik).reset_index(drop=True)
        pivot = df_clean.pivot_table(index='Kod', columns='Gun', values='Fiyat', aggfunc='mean').ffill(axis=1).bfill(
            axis=1)

        if not pivot.empty:
            df_analiz = pd.merge(df_sepet, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])
            gunler = sorted(pivot.columns)
            baz, son = gunler[0], gunler[-1]

            # Genel Trend
            trend_data = []
            for g in gunler:
                tmp = df_analiz.dropna(subset=[g, baz])
                if not tmp.empty:
                    val = ((tmp[g] / tmp[baz]) * 100 * tmp['Agirlik_2025']).sum() / tmp['Agirlik_2025'].sum()
                    trend_data.append({"Tarih": g, "TÜFE": val})
            df_trend = pd.DataFrame(trend_data)

            son_tufe = df_trend['TÜFE'].iloc[-1]
            enflasyon = ((son_tufe / df_trend['TÜFE'].iloc[0]) - 1) * 100

            df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
            top_artis = df_analiz.sort_values('Fark', ascending=False).iloc[0]

            # --- 🍏 GIDA ENFLASYONU HESAPLAMA ---
            df_gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            if not df_gida.empty:
                gida_baz_fiyat = (df_gida[baz] * df_gida['Agirlik_2025']).sum()
                gida_son_fiyat = (df_gida[son] * df_gida['Agirlik_2025']).sum()
                if gida_baz_fiyat > 0:
                    gida_enflasyonu = ((gida_son_fiyat / gida_baz_fiyat) - 1) * 100
                    gida_aylik = df_gida['Fark'].mean() * 100
                else:
                    gida_enflasyonu = 0
                    gida_aylik = 0
            else:
                gida_enflasyonu = 0
                gida_aylik = 0

            # --- 1. TICKER (KAYAN YAZI) ---
            ticker_html = ""
            top_up = df_analiz.sort_values('Fark', ascending=False).head(5)
            ticker_items = top_up
            for _, r in ticker_items.iterrows():
                val = r['Fark']
                ticker_html += f"<span style='color:#dc3545'>▲ {r['Madde adı']} %{val * 100:.1f}</span> &nbsp;&nbsp;&nbsp;&nbsp; "
            st.markdown(
                f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">PİYASA ÖZETİ: &nbsp;&nbsp; {ticker_html}</div></div></div>""",
                unsafe_allow_html=True)

            # --- 2. BAŞLIK VE METRİKLER ---
            st.title("🟡 ENFLASYON MONİTÖRÜ")

            # --- 3. TABS (SEKMELER) ---
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["GENEL BAKIŞ", "🍏 GIDA ENFLASYONU", "SEKTÖREL", "DETAYLI LİSTE", "SİMÜLASYON"])

            with tab1:
                # Genel Panel
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("GENEL ENDEKS", f"{son_tufe:.2f}", "Baz: 100")
                c2.metric("GENEL ENFLASYON", f"%{enflasyon:.2f}", delta_color="inverse")
                c3.metric("ZAM ŞAMPİYONU", f"{top_artis['Madde adı'][:12]}..", f"%{top_artis['Fark'] * 100:.1f}",
                          delta_color="inverse")
                c4.metric("VERİ GÜVENİ", f"%{100 - (df_analiz[son].isna().sum() / len(df_analiz) * 100):.0f}",
                          f"{len(gunler)} Gün")

                c_left, c_right = st.columns([2, 1])
                with c_left:
                    st.plotly_chart(px.area(df_trend, x='Tarih', y='TÜFE', color_discrete_sequence=['#ebc71d']),
                                    use_container_width=True)
                with c_right:
                    val = min(max(0, abs(enflasyon)), 50)
                    st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=val,
                                                           gauge={'axis': {'range': [None, 50]},
                                                                  'bar': {'color': "#dc3545"}, 'bgcolor': "white"})),
                                    use_container_width=True)

            with tab2:
                # 🍏 ÖZEL GIDA ENFLASYONU SEKME 🍏
                st.subheader("🍏 Mutfak Enflasyonu (Migros Endeksi)")
                if not df_gida.empty:
                    kg1, kg2, kg3 = st.columns(3)
                    kg1.metric("GIDA ENFLASYONU (Kümülatif)", f"%{gida_enflasyonu:.2f}", delta_color="inverse")
                    kg2.metric("Ortalama Gıda Artışı", f"%{gida_aylik:.2f}")
                    kg3.metric("Takip Edilen Ürün", f"{len(df_gida)} Adet")

                    st.markdown("#### 🥦 Gıda Ürünlerinde Değişim")

                    # --- HATA DÜZELTME ALANI ---
                    # Önce veriyi hazırlıyoruz
                    df_gida_show = df_gida[['Madde adı', 'Fark', son]].sort_values('Fark', ascending=False)

                    # KRİTİK DÜZELTME: Kolon adı olan 'son' (Tarih objesi) yerine string kullanıyoruz.
                    # Kolon adını 'Son_Tutar' olarak değiştiriyoruz ki JSON hatası vermesin.
                    df_gida_show = df_gida_show.rename(columns={son: "Son_Tutar"})

                    st.dataframe(
                        df_gida_show,
                        column_config={
                            "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f%%", min_value=-0.5,
                                                                    max_value=0.5),
                            "Son_Tutar": st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                        },
                        hide_index=True, use_container_width=True
                    )
                else:
                    st.warning("Henüz 01 kodlu Gıda verisi bulunamadı.")

            with tab3:
                df_analiz['Grup_Degisim'] = df_analiz.groupby('Grup')['Fark'].transform('mean') * 100
                grup_data = df_analiz[['Grup', 'Grup_Degisim']].drop_duplicates().sort_values('Grup_Degisim')
                st.plotly_chart(go.Figure(go.Bar(y=grup_data['Grup'], x=grup_data['Grup_Degisim'], orientation='h',
                                                 marker=dict(color=grup_data['Grup_Degisim'], colorscale='RdYlGn_r'))),
                                use_container_width=True)

            with tab4:
                st.dataframe(df_analiz[['Emoji', 'Madde adı', 'Grup', 'Fark', son]], use_container_width=True)

            with tab5:
                st.info("Kutucuklara beklediğiniz % zam oranını girin.")
                cols = st.columns(4)
                sim_inputs = {grp: cols[i % 4].number_input(f"{grp} (%)", -100.0, 100.0, 0.0) for i, grp in
                              enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in sim_inputs.items()])
                st.metric("Simüle Enflasyon", f"%{enflasyon + etki:.2f}", f"{etki:+.2f}% Etki", delta_color="inverse")

    else:
        st.info("⚠️ Veri Bulunamadı. Lütfen Botu Çalıştırın.")

    # --- YÖNETİM PANELİ ---
    st.markdown('<div class="admin-panel"><div class="admin-header">⚙️ SİSTEM YÖNETİMİ</div>', unsafe_allow_html=True)
    c_load, c_bot, c_migros = st.columns(3)

    with c_load:
        st.markdown("**📂 Excel Yükle**")
        uf = st.file_uploader("", type=['xlsx'], label_visibility="collapsed")
        if uf:
            pd.read_excel(uf).to_excel(FIYAT_DOSYASI, sheet_name='Fiyat_Log', index=False)
            st.success("Yüklendi!")
            time.sleep(1);
            st.rerun()

    with c_bot:
        st.markdown("**⚠️ Genel Bot (Tümü)**")
        if st.button("Tüm Verileri Çek", use_container_width=True):
            st.warning("Bu mod şu an pasif. Migros modunu kullanın.")

    with c_migros:
        st.markdown("**🍏 Gıda Enflasyonu**")
        # ÖZEL TURUNCU BUTON (CSS ile renklendirildi)
        st.markdown('<div class="migros-btn">', unsafe_allow_html=True)
        if st.button("🍏 GIDA HESAPLA (MİGROS)", type="primary", use_container_width=True):
            log_container = st.empty()

            def log_yazici(mesaj):
                log_container.code(mesaj, language="yaml")

            sonuc = migros_gida_botu(log_yazici)

            if "Güncellendi" in sonuc:
                st.success(sonuc)
                time.sleep(2)
                st.rerun()
            else:
                st.error(sonuc)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="signature">Fatih Arslan Tarafından yapılmıştır</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()