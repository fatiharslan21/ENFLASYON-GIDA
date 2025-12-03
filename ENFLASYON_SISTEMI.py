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
st.set_page_config(page_title="ENFLASYON MONITORU PRO", page_icon="💸", layout="wide", initial_sidebar_state="collapsed")

# --- WHITE THEME & ULTRA UI CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');

        .stApp { background-color: #f8fafc; color: #0f172a; font-family: 'Inter', sans-serif; }
        [data-testid="stSidebar"], [data-testid="stToolbar"], .stDeployButton, footer, #MainMenu {display: none !important;}

        /* TICKER */
        .ticker-wrap {
            width: 100%; overflow: hidden; background: #ffffff; border-bottom: 2px solid #3b82f6;
            white-space: nowrap; padding: 14px 0; margin-bottom: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);
        }
        .ticker { display: inline-block; animation: ticker 60s linear infinite; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-weight: 600; font-size: 14px; color: #334151; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* KARTLAR */
        div[data-testid="metric-container"] {
            background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: all 0.3s ease;
        }
        div[data-testid="metric-container"]:hover { transform: translateY(-4px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); border-color: #3b82f6; }

        /* TABLOLAR */
        .stDataFrame { border-radius: 12px; border: 1px solid #e2e8f0; background: white; overflow: hidden; }

        /* ACTION BUTTON */
        .action-btn button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important; color: white !important;
            border: none !important; height: 80px; font-size: 20px !important; font-weight: 700 !important;
            border-radius: 20px !important; box-shadow: 0 10px 25px rgba(37, 99, 235, 0.25); width: 100%;
            text-transform: uppercase; transition: all 0.3s ease;
        }
        .action-btn button:hover { transform: translateY(-2px); box-shadow: 0 20px 30px rgba(37, 99, 235, 0.35); }

        /* SEKMELER */
        .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #e2e8f0; gap: 24px; }
        .stTabs [data-baseweb="tab"] { font-weight: 600; color: #64748b; font-size: 15px; padding: 12px 0; border: none; }
        .stTabs [aria-selected="true"] { color: #3b82f6; border-bottom: 3px solid #3b82f6; }

        /* BAŞLIK */
        .main-title { font-size: 48px; font-weight: 900; color: #0f172a; text-align: center; margin-bottom: 5px; letter-spacing: -1.5px; }
        .sub-title { font-size: 15px; font-weight: 500; color: #64748b; text-align: center; margin-bottom: 40px; }

        /* BOT MESAJ KUTUSU */
        .bot-msg {
            background-color: #eff6ff; border-left: 5px solid #3b82f6; padding: 25px; border-radius: 12px;
            font-size: 16px; line-height: 1.6; color: #1e3a8a; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .bot-bad { border-left-color: #ef4444; background-color: #fef2f2; color: #991b1b; }
        .bot-good { border-left-color: #22c55e; background-color: #f0fdf4; color: #166534; }

        /* INPUT STİLİ */
        .stTextInput input {
            padding: 15px; font-size: 18px; border-radius: 12px; border: 2px solid #e2e8f0;
        }
        .stTextInput input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }
    </style>
""", unsafe_allow_html=True)

# --- 2. AYARLAR ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


# --- GITHUB ---
def get_github_repo():
    try:
        g = Github(st.secrets["github"]["token"])
        return g.get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


def github_excel_oku(dosya_adi, sayfa_adi=None):
    repo = get_github_repo()
    if not repo: return pd.DataFrame()
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        return pd.read_excel(BytesIO(c.decoded_content), sheet_name=sayfa_adi,
                             dtype={'Kod': str}) if sayfa_adi else pd.read_excel(BytesIO(c.decoded_content))
    except:
        return pd.DataFrame()


def github_excel_guncelle(df_yeni, dosya_adi):
    repo = get_github_repo()
    if not repo: return "Repo Yok"
    try:
        try:
            c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            old = pd.read_excel(BytesIO(c.decoded_content))
            yeni_tarih = df_yeni['Tarih'].iloc[0]
            old = old[~((old['Tarih'].astype(str) == str(yeni_tarih)) & (old['Kod'].isin(df_yeni['Kod'])))]
            final = pd.concat([old, df_yeni], ignore_index=True)
        except:
            c = None;
            final = df_yeni

        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            final.to_excel(w, index=False, sheet_name='Fiyat_Log')

        if c:
            repo.update_file(c.path, "Update", out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, "Create", out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# --- HELPER ---
def kod_standartlastir(k): return str(k).replace('.0', '').strip().zfill(7)


def temizle_fiyat(t):
    t = str(t).replace('TL', '').replace('₺', '').strip()
    t = t.replace('.', '').replace(',', '.') if ',' in t and '.' in t else t.replace(',', '.')
    try:
        return float(re.sub(r'[^\d.]', '', t))
    except:
        return None


def install_browsers():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "firefox"], check=True); subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps", "firefox"], check=False)
    except:
        pass


# --- BOT ---
def migros_gida_botu(cb=None):
    if cb: cb("⚡ Bot Başlatılıyor...")
    install_browsers()
    try:
        df = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        if df.empty: return "Liste Boş"
        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        takip = df[(df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False))].copy()
    except:
        return "Hata"

    veriler = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        for _, row in takip.iterrows():
            url = row['URL']
            if cb: cb(f"🔍 Taranıyor: {row.get('Madde adı')[:20]}")
            fiyat = 0.0
            try:
                page.goto(url, timeout=30000);
                time.sleep(1)
                try:
                    d = json.loads(page.locator("script[type='application/ld+json']").first.inner_text())
                    if "offers" in d: fiyat = float(d["offers"]["price"])
                except:
                    pass
                if fiyat == 0:
                    for sel in ["span:has(span.currency)", "#sale-price", ".sale-price", ".amount"]:
                        if page.locator(sel).count():
                            fiyat = temizle_fiyat(page.locator(sel).first.inner_text());
                            break
            except:
                pass
            if fiyat > 0:
                veriler.append({"Tarih": datetime.now().strftime("%Y-%m-%d"), "Zaman": datetime.now().strftime("%H:%M"),
                                "Kod": row['Kod'], "Madde_Adi": row['Madde adı'], "Fiyat": fiyat,
                                "Kaynak": "Sanal Market", "URL": url})
        browser.close()

    if veriler:
        if cb: cb("💾 Kaydediliyor...")
        return github_excel_guncelle(pd.DataFrame(veriler), FIYAT_DOSYASI)
    return "Veri Yok"


# --- DASHBOARD ---
def dashboard_modu():
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    if not df_f.empty and not df_s.empty:
        df_f['Tarih'] = pd.to_datetime(df_f['Tarih'])
        df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
        df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
        df_f = df_f[df_f['Fiyat'] > 0]
        df_s['Kod'] = df_s['Kod'].astype(str).apply(kod_standartlastir)
        df_s['Grup'] = df_s['Kod'].str[:2].map(
            {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık", "07": "Ulaşım",
             "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta", "12": "Çeşitli"})

        if 'Zaman' in df_f.columns:
            df_f['Tam_Zaman'] = pd.to_datetime(df_f['Tarih'].astype(str) + ' ' + df_f['Zaman'].astype(str),
                                               errors='coerce')
        else:
            df_f['Tam_Zaman'] = df_f['Tarih']

        pivot = df_f.sort_values('Tam_Zaman').pivot_table(index='Kod', columns=df_f['Tarih'].dt.date, values='Fiyat',
                                                          aggfunc='last').ffill(axis=1).bfill(axis=1)

        if not pivot.empty:
            df_analiz = pd.merge(df_s, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])
            gunler = sorted(pivot.columns);
            baz, son = gunler[0], gunler[-1]

            trend = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])['Agirlik_2025'] * (
                        df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                              'Agirlik_2025'].sum() * 100} for g in gunler]
            df_trend = pd.DataFrame(trend)
            genel_enf = (df_trend['TÜFE'].iloc[-1] / 100 - 1) * 100

            df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
            top = df_analiz.sort_values('Fark', ascending=False).iloc[0]

            gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            gida_enf = ((gida[son] / gida[baz] * gida['Agirlik_2025']).sum() / gida[
                'Agirlik_2025'].sum() - 1) * 100 if not gida.empty else 0

            # UI
            tkr = " &nbsp;&nbsp; ".join([
                                            f"<span style='color:{'#dc2626' if r['Fark'] > 0 else '#16a34a'}'>{r['Madde adı']} {'▲' if r['Fark'] > 0 else '▼'} %{r['Fark'] * 100:.1f}</span>"
                                            for _, r in
                                            df_analiz.sort_values('Fark', ascending=False).head(15).iterrows()])
            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{tkr}</div></div></div>',
                unsafe_allow_html=True)
            st.markdown('<div class="main-title">ENFLASYON MONİTÖRÜ</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sub-title">Son Güncelleme: {son}</div>', unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("GENEL ENDEKS", f"{df_trend['TÜFE'].iloc[-1]:.2f}")
            c2.metric("GENEL ENFLASYON", f"%{genel_enf:.2f}", delta_color="inverse")
            c3.metric("GIDA ENFLASYONU", f"%{gida_enf:.2f}", delta_color="inverse")
            c4.metric("ZİRVEDEKİ", f"{top['Madde adı'][:15]}", f"%{top['Fark'] * 100:.1f}", delta_color="inverse")
            st.markdown("<br>", unsafe_allow_html=True)

            # SEKMELER
            t1, t2, t3, t4, t5, t6, t7 = st.tabs(
                ["🤖 ASİSTAN", "🫧 PİYASA BALONCUKLARI", "🍏 GIDA DETAY", "🚀 ZİRVE", "📉 FIRSATLAR", "📑 TAM LİSTE",
                 "🎲 SİMÜLASYON"])

            with t1:  # 🤖 ASİSTAN SORGULAMA (YENİ)
                st.markdown("##### 🤖 Merhaba, neyi merak ediyorsun?")
                sorgu = st.text_input("", placeholder="Örn: Süt, Ekmek, Gıda, Alkol...", key="asistan_input")

                if sorgu:
                    # Arama İşlemi
                    sorgu = sorgu.lower()
                    sonuc_urun = df_analiz[df_analiz['Madde adı'].str.lower().str.contains(sorgu, na=False)]
                    sonuc_grup = df_analiz[df_analiz['Grup'].str.lower().str.contains(sorgu, na=False)]

                    if not sonuc_urun.empty:
                        # Ürün Bulunduysa En İlgiliyi Al
                        row = sonuc_urun.iloc[0]
                        fark = row['Fark'] * 100

                        emoji = "📈" if fark > 0 else "🎉" if fark < 0 else "😐"
                        stil = "bot-bad" if fark > 0 else "bot-good" if fark < 0 else "bot-msg"
                        yorum = "maalesef zamlandı." if fark > 0 else "indirimde!" if fark < 0 else "fiyatını koruyor."

                        st.markdown(f"""
                        <div class="{stil}">
                            <h3>{emoji} {row['Madde adı']} Analizi</h3>
                            <p>Sistemi taradım. Bu ürün <b>{baz}</b> tarihinde <b>{row[baz]:.2f} TL</b> iken, bugün <b>{row[son]:.2f} TL</b> olmuş.</p>
                            <p>Genel değişim: <b>%{fark:.2f}</b> oranında {yorum}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Grafik
                        kod = row['Kod']
                        hist = df_f[df_f['Kod'] == kod].sort_values('Tam_Zaman')
                        fig_l = px.line(hist, x='Tam_Zaman', y='Fiyat', markers=True,
                                        title=f"{row['Madde adı']} Fiyat Grafiği")
                        fig_l.update_traces(line_color='#3b82f6', line_width=4)
                        fig_l.update_layout(plot_bgcolor='white', xaxis_title="", yaxis_title="Fiyat (TL)")
                        st.plotly_chart(fig_l, use_container_width=True)

                        if len(sonuc_urun) > 1:
                            st.info(
                                f"💡 Ayrıca şunları da buldum: {', '.join(sonuc_urun['Madde adı'].tolist()[1:5])}...")

                    elif not sonuc_grup.empty:
                        # Kategori Bulunduysa
                        grp_name = sonuc_grup.iloc[0]['Grup']
                        grp_data = df_analiz[df_analiz['Grup'] == grp_name]
                        grp_enf = ((grp_data[son] / grp_data[baz] * grp_data['Agirlik_2025']).sum() / grp_data[
                            'Agirlik_2025'].sum() - 1) * 100

                        st.markdown(f"""
                        <div class="bot-msg">
                            <h3>📂 {grp_name} Kategorisi Raporu</h3>
                            <p>Bu kategorideki genel enflasyon oranı: <b>%{grp_enf:.2f}</b></p>
                            <p>Kategoride toplam <b>{len(grp_data)}</b> ürün takip ediliyor.</p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.dataframe(grp_data[['Madde adı', 'Fark', son]].sort_values('Fark', ascending=False),
                                     use_container_width=True)

                    else:
                        st.warning(
                            "😕 Üzgünüm, veri tabanında böyle bir ürün veya kategori bulamadım. Lütfen başka bir kelime dene.")

                else:
                    st.info("👆 Yukarıya bir ürün adı yaz, senin için analiz edeyim.")

            with t2:  # BUBBLE CHART
                st.markdown("##### 🫧 Piyasa Fiyat Dağılımı")
                df_analiz['Yuzde_Degisim'] = df_analiz['Fark'] * 100
                fig_bub = px.scatter(
                    df_analiz, x="Grup", y="Yuzde_Degisim",
                    size="Agirlik_2025", color="Yuzde_Degisim",
                    hover_name="Madde adı", color_continuous_scale="RdYlGn_r", size_max=60
                )
                fig_bub.update_layout(plot_bgcolor='white', yaxis_title="Değişim (%)", xaxis_title="")
                st.plotly_chart(fig_bub, use_container_width=True)

            with t3:  # GIDA DETAY
                if not gida.empty:
                    df_g = gida[['Madde adı', 'Fark', baz, son]].sort_values('Fark', ascending=False)
                    df_g = df_g.rename(columns={baz: str(baz), son: str(son)})
                    st.dataframe(df_g, column_config={
                        "Fark": st.column_config.ProgressColumn("Trend", format="%.2f%%", min_value=-0.5,
                                                                max_value=0.5),
                        str(baz): st.column_config.NumberColumn(format="%.2f ₺"),
                        str(son): st.column_config.NumberColumn(format="%.2f ₺")}, use_container_width=True)
                else:
                    st.warning("Gıda verisi yok.")

            with t4:  # ZİRVE
                st.table(df_analiz.sort_values('Fark', ascending=False).head(10)[['Madde adı', 'Grup', 'Fark']].assign(
                    Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))

            with t5:  # FIRSATLAR
                low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark')
                if not low.empty:
                    st.table(low[['Madde adı', 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                else:
                    st.info("Şu an indirimde ürün yok.")

            with t6:  # TAM LİSTE
                out = BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as w: df_analiz.to_excel(w, index=False)
                st.download_button("📥 Excel İndir", out.getvalue(), f"Enflasyon_{son}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)

                df_sh = df_analiz[['Grup', 'Madde adı', 'Fark', baz, son]].rename(
                    columns={baz: str(baz), son: str(son)})
                st.dataframe(df_sh, column_config={"Fark": st.column_config.LineChartColumn("Trend"),
                                                   str(baz): st.column_config.NumberColumn(format="%.2f ₺"),
                                                   str(son): st.column_config.NumberColumn(format="%.2f ₺")},
                             use_container_width=True)

            with t7:  # SİMÜLASYON
                cols = st.columns(4)
                inps = {g: cols[i % 4].number_input(f"{g} (%)", -50.0, 100.0, 0.0) for i, g in
                        enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in inps.items()])
                st.success(f"Yeni Tahmin: %{(genel_enf + etki):.2f} (Etki: {etki:+.2f} puan)")

    else:
        st.warning("Veri bekleniyor...")

    st.markdown("---")
    st.markdown('<div class="action-btn">', unsafe_allow_html=True)
    if st.button("GIDAMI HESAPLA", type="primary", use_container_width=True):
        ph = st.empty();
        bar = st.progress(0)
        res = migros_gida_botu(lambda m: ph.info(m))
        bar.progress(100);
        ph.empty()
        if "OK" in res:
            st.success("✅ Güncellendi!"); time.sleep(1); st.rerun()
        else:
            st.error(res)
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()