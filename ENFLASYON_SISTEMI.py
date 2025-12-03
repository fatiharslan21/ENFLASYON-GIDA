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
            background-color: #f8fafc; /* Slate-50 */
            font-family: 'Inter', sans-serif;
            color: #1e293b;
        }

        /* GİZLİ ELEMENTLER */
        [data-testid="stSidebar"], [data-testid="stToolbar"], .stDeployButton, footer, #MainMenu {display: none !important;}

        /* ✨ HEADER & LIVE INDICATOR */
        .header-container {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 30px;
        }
        .app-title {
            font-size: 32px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px;
        }
        .live-indicator {
            display: flex; align-items: center; font-size: 13px; font-weight: 600; color: #15803d;
            background: #ffffff; padding: 6px 12px; border-radius: 20px; border: 1px solid #bbf7d0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .pulse {
            width: 8px; height: 8px; background-color: #22c55e; border-radius: 50%; margin-right: 8px;
            box-shadow: 0 0 0 rgba(34, 197, 94, 0.4); animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }

        /* 📈 MODERN TICKER */
        .ticker-wrap {
            width: 100%; overflow: hidden; background: #ffffff;
            border-bottom: 1px solid #cbd5e1;
            white-space: nowrap; padding: 10px 0; margin-bottom: 25px;
        }
        .ticker { display: inline-block; animation: ticker 50s linear infinite; }
        .ticker-item { 
            display: inline-block; padding: 0 2rem; font-family: 'Inter', sans-serif;
            font-weight: 600; font-size: 14px; color: #475569;
        }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* 💎 CUSTOM METRIC CARDS */
        .metric-card {
            background: #ffffff; border-radius: 12px; padding: 24px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0; transition: all 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #94a3b8;
        }
        .metric-label { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
        .metric-value { font-size: 28px; font-weight: 800; color: #0f172a; margin: 8px 0; letter-spacing: -0.5px; }
        .metric-delta { font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 6px; display: inline-block; }
        .delta-pos { background: #fee2e2; color: #ef4444; } 
        .delta-neg { background: #dcfce7; color: #16a34a; } 
        .delta-neu { background: #f1f5f9; color: #475569; }

        /* 🤖 ASİSTAN PRO UI */
        .chat-container {
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 25px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px;
        }

        /* 🚀 ACTION BUTTON */
        .action-container { margin-top: 40px; text-align: center; }
        .action-btn button {
            background: #0f172a !important; color: white !important; height: 60px; font-size: 18px !important; font-weight: 600 !important;
            border-radius: 8px !important; width: 100%; border: none !important; transition: all 0.2s ease;
        }
        .action-btn button:hover { background: #334155 !important; transform: translateY(-1px); }

        /* TABS */
        .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 2px solid #e2e8f0; }
        .stTabs [data-baseweb="tab"] { background: transparent; border: none; color: #64748b; font-weight: 600; padding-bottom: 10px; }
        .stTabs [aria-selected="true"] { color: #0f172a; border-bottom: 2px solid #0f172a; }

        /* IMZA */
        .signature-footer {
            text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #e2e8f0;
            color: #94a3b8; font-size: 14px; font-weight: 500; font-family: 'Inter', sans-serif;
        }
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

            # UI: HEADER
            st.markdown(f"""
                <div class="header-container">
                    <div class="app-title">Enflasyon Monitörü <span style="font-weight:300; color:#64748b;">v4.0</span></div>
                    <div class="live-indicator"><div class="pulse"></div>SİSTEM AKTİF • {son.strftime('%d.%m.%Y')}</div>
                </div>
            """, unsafe_allow_html=True)

            # TICKER
            items = []
            for _, r in df_analiz.sort_values('Fark', ascending=False).head(15).iterrows():
                color = "#dc2626" if r['Fark'] > 0 else "#16a34a"
                icon = "▲" if r['Fark'] > 0 else "▼"
                items.append(f"<span style='color:{color}'>{r['Madde adı']} {icon} %{r['Fark'] * 100:.1f}</span>")
            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp;•&nbsp;&nbsp; ".join(items)}</div></div></div>',
                unsafe_allow_html=True)

            # KARTLAR
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

            display_card(c1, "Genel Endeks", f"{df_trend['TÜFE'].iloc[-1]:.2f}", "Baz: 100", "neu")
            display_card(c2, "Genel Enflasyon", f"%{genel_enf:.2f}", "Kümülatif", "pos")
            display_card(c3, "Gıda Enflasyonu", f"%{gida_enf:.2f}", "Mutfak", "pos")
            display_card(c4, "En Yüksek Risk", f"{top['Madde adı'][:12]}..", f"%{top['Fark'] * 100:.1f} Artış", "pos")

            st.markdown("<br>", unsafe_allow_html=True)

            # 📈 ANA GRAFİK (PRO VERSİYON - GRADIENT)
            fig_area = go.Figure()
            fig_area.add_trace(go.Scatter(
                x=df_trend['Tarih'], y=df_trend['TÜFE'],
                mode='lines',
                name='TÜFE',
                line=dict(color='#2563eb', width=3),
                fill='tozeroy',
                fillcolor='rgba(37, 99, 235, 0.1)'  # Gradient Efekti
            ))
            fig_area.update_layout(
                title=dict(text="📈 Enflasyon Trend Analizi", font=dict(size=18, color='#0f172a')),
                plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(t=50, b=0, l=0, r=0),
                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', rangeslider=dict(visible=True)),
                yaxis=dict(showgrid=True, gridcolor='#f1f5f9'),
                hovermode="x unified"
            )
            st.plotly_chart(fig_area, use_container_width=True)

            # SEKMELER
            tabs = st.tabs(
                ["🤖 AKILLI ASİSTAN", "🫧 BALONCUKLAR", "🍏 GIDA", "🚀 ZİRVE", "📉 FIRSATLAR", "📑 LİSTE", "🎲 SİMÜLE"])

            with tabs[0]:  # ASİSTAN (GELİŞMİŞ RENK & SEÇİM)
                st.markdown('<div class="chat-container">', unsafe_allow_html=True)
                st.markdown("##### 🤖 Piyasa Analiz Asistanı")
                sorgu_ham = st.text_input("", placeholder="Merak ettiğin ürünü veya kategoriyi yaz (Örn: Süt, Yağ)...",
                                          label_visibility="collapsed")

                if sorgu_ham:
                    sorgu = sorgu_ham.lower()
                    sonuc_urun = df_analiz[df_analiz['Madde adı'].str.lower().str.contains(sorgu, na=False)]
                    target = None

                    if not sonuc_urun.empty:
                        # 1. ÇOKLU SEÇİM KONTROLÜ
                        if len(sonuc_urun) > 1:
                            st.info(f"🤔 '{sorgu_ham}' için birden fazla sonuç buldum. Hangisi?")
                            secim = st.selectbox("Lütfen Seçin:", sonuc_urun['Madde adı'].unique(),
                                                 label_visibility="collapsed")
                            target = df_analiz[df_analiz['Madde adı'] == secim].iloc[0]
                        else:
                            target = sonuc_urun.iloc[0]

                        # 2. ANALİZ VE RENKLENDİRME
                        if target is not None:
                            fark = target['Fark'] * 100

                            # RENK MANTIĞI: ARTIŞ KIRMIZI, AZALIŞ YEŞİL
                            if fark > 0:
                                durum_icon = "📈"
                                durum_text = "ZAMLANDI"
                                color_style = "#dc2626"  # Kırmızı
                                bg_style = "#fef2f2"
                                msg_extra = "Bu ürünün fiyatı artış eğiliminde."
                            elif fark < 0:
                                durum_icon = "🎉"
                                durum_text = "İNDİRİMDE"
                                color_style = "#16a34a"  # Yeşil
                                bg_style = "#f0fdf4"
                                msg_extra = "Fiyat düşüşü yakaladınız."
                            else:
                                durum_icon = "➖"
                                durum_text = "SABİT"
                                color_style = "#475569"
                                bg_style = "#f8fafc"
                                msg_extra = "Fiyat değişmedi."

                            # HTML MESAJ
                            html_msg = f"""
                                <div style="background-color:{bg_style}; border-left: 5px solid {color_style}; padding: 20px; border-radius: 8px; color: #1e293b;">
                                    <div style="font-size:20px; font-weight:800; color:{color_style}; margin-bottom:10px;">
                                        {durum_icon} {durum_text} (%{fark:.2f})
                                    </div>
                                    <div style="font-size:16px; line-height:1.5;">
                                        <b>{target['Madde adı']}</b><br>
                                        Başlangıç: <b>{target[baz]:.2f} TL</b> <span style="color:#cbd5e1">➜</span> Son: <b>{target[son]:.2f} TL</b>
                                        <br><br>
                                        <span style="font-size:14px; color:#64748b;">ℹ️ {msg_extra}</span>
                                    </div>
                                </div>
                            """
                            st.markdown(html_msg, unsafe_allow_html=True)

                            # MİNİ GRAFİK
                            hist = df_f[df_f['Kod'] == target['Kod']].sort_values('Tam_Zaman')
                            fig_mini = px.line(hist, x='Tam_Zaman', y='Fiyat', markers=True)
                            fig_mini.update_traces(line_color='#2563eb', line_width=3)
                            fig_mini.update_layout(height=250, margin=dict(t=20, b=0, l=0, r=0),
                                                   plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None,
                                                   yaxis_title="Fiyat (TL)")
                            st.plotly_chart(fig_mini, use_container_width=True)
                    else:
                        st.warning(f"😕 '{sorgu_ham}' ile ilgili bir kayıt bulunamadı.")
                st.markdown('</div>', unsafe_allow_html=True)

            with tabs[1]:  # BUBBLE
                st.markdown("##### 🫧 Sektörel Dağılım")
                fig_bub = px.scatter(df_analiz, x="Grup", y="Fark", size="Agirlik_2025", color="Fark",
                                     hover_name="Madde adı", color_continuous_scale="RdYlGn_r", size_max=60)
                fig_bub.update_layout(plot_bgcolor='white', yaxis_title="Değişim Oranı", height=500)
                st.plotly_chart(fig_bub, use_container_width=True)

            with tabs[2]:  # GIDA
                if not gida.empty:
                    df_g = gida[['Madde adı', 'Fark', baz, son]].sort_values('Fark', ascending=False)
                    st.dataframe(df_g, column_config={
                        "Fark": st.column_config.ProgressColumn("Trend", format="%.2f%%", min_value=-0.5,
                                                                max_value=0.5)}, use_container_width=True)
                else:
                    st.warning("Veri yok")

            with tabs[3]:  # ZİRVE
                st.table(df_analiz.sort_values('Fark', ascending=False).head(10)[['Madde adı', 'Grup', 'Fark']].assign(
                    Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))

            with tabs[4]:  # FIRSAT
                low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark')
                if not low.empty:
                    st.table(low[['Madde adı', 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                else:
                    st.info("İndirim yok.")

            with tabs[5]:  # LİSTE
                out = BytesIO();
                with pd.ExcelWriter(out, engine='openpyxl') as w: df_analiz.to_excel(w, index=False)
                st.download_button("📥 Excel İndir", out.getvalue(), f"Report_{son}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
                st.dataframe(df_analiz[['Grup', 'Madde adı', 'Fark', baz, son]],
                             column_config={"Fark": st.column_config.LineChartColumn("Trend")},
                             use_container_width=True)

            with tabs[6]:  # SIM
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
    if st.button("Gıdamı Hesapla!", type="primary", use_container_width=True):
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

    # İMZA (PRO FOOTER)
    st.markdown(
        '<div class="signature-footer">Designed by Fatih Arslan © 2025<br>Advanced Inflation Analytics System</div>',
        unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()