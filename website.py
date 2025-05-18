from flask import Flask, render_template, request, session, redirect, url_for
import pandas as pd
import numpy as np
import os
from sklearn.neighbors import NearestNeighbors


app = Flask(__name__)
app.secret_key = 'your_secret_key_here' 


# 2. Fungsi Kategori Hipertensi
def get_kategori_natrium(tekanan_darah):
    if isinstance(tekanan_darah, str):
        try:
            sistolik, diastolik = map(int, tekanan_darah.split('/'))
        except:
            raise ValueError("Format tekanan darah harus seperti '180/110'")
    elif isinstance(tekanan_darah, (tuple, list)) and len(tekanan_darah) == 2:
        sistolik, diastolik = tekanan_darah
    else:
        raise ValueError("Tekanan darah harus dalam format '180/110' atau tuple (sistolik, diastolik)")
    
    def konversi_ke_sendok_teh(rentang):
        return round(rentang[0]/ 2000, 2), round(rentang[1] / 2000, 2)
    
    if 140 <= sistolik <= 159 or 90 <= diastolik <= 99:
        batas_natrium = (1000, 1200)
        batas_sdt = konversi_ke_sendok_teh(batas_natrium)
        return "Hipertensi Derajat 1", batas_natrium, batas_sdt
    elif 160 <= sistolik <= 179 or 100 <= diastolik <= 109:
        batas_natrium = (600, 800)
        batas_sdt = konversi_ke_sendok_teh(batas_natrium)
        return "Hipertensi Derajat 2", batas_natrium, batas_sdt
    elif sistolik >= 180 or diastolik >= 110:
        batas_natrium = (200, 400)
        batas_sdt = konversi_ke_sendok_teh(batas_natrium)
        return "Hipertensi Derajat 3", batas_natrium, batas_sdt
    else:
        raise ValueError("Tekanan darah tidak sesuai dengan kategori hipertensi.")
    
def penjelasan_sdt_praktis(min_sdt, max_sdt):
    rata_rata = (min_sdt + max_sdt) / 2
    if rata_rata <= 0.2:
        return "setara 1/10 sendok teh garam (seujung sendok teh)"
    elif rata_rata <= 0.45:
        return "setara 1/3 sendok teh garam"
    elif rata_rata <= 0.6:
        return "setara 1/2 sendok teh garam"
    else:
        return "perkiraan sesuai kebutuhan harian"


def rekomendasi_menu(tekanan_darah, preferensi= None, max_k=50, min_hasil=1):

    kategori, (min_natrium, max_natrium) , (min_sdt, max_sdt) = get_kategori_natrium(tekanan_darah)
    takaran_praktis = penjelasan_sdt_praktis(min_sdt, max_sdt)
    target_natrium = (min_natrium + max_natrium) / 2

    df_menu = pd.read_csv('kombinasi_menu.csv')
    X = df_menu[['Total_natrium']].values.reshape(-1, 1)


    for k in range(1, max_k + 1):
        model = NearestNeighbors(n_neighbors = k, metric='euclidean').fit(X)
        _, indices = model.kneighbors([[target_natrium]])
        hasil = df_menu.iloc[indices[0]]

    if preferensi:
        hasil = hasil[
            hasil.apply(
                lambda row: any(pref.lower() in row.to_string().lower() for pref in preferensi), axis=1
            )
        ]
        
        if len(hasil) >= min_hasil:
            hasil['Selisih'] = abs(hasil['Total_natrium'] - target_natrium)
            hasil = (
                hasil
                .sort_values('Selisih')
                .drop(columns='Selisih')
                .assign(Total_natrium=lambda df: df['Total_natrium'].round(2))
                .reset_index(drop=True)
            )
            return hasil

    return pd.DataFrame(columns=df_menu.columns)

       


@app.route('/')
def halaman_awal():
    session.pop('hasil_rekomendasi', None)  # Hapus hasil rekomendasi dari session
    return render_template('halaman_awal.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/rekomendasi')
def rekomendasi():
    return render_template('rekomendasi.html')

@app.route('/hasil_rekomendasi', methods=['GET', 'POST'])
def hasil_rekomendasi():
    if request.method == 'POST':
        tekanan_darah = request.form.get('tekanan_darah')
        nama_makanan  = request.form.get('makanan', '')
        prefs = [x.strip().lower() for x in nama_makanan.split(',')] if nama_makanan else []

        try:
            # Hitung kategori & batas
            kategori, (min_n, max_n), (min_sdt, max_sdt) = get_kategori_natrium(tekanan_darah)
            takaran_praktis = penjelasan_sdt_praktis(min_sdt, max_sdt)

            # Dapatkan DataFrame rekomendasi
            hasil_df = rekomendasi_menu(tekanan_darah, prefs)
            records = hasil_df.to_dict(orient='records')

            # Simpan ke session supaya tersedia di GET
            session['hasil_rekomendasi'] = records
            session['kategori']         = kategori
            session['batas_natrium']    = (min_n, max_n)
            session['batas_sdt']        = (min_sdt, max_sdt)
            session['takaran_praktis']  = takaran_praktis
            session['tekanan_darah']    = tekanan_darah

            error = None
            if not records:
                error = "Tidak ada menu yang cocok dengan preferensi Anda."

            # Render langsung hasil pertama kali
            return render_template('hasil_rekomendasi.html',
                                   hasil=records,
                                   error=error,
                                   show_result=True,
                                   kategori=kategori,
                                   batas_natrium=f"{min_n} - {max_n} mg",
                                   batas_sdt=(min_sdt, max_sdt),
                                   takaran_praktis=takaran_praktis,
                                   tekanan_darah=tekanan_darah)

        except Exception as e:
            print(f"Terjadi kesalahan: {e}")
            # Ikut simpan dummy ke session agar GET tidak error
            session['hasil_rekomendasi'] = []
            session['batas_sdt'] = (0, 0)
            return render_template('hasil_rekomendasi.html',
                                   hasil=[],
                                   error="Terjadi kesalahan sistem",
                                   show_result=True,
                                   kategori=None,
                                   batas_natrium=None,
                                   batas_sdt=(0, 0),
                                   takaran_praktis=None,
                                   tekanan_darah=None)

    # === GET method: ambil dari session ===
    records       = session.get('hasil_rekomendasi', [])
    kategori      = session.get('kategori', None)
    (min_n, max_n)= session.get('batas_natrium', (0, 0))
    (min_sdt, max_sdt) = session.get('batas_sdt', (0, 0))
    takaran_praktis = session.get('takaran_praktis', None)
    tekanan_darah  = session.get('tekanan_darah', None)

    return render_template('hasil_rekomendasi.html',
                           hasil=records,
                           error=None,
                           show_result=bool(records),
                           kategori=kategori,
                           batas_natrium=f"{min_n} - {max_n} mg" if min_n else None,
                           batas_sdt=(min_sdt, max_sdt),
                           takaran_praktis=takaran_praktis,
                           tekanan_darah=tekanan_darah)

                         
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
  