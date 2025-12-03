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

# --- 1. SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="ENFLASYON MONITORU PRO", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

# --- 🎨 ULTRA PREMIUM UI CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400&display=swap');

        /* GENEL ATMOSFER */
        .stApp {
            background-color: #f8fafc; /* Ultra Clean White/Slate */
            font-family: 'Inter', sans-serif;
            color: #1e293b;
        }

        /* GİZLİ ELEMENTLER */
        [data-testid="stSidebar"], [data-testid="stToolbar"], .stDeployButton, footer, #MainMenu {display: none !important;}

        /* ✨ HEADER & LIVE INDICATOR */
        .header-container {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 0; border-bottom: 2px solid #e2e8f0; margin-bottom: 30px;
        }
        .app-title {
            font-size: 36px; font-weight: 900; background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px;
        }
        .live-indicator {
            display: flex; align-items: center; font-size: 14px; font-weight: 600; color: #15803d;
            background: #dcfce7; padding: 8px 16px; border-radius: 20px; border: 1px solid #bbf7d0;
        }
        .pulse {
            width: 10px; height: 10px; background-color: #22c55e; border-radius: 50%; margin-right: 10px;
            box-shadow: 0 0 0 rgba(34, 197, 94, 0.4); animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }

        /* 📈 MODERN TICKER */
        .ticker-wrap {
            width: 100%; overflow: hidden; background: #ffffff;
            border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;
            white-space: nowrap; padding: 12px 0; margin-bottom: 20px;
        }
        .ticker { display: inline-block; animation: ticker 50s linear infinite; }
        .ticker-item { 
            display: inline-block; padding: 0 2rem; font-family: 'JetBrains Mono', monospace;
            font-weight: 600; font-size: 13px; color: #475569;
        }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* 💎 CUSTOM METRIC CARDS */
        .metric-card {
            background: #ffffff; border-radius: 16px; padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            border: 1px solid #f1f5f9; transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative; overflow: hidden;
        }
        .metric-card:hover {
            transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            border-color: #3b82f6;
        }
        .metric-label { font-size: 14px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
        .metric-value { font-size: 32px; font-weight: 800; color: #0f172a; margin: 10px 0; letter-spacing: -1px; }
        .metric-delta { font-size: 14px; font-weight: 600; padding: 4px 10px; border-radius: 8px; display: inline-block; }
        .delta-pos { background: #fee2e2; color: #991b1b; } /* Kırmızı (Kötü) */
        .delta-neg { background: #dcfce7; color: #166534; } /* Yeşil (İyi) */
        .delta-neu { background: #f1f5f9; color: #475569; }

        /* 🤖 ASİSTAN CHAT UI */
        .chat-container {
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); margin-bottom: 25px;
        }
        .bot-bubble {
            background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 20px; border-radius: 0 12px 12px 12px;
            margin-top: 15px; color: #0c4a6e; font-size: 16px; line-height: 1.6;
        }

        /* 🚀 ACTION BUTTON */
        .action-container { margin-top: 40px; text-align: center; }
        .action-btn button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: white !important; height: 70px; font-size: 20px !important; font-weight: 700 !important;
            border-radius: 50px !important; box-shadow: 0 20px 25px -5px rgba(37, 99, 235, 0.4) !important;
            width: 100%; border: none !important; transition: all 0.3s ease;
        }
        .action-btn button:hover { transform: scale(1.02); box-shadow: 0 25px 30px -5px rgba(37, 99, 235, 0.5) !important; }

        /* TABS */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; background: #f1f5f9; padding: 5px; border-radius: 12px; }
        .stTabs [data-baseweb="tab"] { background: transparent; border: none; border-radius: 8px; color: #64748b; font-weight: 600; }
        .stTabs [aria-selected="true"] { background: #ffffff; color: #2563eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
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
            # Akıllı Kayıt: Aynı gün verisini duplicate yapma, güncelle
            old = old[~((old['Tarih'].astype(str) == str(yeni_tarih)) & (old['Kod'].isin(df_yeni['Kod'])))]
            final = pd.concat([old, df_yeni], ignore_index=True)
        except:
            c = None; final = df_yeni

        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            final.to_excel(w, index=False, sheet_name='Fiyat_Log')

        if c:
            repo.update_file(c.path, "Auto-Update", out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, "Auto-Create", out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# --- 3. HELPER & BOT MOTORU ---
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


def migros_gida_botu(cb=None):
    if cb: cb("🚀 Bağlantı Kuruluyor...")
    install_browsers()
    try:
        df = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        if df.empty: return "Liste Boş"
        df['Kod'] = df['Kod'].astype(str).apply(kod_standartlastir)
        takip = df[(df['Kod'].str.startswith('01')) & (df['URL'].str.contains('migros', case=False))].copy()
    except:
        return "Veri Hatası"

    veriler = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        for _, row in takip.iterrows():
            url = row['URL']
            if cb: cb(f"📡 Taranıyor: {row.get('Madde adı')[:20]}")
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
                        if page.locator(sel).count(): fiyat = temizle_fiyat(page.locator(sel).first.inner_text()); break
            except:
                pass
            if fiyat > 0:
                veriler.append({"Tarih": datetime.now().strftime("%Y-%m-%d"), "Zaman": datetime.now().strftime("%H:%M"),
                                "Kod": row['Kod'], "Madde_Adi": row['Madde adı'], "Fiyat": fiyat,
                                "Kaynak": "Sanal Market", "URL": url})
        browser.close()

    if veriler:
        if cb: cb("💾 Buluta Kaydediliyor...")
        return github_excel_guncelle(pd.DataFrame(veriler), FIYAT_DOSYASI)
    return "Veri Yok"


# --- 4. DASHBOARD MODU ---
def dashboard_modu():
    # Veri Hazırlığı
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

            # UI BAŞLIYOR: HEADER
            st.markdown(f"""
                <div class="header-container">
                    <div class="app-title">ENFLASYON MONİTÖRÜ <span style="font-weight:300; font-size:24px; color:#64748b;">PRO</span></div>
                    <div class="live-indicator"><div class="pulse"></div>SİSTEM AKTİF • {son.strftime('%d.%m.%Y')}</div>
                </div>
            """, unsafe_allow_html=True)

            # TICKER
            items = []
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(15).iterrows():
                color = "#ef4444" if r['Fark'] > 0 else "#22c55e"
                icon = "▲" if r['Fark'] > 0 else "▼"
                items.append(f"<span style='color:{color}'>{r['Madde adı']} {icon} %{r['Fark'] * 100:.1f}</span>")
            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp;•&nbsp;&nbsp; ".join(items)}</div></div></div>',
                unsafe_allow_html=True)

            # METRİKLER (CUSTOM HTML KARTLAR)
            c1, c2, c3, c4 = st.columns(4)

            def display_card(col, title, value, sub, delta_type="neu"):
                cls = "delta-pos" if delta_type == "pos" else "delta-neg" if delta_type == "neg" else "delta-neu"
                col.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{title}</div>
                        <div class="metric-value">{value}</div>
                        <div class="metric-delta {cls}">{sub}</div>
                    </div>
                """, unsafe_allow_html=True)

            display_card(c1, "Genel Endeks", f"{df_trend['TÜFE'].iloc[-1]:.2f}", "Baz: 100 Puan", "neu")
            display_card(c2, "Genel Enflasyon", f"%{genel_enf:.2f}", "Kümülatif Artış", "pos")
            display_card(c3, "Gıda Enflasyonu", f"%{gida_enf:.2f}", "Mutfak Harcaması", "pos")
            display_card(c4, "Risk Lideri", f"{top['Madde adı'][:12]}..", f"%{top['Fark'] * 100:.1f} Artış", "pos")

            st.markdown("<br>", unsafe_allow_html=True)

            # 📈 ANA GRAFİK
            fig_area = px.area(df_trend, x='Tarih', y='TÜFE', color_discrete_sequence=['#3b82f6'])
            fig_area.update_layout(
                title="📈 Enflasyon Trend Analizi",
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=40, b=0, l=0, r=0),
                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', rangeslider=dict(visible=True)),
                yaxis=dict(showgrid=True, gridcolor='#f1f5f9'),
                hovermode="x unified"  # Crosshair Efekti
            )
            fig_area.update_traces(line_shape='spline', fillcolor="rgba(59, 130, 246, 0.1)")
            st.plotly_chart(fig_area, use_container_width=True)

            # SEKMELER (GELİŞMİŞ)
            tabs = st.tabs(
                ["🤖 ASİSTAN", "🕸️ RADAR ANALİZİ", "🫧 BALONCUKLAR", "🍏 GIDA", "🚀 ZİRVE", "📉 FIRSATLAR", "📑 LİSTE",
                 "🎲 SİMÜLE"])

            with tabs[0]:  # AKILLI ASİSTAN
                st.markdown('<div class="chat-container">', unsafe_allow_html=True)
                st.markdown("##### 🤖 Finans Asistanı")
                sorgu_ham = st.text_input("",
                                          placeholder="Merak ettiğin ürünü veya kategoriyi yaz (Örn: Süt, Gıda, Ekmek)...",
                                          label_visibility="collapsed")

                if sorgu_ham:
                    sorgu = sorgu_ham.lower()
                    sonuc_urun = df_analiz[df_analiz['Madde adı'].str.lower().str.contains(sorgu, na=False)]
                    sonuc_grup = df_analiz[df_analiz['Grup'].str.lower().str.contains(sorgu, na=False)]

                    target = None
                    if not sonuc_urun.empty:
                        if len(sonuc_urun) > 1:
                            st.info(f"🤔 '{sorgu_ham}' ile eşleşen birden fazla ürün var. Lütfen seçin:")
                            secim = st.selectbox("", sonuc_urun['Madde adı'].unique())
                            target = df_analiz[df_analiz['Madde adı'] == secim].iloc[0]
                        else:
                            target = sonuc_urun.iloc[0]

                        if target is not None:
                            fark = target['Fark'] * 100
                            durum = "📈 ZAMLANDI" if fark > 0 else "🎉 İNDİRİMDE" if fark < 0 else "➖ STABİL"
                            msg = f"""
                                <b>{durum}: {target['Madde adı']}</b><br>
                                Bu ürün döneme <b>{target[baz]:.2f} TL</b> ile başladı, şu an <b>{target[son]:.2f} TL</b>.<br>
                                Toplam değişim: <b>%{fark:.2f}</b>.
                            """
                            st.markdown(f'<div class="bot-bubble">{msg}</div>', unsafe_allow_html=True)

                            # Mini Grafik
                            hist = df_f[df_f['Kod'] == target['Kod']].sort_values('Tam_Zaman')
                            fig_mini = px.line(hist, x='Tam_Zaman', y='Fiyat', markers=True)
                            fig_mini.update_traces(line_color='#0ea5e9')
                            fig_mini.update_layout(height=250, margin=dict(t=10, b=0, l=0, r=0),
                                                   plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_mini, use_container_width=True)

                    elif not sonuc_grup.empty:
                        grp = sonuc_grup.iloc[0]['Grup']
                        g_data = df_analiz[df_analiz['Grup'] == grp]
                        g_enf = ((g_data[son] / g_data[baz] * g_data['Agirlik_2025']).sum() / g_data[
                            'Agirlik_2025'].sum() - 1) * 100
                        st.markdown(
                            f'<div class="bot-bubble">📂 <b>{grp} Kategorisi:</b><br>Kategori genel enflasyonu <b>%{g_enf:.2f}</b> seviyesinde. Toplam {len(g_data)} ürün takip ediliyor.</div>',
                            unsafe_allow_html=True)
                        st.dataframe(g_data[['Madde adı', 'Fark', son]].sort_values('Fark', ascending=False),
                                     use_container_width=True)
                    else:
                        st.warning("Veri bulunamadı. Başka bir kelime dene.")
                st.markdown('</div>', unsafe_allow_html=True)

            with tabs[1]:  # RADAR CHART (YENİ ŞOV)
                st.markdown("##### 🕸️ Sektörel Enflasyon Radarı")
                df_radar = df_analiz.copy()
                df_radar['Etki'] = (df_radar[son] / df_radar[baz]) - 1
                radar_data = df_radar.groupby('Grup')['Etki'].mean().reset_index()

                fig_rad = px.line_polar(radar_data, r='Etki', theta='Grup', line_close=True,
                                        range_r=[0, radar_data['Etki'].max() * 1.2])
                fig_rad.update_traces(fill='toself', line_color='#3b82f6')
                fig_rad.update_layout(height=500)
                st.plotly_chart(fig_rad, use_container_width=True)

            with tabs[2]:  # BUBBLE
                st.markdown("##### 🫧 Piyasa Dağılımı")
                fig_bub = px.scatter(df_analiz, x="Grup", y="Fark", size="Agirlik_2025", color="Fark",
                                     hover_name="Madde adı", color_continuous_scale="RdYlGn_r", size_max=60)
                fig_bub.update_layout(plot_bgcolor='white', yaxis_title="Değişim Oranı")
                st.plotly_chart(fig_bub, use_container_width=True)

            with tabs[3]:  # GIDA
                if not gida.empty:
                    df_g = gida[['Madde adı', 'Fark', baz, son]].sort_values('Fark', ascending=False)
                    st.dataframe(df_g, column_config={
                        "Fark": st.column_config.ProgressColumn("Trend", format="%.2f%%", min_value=-0.5,
                                                                max_value=0.5)}, use_container_width=True)
                else:
                    st.warning("Veri yok")

            with tabs[4]:  # ZİRVE
                st.table(df_analiz.sort_values('Fark', ascending=False).head(10)[['Madde adı', 'Grup', 'Fark']].assign(
                    Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))

            with tabs[5]:  # FIRSAT
                low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark')
                if not low.empty:
                    st.table(low[['Madde adı', 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                else:
                    st.info("İndirim yok.")

            with tabs[6]:  # LİSTE
                out = BytesIO();
                with pd.ExcelWriter(out, engine='openpyxl') as w: df_analiz.to_excel(w, index=False)
                st.download_button("📥 Excel İndir", out.getvalue(), f"Report_{son}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
                st.dataframe(df_analiz[['Grup', 'Madde adı', 'Fark', baz, son]],
                             column_config={"Fark": st.column_config.LineChartColumn("Trend")},
                             use_container_width=True)

            with tabs[7]:  # SIM
                c = st.columns(4)
                inps = {g: c[i % 4].number_input(f"{g} (%)", -50., 100., 0.) for i, g in
                        enumerate(sorted(df_analiz['Grup'].unique()))}
                etki = sum(
                    [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v for
                     g, v in inps.items()])
                st.success(f"Yeni Enflasyon Tahmini: %{(genel_enf + etki):.2f}")

    else:
        st.warning("Sistem verisi bekleniyor...")

    # ACTION BUTTON
    st.markdown('<div class="action-container"><div class="action-btn">', unsafe_allow_html=True)
    if st.button("SİSTEMİ GÜNCELLE (GIDAMI HESAPLA)", type="primary", use_container_width=True):
        ph = st.empty();
        bar = st.progress(0)
        res = migros_gida_botu(lambda m: ph.info(m))
        bar.progress(100);
        ph.empty()
        if "OK" in res:
            st.success("✅ Veritabanı Güncellendi!"); time.sleep(1); st.rerun()
        else:
            st.error(res)
    st.markdown('</div></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()