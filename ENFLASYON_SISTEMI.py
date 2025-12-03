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

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="ENFLASYON MONITORU", page_icon="🍏", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ---
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stToolbar"] {visibility: hidden !important;} 
        .stDeployButton {display:none !important;} 
        footer {visibility: hidden;} 
        #MainMenu {visibility: hidden;}
        .stApp {background-color: #F8F9FA; color: #212529;}
        div[data-testid="metric-container"] {
            background: #FFFFFF; border: 1px solid #EAEDF0; border-radius: 12px; padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.02);
        }
        .admin-panel {
            background-color: #FFFFFF; border-top: 4px solid #ebc71d; padding: 30px;
            border-radius: 15px; margin-top: 50px; box-shadow: 0 -5px 25px rgba(0,0,0,0.05);
        }
        .migros-btn button {
            background-color: #f68b1f !important; color: white !important;
            border: none !important; padding: 10px 20px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA TANIMLARI ---
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


def install_browsers():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "firefox"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps", "firefox"], check=False)
    except:
        pass


# --- 🤖 MİGROS BOTU (DATA APPENDER) 🤖 ---
def migros_gida_botu(log_callback=None):
    if log_callback: log_callback("⚡ Başlatılıyor...")
    install_browsers()

    # Listeyi Oku
    try:
        df = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()
        if takip.empty: return "⚠️ Listede Migros Gıda ürünü yok!"
    except Exception as e:
        return f"Excel Hatası: {e}"

    veriler = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        # Hız için görsel engelleme
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media",
                                                                                          "font"] else route.continue_())
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        total = len(takip)
        for i, row in takip.iterrows():
            urun_adi = str(row.get('Madde adı', '---'))[:20]
            url = row['URL']

            if log_callback: log_callback(f"🛒 [{i + 1}/{total}] {urun_adi}...")

            fiyat = 0.0

            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                # Hızlıca JSON kontrolü
                try:
                    json_data = page.locator("script[type='application/ld+json']").first.inner_text()
                    data = json.loads(json_data)
                    if "offers" in data and "price" in data["offers"]:
                        fiyat = float(data["offers"]["price"])
                    elif "hasVariant" in data:
                        fiyat = float(data["hasVariant"][0]["offers"]["price"])
                except:
                    # JSON yoksa CSS
                    try:
                        el = page.wait_for_selector("sm-product-price .amount, .product-price, #price-value",
                                                    timeout=1500)
                        if el:
                            val = temizle_fiyat(el.inner_text())
                            if val: fiyat = val
                    except:
                        pass
            except:
                pass

            if fiyat > 0:
                if log_callback: log_callback(f"✅ {fiyat} TL")
                veriler.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d"),
                    "Zaman": datetime.now().strftime("%H:%M"),
                    "Kod": row.get('Kod'),
                    "Madde_Adi": row.get('Madde adı'),
                    "Fiyat": fiyat,
                    "Kaynak": "Migros Bot",
                    "URL": url
                })
            else:
                if log_callback: log_callback("❌ Bulunamadı")

        browser.close()

    # --- VERİTABANINA EKLEME KISMI ---
    if veriler:
        df_new = pd.DataFrame(veriler)
        try:
            if not os.path.exists(FIYAT_DOSYASI):
                with pd.ExcelWriter(FIYAT_DOSYASI, engine='openpyxl') as writer:
                    df_new.to_excel(writer, sheet_name='Fiyat_Log', index=False)
            else:
                # Mevcut dosyanın altına ekle (Append)
                with pd.ExcelWriter(FIYAT_DOSYASI, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                    try:
                        start = writer.book['Fiyat_Log'].max_row
                    except:
                        start = 0
                    df_new.to_excel(writer, sheet_name='Fiyat_Log', index=False, header=False, startrow=start)
            return "OK"
        except Exception as e:
            return f"Yazma Hatası: {e}"

    return "Veri Yok"


# --- 📊 ANA UYGULAMA 📊 ---
def main():
    # --- VERİ OKUMA (CACHE YOK - HER SEFERİNDE DİSKTEN OKUR) ---
    def get_data():
        if not os.path.exists(FIYAT_DOSYASI) or not os.path.exists(EXCEL_DOSYASI):
            return None, None

        try:
            # Fiyatlar
            df_f = pd.read_excel(FIYAT_DOSYASI, sheet_name="Fiyat_Log")
            if df_f.empty: return None, None

            # Tipler
            df_f['Tarih'] = pd.to_datetime(df_f['Tarih'])
            df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
            df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
            df_f = df_f[df_f['Fiyat'] > 0]

            # Sıralama (En güncel en altta)
            if 'Zaman' in df_f.columns:
                df_f['Tam_Zaman'] = pd.to_datetime(df_f['Tarih'].astype(str) + ' ' + df_f['Zaman'].astype(str),
                                                   errors='coerce')
                df_f = df_f.sort_values('Tam_Zaman')

            # Sepet
            df_s = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
            df_s['Kod'] = df_s['Kod'].astype(str).apply(kod_standartlastir)

            # Mapping
            grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık",
                        "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta",
                        "12": "Çeşitli"}
            df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map)

            return df_f, df_s
        except:
            return None, None

    # Veriyi Çek
    df_fiyat, df_sepet = get_data()

    # --- HESAPLAMALAR ---
    son_gun = date.today()
    genel_enflasyon = 0
    gida_enflasyonu = 0
    gida_aylik = 0
    df_gida_show = pd.DataFrame()
    top_artis = None

    # Eğer veri varsa hesapla
    if df_fiyat is not None and not df_fiyat.empty:
        df_fiyat['Gun'] = df_fiyat['Tarih'].dt.date
        # Pivot (Günlük Son Fiyat)
        pivot = df_fiyat.pivot_table(index='Kod', columns='Gun', values='Fiyat', aggfunc='last')
        pivot = pivot.ffill(axis=1).bfill(axis=1)

        if not pivot.empty:
            df_analiz = pd.merge(df_sepet, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])
            gunler = sorted(pivot.columns)
            baz_gun, son_gun = gunler[0], gunler[-1]

            # 1. Genel Enflasyon
            df_analiz['Puan'] = (df_analiz[son_gun] / df_analiz[baz_gun]) * df_analiz['Agirlik_2025']
            son_endeks = (df_analiz['Puan'].sum() / df_analiz['Agirlik_2025'].sum()) * 100
            genel_enflasyon = (son_endeks / 100 - 1) * 100

            # 2. Değişimler
            df_analiz['Fark'] = (df_analiz[son_gun] / df_analiz[baz_gun]) - 1
            top_artis = df_analiz.sort_values('Fark', ascending=False).iloc[0]

            # 3. Gıda Enflasyonu
            df_gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            if not df_gida.empty:
                df_gida['Etki'] = (df_gida[son_gun] / df_gida[baz_gun]) * df_gida['Agirlik_2025']
                gida_endeks = df_gida['Etki'].sum() / df_gida['Agirlik_2025'].sum()
                gida_enflasyonu = (gida_endeks - 1) * 100
                gida_aylik = df_gida['Fark'].mean() * 100

                # Tablo için hazırlık
                df_gida_show = df_gida[['Madde adı', 'Fark', son_gun]].sort_values('Fark', ascending=False)
                df_gida_show = df_gida_show.rename(columns={son_gun: "Son_Tutar"})

    # --- ARAYÜZ ---
    st.title("🟡 ENFLASYON MONİTÖRÜ")
    st.caption(f"📅 Veri Tarihi: {son_gun} (Oto-Yenileme Aktif)")

    tab1, tab2 = st.tabs(["GENEL BAKIŞ", "🍏 GIDA ENFLASYONU"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("GENEL ENFLASYON", f"%{genel_enflasyon:.2f}")
        if top_artis is not None:
            c2.metric("ZAM ŞAMPİYONU", f"{top_artis['Madde adı'][:10]}", f"%{top_artis['Fark'] * 100:.1f}")
        c3.metric("VERİ DURUMU", "AKTİF", f"{len(df_fiyat) if df_fiyat is not None else 0} Kayıt")

    with tab2:
        st.subheader("🍏 Migros Gıda Endeksi")
        kg1, kg2 = st.columns(2)
        kg1.metric("GIDA ENFLASYONU", f"%{gida_enflasyonu:.2f}", delta_color="inverse")
        kg2.metric("Ortalama Artış", f"%{gida_aylik:.2f}")

        st.divider()
        if not df_gida_show.empty:
            st.dataframe(
                df_gida_show,
                column_config={
                    "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f%%", min_value=-0.5, max_value=0.5),
                    "Son_Tutar": st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                },
                hide_index=True, use_container_width=True
            )
        else:
            st.warning("Veri bekleniyor...")

    # --- YÖNETİM PANELİ ---
    st.markdown('<div class="admin-panel">', unsafe_allow_html=True)
    c_load, c_bot = st.columns([1, 2])

    with c_load:
        uf = st.file_uploader("Excel Yükle", type=['xlsx'], label_visibility="collapsed")
        if uf:
            pd.read_excel(uf).to_excel(FIYAT_DOSYASI, sheet_name='Fiyat_Log', index=False)
            st.success("Yüklendi!");
            time.sleep(1);
            st.cache_data.clear();
            st.rerun()

    with c_bot:
        st.markdown('<div class="migros-btn">', unsafe_allow_html=True)
        # BUTONA BASINCA OLANLAR
        if st.button("🍏 GIDA HESAPLA (MİGROS)", use_container_width=True):
            log_box = st.empty()

            # 1. BOTU ÇALIŞTIR
            sonuc = migros_gida_botu(lambda m: log_box.code(m, language="yaml"))

            # 2. BAŞARILIYSA ZORLA YENİLE
            if "OK" in sonuc:
                st.success("Veritabanı Güncellendi! Sayfa Yenileniyor...")
                # BU İKİ SATIR HAYAT KURTARIR:
                st.cache_data.clear()  # 1. Hafızayı sil
                time.sleep(1)  # 2. Dosya yazılsın diye bekle
                st.rerun()  # 3. Sayfayı yeniden başlat
            else:
                st.error(sonuc)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()