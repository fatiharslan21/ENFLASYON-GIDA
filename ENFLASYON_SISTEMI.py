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
# --- 🤖 GÜNCELLENMİŞ MİGROS GIDA BOTU (Terminator Modu) 🤖 ---
# --- 🚀 MİGROS TURBO BOT (GÖRSELSİZ & HIZLI) 🚀 ---
# --- ⚡ AKILLI TURBO MOD (Resimsiz ama Garantili) ⚡ ---
def migros_gida_botu(log_callback=None):
    if log_callback: log_callback("⚡ Akıllı Hız Modu: Görseller Kapalı, Veri Odaklı...")
    install_browsers()

    try:
        df = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        mask = (df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False, na=False))
        takip = df[mask].copy()
        if takip.empty: return "⚠️ Listede '01' kodlu MİGROS ürünü bulunamadı!"
    except Exception as e:
        return f"Excel Hatası: {e}"

    veriler = []
    total = len(takip)

    if log_callback: log_callback(f"🏎️ {total} Ürün Taranıyor...")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        )

        page = context.new_page()

        # --- OPTİMİZASYON AYARI ---
        # Sadece görselleri, medyayı ve fontları engelliyoruz.
        # Stylesheet (CSS) açık kalmalı yoksa Migros veriyi oluşturamıyor.
        page.route("**/*", lambda route: route.abort()
        if route.request.resource_type in ["image", "media", "font"]
        else route.continue_())

        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for i, row in takip.iterrows():
            urun_adi = str(row.get('Madde adı', 'Bilinmeyen'))[:25]
            url = row['URL']

            if log_callback: log_callback(f"⚡ [{i + 1}/{total}] {urun_adi}...")

            fiyat = 0.0
            kaynak = ""

            try:
                # Sayfaya git
                page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # Sleep YOK. Onun yerine elemanı bekleme var.
                # JSON verisi veya Fiyat etiketi hangisi önce gelirse onu kapacağız.

                # 1. YÖNTEM: JSON-LD (En Temiz Veri)
                try:
                    # Maksimum 3 saniye JSON scriptini bekle (Varsa hemen alır, yoksa hata verir geçer)
                    page.wait_for_selector("script[type='application/ld+json']", timeout=3000)
                    json_data = page.locator("script[type='application/ld+json']").first.inner_text()
                    data = json.loads(json_data)

                    if "offers" in data and "price" in data["offers"]:
                        fiyat = float(data["offers"]["price"])
                        kaynak = "Meta"
                    elif "hasVariant" in data:
                        fiyat = float(data["hasVariant"][0]["offers"]["price"])
                        kaynak = "Varyant"
                except:
                    pass

                # 2. YÖNTEM: Görsel Seçiciler (Eğer JSON gelmediyse)
                if fiyat == 0:
                    try:
                        # Fiyat etiketini bekle (En fazla 2 sn)
                        # Geldiği an alır, sleep gibi boşuna beklemez.
                        el = page.wait_for_selector(
                            "sm-product-price .amount, .product-price, #price-value",
                            timeout=2000
                        )
                        if el:
                            val = temizle_fiyat(el.inner_text())
                            if val: fiyat = val; kaynak = "CSS"
                    except:
                        pass

                # 3. YÖNTEM: Regex (Acil Durum)
                if fiyat == 0:
                    try:
                        body_text = page.locator("body").inner_text()
                        bulunanlar = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', body_text)
                        fiyatlar = [temizle_fiyat(x) for x in bulunanlar if temizle_fiyat(x)]
                        if fiyatlar: fiyat = fiyatlar[0]; kaynak = "Regex"
                    except:
                        pass

            except Exception as e:
                pass

            if fiyat and fiyat > 0:
                if log_callback: log_callback(f"✅ {fiyat} TL")
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
                if log_callback: log_callback("❌ Bulunamadı")

        browser.close()

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
            return f"🏁 Tamamlandı! {len(veriler)} fiyat alındı."
        except Exception as e:
            return f"Kayıt Hatası: {e}"

    return "Veri Yok"


