from flask import Flask, render_template, request, session, redirect, url_for
import pandas as pd
import numpy as np
import os
import joblib

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

# Load model dan data
model = joblib.load('model.pkl')
menu_df = pd.read_csv('data_kombinasi_na.csv')

# Hitung total natrium jika belum tersedia
if 'total_natrium' not in menu_df.columns:
    menu_df['total_natrium'] = (
        menu_df['natrium_makan_pagi'] +
        menu_df['natrium_makan_siang'] +
        menu_df['natrium_makan_malam'] +
        menu_df['natrium_snack_1'] +
        menu_df['natrium_snack_2']
    )

def derajat_dari_tekanan_darah(sistolik, diastolik):
    if sistolik >= 180 or diastolik >= 120:
        return 3
    elif 160 <= sistolik <= 179 or 100 <= diastolik <= 109:
        return 2
    elif 140 <= sistolik <= 159 or 90 <= diastolik <= 99:
        return 1
    else:
        return 0

def hitung_total_natrium(makanan):
    total = 0
    for waktu_makan in ['makan_pagi', 'makan_siang', 'makan_malam', 'snack_1', 'snack_2']:
        nama = makanan.get(waktu_makan, '').strip().lower()
        baris = menu_df[menu_df[waktu_makan].str.lower() == nama]
        if not baris.empty:
            total += float(baris.iloc[0][f'natrium_{waktu_makan}'])
    return total

def batas_natrium_dari_derajat(derajat):
    if derajat == 1:
        return (1000, 1200)
    elif derajat == 2:
        return (600, 800)
    elif derajat == 3:
        return (200, 400)
    else:
        return (0, 200)

def penjelasan_sdt_praktis(min_sdt, max_sdt):
    rata2 = (min_sdt + max_sdt) / 2
    if rata2 <= 0.2:
        return "setara 1/10 sendok teh garam"
    elif rata2 <= 0.45:
        return "setara 1/3 sendok teh garam"
    elif rata2 <= 0.6:
        return "setara 1/2 sendok teh garam"
    else:
        return "perkiraan sesuai kebutuhan harian"

@app.route('/')
def halaman_awal():
    session.pop('hasil_rekomendasi', None)
    return render_template('halaman_awal.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/rekomendasi')
def rekomendasi():
    kolom_makanan = ['makan_pagi', 'makan_siang', 'makan_malam', 'snack_1', 'snack_2']
    semua_makanan = set()
    for kolom in kolom_makanan:
        semua_makanan.update(menu_df[kolom].dropna().str.strip().str.lower().unique())
    daftar_makanan = sorted(semua_makanan)
    return render_template('rekomendasi.html', show_result=False, daftar_makanan=daftar_makanan)

@app.route('/hasil_rekomendasi', methods=['POST'])
def hasil_rekomendasi():
    makanan = {
        'makan_pagi': request.form.get('makan_pagi'),
        'makan_siang': request.form.get('makan_siang'),
        'makan_malam': request.form.get('makan_malam'),
        'snack_1': request.form.get('snack_1'),
        'snack_2': request.form.get('snack_2')
    }

    total_natrium = hitung_total_natrium(makanan)
    fitur_input = np.array([[total_natrium]*5])
    derajat_makanan = model.predict(fitur_input)[0]

    tekanan_darah = request.form.get('tekanan_darah')
    try:
        sistolik, diastolik = map(int, tekanan_darah.strip().split('/'))
        derajat_pasien = derajat_dari_tekanan_darah(sistolik, diastolik)
    except:
        return "⚠️ Format tekanan darah salah. Gunakan format: 160/100"

    if derajat_makanan == derajat_pasien:
        status = "✅ Makanan yang Anda pilih sesuai dengan kondisi tekanan darah Anda."
    else:
        status = (
            f"⚠️ Makanan yang Anda pilih (Derajat {derajat_makanan}) tidak sesuai dengan kondisi tekanan darah Anda (Derajat {derajat_pasien}). "
            "Berikut rekomendasi makanan yang sesuai untuk Anda:"
        )

    batas_min, batas_max = batas_natrium_dari_derajat(derajat_pasien)
    sdt_min = round(batas_min / 2000, 2)
    sdt_max = round(batas_max / 2000, 2)
    takaran = penjelasan_sdt_praktis(sdt_min, sdt_max)

    # Ambil rekomendasi paling dekat dengan batas bawah (bukan rata-rata)
    menu_sesuai = menu_df[menu_df['derajat'] == derajat_pasien].copy()
    menu_sesuai['jarak'] = abs(menu_sesuai['total_natrium'] - batas_min)
    hasil_df = menu_sesuai.sort_values(by='jarak').head(5)

    return render_template('hasil_rekomendasi.html',
        makanan=makanan,
        total_natrium=total_natrium,
        tekanan_darah=tekanan_darah,
        derajat_pasien=derajat_pasien,
        derajat_makanan=derajat_makanan,
        status=status,
        batas_natrium=f"{batas_min} - {batas_max}",
        batas_sdt=(sdt_min, sdt_max),
        takaran_praktis=takaran,
        hasil=hasil_df.to_dict(orient='records'),
        show_result=True)

if __name__ == '__main__':
    app.run(debug=True)