# --- DASHBOARD MODU ---
# --- 📊 GÜNCELLENMİŞ DASHBOARD (ANLIK GÜNCELLEME GARANTİLİ) 📊 ---
def dashboard_modu():
    # 1. VERİ YÜKLEME (Cache Yok - Her Seferinde Taze Okur)
    def veri_yukle():
        if not os.path.exists(FIYAT_DOSYASI): return None, None
        try:
            # Fiyatları Oku
            df_f = pd.read_excel(FIYAT_DOSYASI, sheet_name="Fiyat_Log")
            if df_f.empty: return pd.DataFrame(), None

            # Tarih ve Saat Düzenlemesi
            df_f['Tarih'] = pd.to_datetime(df_f['Tarih'])
            df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
            df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')

            # Fiyatı 0 veya Boş Olanları Temizle (Grafiği Bozmasın)
            df_f = df_f[df_f['Fiyat'] > 0]

            # Sepet Ağırlıklarını Oku
            df_s = pd.read_excel(EXCEL_DOSYASI, sheet_name=SAYFA_ADI, dtype={'Kod': str})
            df_s['Kod'] = df_s['Kod'].astype(str).apply(kod_standartlastir)

            # Gruplandırma ve Emoji
            grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık",
                        "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta",
                        "12": "Çeşitli"}
            emoji_map = {"01": "🍎", "02": "🍷", "03": "👕", "04": "🏠", "05": "🛋️", "06": "💊", "07": "🚗", "08": "📱",
                         "09": "🎭", "10": "🎓", "11": "🍽️", "12": "💅"}
            df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map)
            df_s['Emoji'] = df_s['Kod'].str[:2].map(emoji_map).fillna("📦")

            return df_f, df_s
        except:
            return None, None

    df_fiyat, df_sepet = veri_yukle()

    # --- 2. HESAPLAMA MOTORU (DÜZELTİLDİ) ---
    if df_fiyat is not None and not df_fiyat.empty:
        # Tarih ve Saat sütununu birleştirip sıralama yapıyoruz (En son veriyi bulmak için)
        # Eğer 'Zaman' sütunu varsa kullan, yoksa sadece Tarih
        if 'Zaman' in df_fiyat.columns:
            df_fiyat['Tam_Zaman'] = pd.to_datetime(df_fiyat['Tarih'].astype(str) + ' ' + df_fiyat['Zaman'].astype(str),
                                                   errors='coerce')
        else:
            df_fiyat['Tam_Zaman'] = df_fiyat['Tarih']

        df_fiyat = df_fiyat.sort_values('Tam_Zaman')  # Eskiden yeniye sırala
        df_fiyat['Gun'] = df_fiyat['Tarih'].dt.date

        # Manuel mi?
        df_fiyat['Is_Manuel'] = df_fiyat['Kaynak'].astype(str).str.contains('Manuel', na=False)

        # Temizlik ve Önceliklendirme
        # Aynı gün hem Otomatik hem Manuel varsa Manuel'i al.
        # Aynı gün 3 tane Otomatik varsa EN SONUNCUSUNU al (aggfunc='last')
        def veri_hazirla(df):
            # Pivot Table: Satırlar Kod, Sütunlar Gün, Değer Fiyat
            # aggfunc='last' -> O günkü EN SON fiyatı alır. (Ortalama almaz!)
            piv = df.pivot_table(index='Kod', columns='Gun', values='Fiyat', aggfunc='last')
            # Eksik günleri önceki günden tamamla (Forward Fill)
            piv = piv.ffill(axis=1).bfill(axis=1)
            return piv

        pivot = veri_hazirla(df_fiyat)

        if not pivot.empty:
            # Sepet ile Fiyatları Birleştir
            df_analiz = pd.merge(df_sepet, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])

            gunler = sorted(pivot.columns)
            baz_gun = gunler[0]
            son_gun = gunler[-1]  # En son veri tarihi (Bugün)

            # --- ANA METRİKLERİ HESAPLA ---

            # 1. Genel Enflasyon
            # Endeks Formülü: (Son Fiyat * Ağırlık) / (Baz Fiyat * Ağırlık)
            toplam_agirlik = df_analiz['Agirlik_2025'].sum()

            # Tarihçeli Trend Verisi
            trend_data = []
            for g in gunler:
                temp = df_analiz.dropna(subset=[g, baz_gun])
                if not temp.empty:
                    # Laspeyres Benzeri Endeks Hesabı
                    # Puan = (O günkü Fiyat / Baz Fiyat) * Ağırlık
                    temp['Puan'] = (temp[g] / temp[baz_gun]) * temp['Agirlik_2025']
                    endeks_degeri = (temp['Puan'].sum() / temp['Agirlik_2025'].sum()) * 100
                    trend_data.append({"Tarih": g, "TÜFE": endeks_degeri})

            df_trend = pd.DataFrame(trend_data)
            son_endeks = df_trend['TÜFE'].iloc[-1]
            genel_enflasyon = ((son_endeks / 100) - 1) * 100

            # Ürün Bazlı Değişim (Son Gün vs Baz Gün)
            df_analiz['Fark'] = (df_analiz[son_gun] / df_analiz[baz_gun]) - 1
            top_artis = df_analiz.sort_values('Fark', ascending=False).iloc[0]

            # --- 🍏 GIDA ENFLASYONU HESAPLAMA (ÖZEL) ---
            df_gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            if not df_gida.empty:
                # Gıda Ağırlıklı Ortalaması
                # Formül: Σ(SonFiyat/BazFiyat * Ağırlık) / Σ(Ağırlık) - 1
                df_gida['Gida_Endeks_Etkisi'] = (df_gida[son_gun] / df_gida[baz_gun]) * df_gida['Agirlik_2025']
                gida_endeks = df_gida['Gida_Endeks_Etkisi'].sum() / df_gida['Agirlik_2025'].sum()
                gida_enflasyonu = (gida_endeks - 1) * 100

                # Aylık/Günlük Ortalama Basit Değişim
                gida_aylik = df_gida['Fark'].mean() * 100
            else:
                gida_enflasyonu = 0;
                gida_aylik = 0

            # --- 🎨 ARAYÜZ KISMI 🎨 ---

            # Ticker
            ticker_html = ""
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(5).iterrows():
                ticker_html += f"<span style='color:#dc3545'>▲ {r['Madde adı']} %{r['Fark'] * 100:.1f}</span> &nbsp;&nbsp; "
            st.markdown(
                f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">PİYASA: &nbsp; {ticker_html}</div></div></div>""",
                unsafe_allow_html=True)

            st.title("🟡 ENFLASYON MONİTÖRÜ")

            # SEKMELER
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["GENEL BAKIŞ", "🍏 GIDA ENFLASYONU", "SEKTÖREL", "DETAYLI LİSTE", "SİMÜLASYON"])

            with tab1:  # Genel
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("GENEL ENDEKS", f"{son_endeks:.2f}", "Baz: 100")
                c2.metric("GENEL ENFLASYON", f"%{genel_enflasyon:.2f}", delta_color="inverse")
                c3.metric("ZAM ŞAMPİYONU", f"{top_artis['Madde adı'][:10]}..", f"%{top_artis['Fark'] * 100:.1f}",
                          delta_color="inverse")
                c4.metric("VERİ TARİHİ", str(son_gun), f"{len(gunler)} Günlük Veri")
                st.plotly_chart(px.area(df_trend, x='Tarih', y='TÜFE', color_discrete_sequence=['#ebc71d']),
                                use_container_width=True)

            with tab2:  # 🍏 GIDA
                st.subheader("🍏 Mutfak Enflasyonu (Migros Endeksi)")
                if not df_gida.empty:
                    kg1, kg2, kg3 = st.columns(3)
                    kg1.metric("GIDA ENFLASYONU", f"%{gida_enflasyonu:.2f}", "Kümülatif", delta_color="inverse")
                    kg2.metric("Ortalama Ürün Artışı", f"%{gida_aylik:.2f}")
                    kg3.metric("Takip Edilen Ürün", f"{len(df_gida)} Adet")

                    st.divider()
                    st.markdown("#### 🥦 Ürün Bazlı Değişimler")

                    # Tablo Hazırlığı (JSON Hatası Çözümü İçin Rename)
                    df_show = df_gida[['Madde adı', 'Fark', son_gun]].sort_values('Fark', ascending=False)
                    df_show = df_show.rename(columns={son_gun: "Son_Tutar"})  # Tarih objesini string isme çevir

                    st.dataframe(
                        df_show,
                        column_config={
                            "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f%%", min_value=-0.5,
                                                                    max_value=0.5),
                            "Son_Tutar": st.column_config.NumberColumn("Son Fiyat", format="%.2f ₺")
                        },
                        hide_index=True, use_container_width=True
                    )
                else:
                    st.warning("Gıda verisi bulunamadı.")

            with tab3:  # Sektörel
                df_analiz['Grup_Degisim'] = df_analiz.groupby('Grup')['Fark'].transform('mean') * 100
                grp = df_analiz[['Grup', 'Grup_Degisim']].drop_duplicates().sort_values('Grup_Degisim')
                st.plotly_chart(go.Figure(go.Bar(y=grp['Grup'], x=grp['Grup_Degisim'], orientation='h',
                                                 marker=dict(color=grp['Grup_Degisim'], colorscale='RdYlGn_r'))),
                                use_container_width=True)

            with tab4:  # Detaylı
                st.dataframe(df_analiz[['Emoji', 'Madde adı', 'Grup', 'Fark']], use_container_width=True)

            with tab5:  # Simülasyon
                st.info("Beklenen zam oranlarını giriniz.")
                cols = st.columns(4)
                sim_inputs = {grp: cols[i % 4].number_input(f"{grp} (%)", -100.0, 100.0, 0.0) for i, grp in
                              enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in sim_inputs.items()])
                st.metric("Simüle Enflasyon", f"%{genel_enflasyon + etki:.2f}", f"{etki:+.2f}% Etki",
                          delta_color="inverse")

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
            st.success("Yüklendi!");
            time.sleep(1);
            st.rerun()

    with c_bot:
        st.markdown("**⚠️ Genel Bot**")
        st.button("Tüm Verileri Çek", disabled=True)  # Pasif yaptık

    with c_migros:
        st.markdown("**🍏 Gıda Enflasyonu**")
        st.markdown('<div class="migros-btn">', unsafe_allow_html=True)
        if st.button("🍏 GIDA HESAPLA (MİGROS)", type="primary", use_container_width=True):
            log_cont = st.empty()
            # Botu Çalıştır
            sonuc = migros_gida_botu(lambda m: log_cont.code(m, language="yaml"))

            if "Güncellendi" in sonuc or "Tamamlandı" in sonuc:
                st.success(sonuc)
                # ÖNBELLEĞİ TEMİZLE VE YENİLE
                st.cache_data.clear()
                time.sleep(2)
                st.rerun()
            else:
                st.error(sonuc)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="signature">Fatih Arslan Tarafından yapılmıştır</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()