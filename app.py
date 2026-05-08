from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
import glob
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ==========================================
# CẤU HÌNH THƯ MỤC CHỨA CÁC ĐỀ THI
# ==========================================
# Trỏ tới thư mục 'data' (nơi chứa De_06.json, De_07.json...)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ==========================================
# CẤU HÌNH KẾT NỐI GOOGLE SHEETS
# ==========================================
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/1WqYaDrJaiEbUCrvozAVhc-wFLSWMocfApfk39Ixc23U/edit?gid=0#gid=0'

def ghi_diem_vao_sheets(ma_de, diem, tong_cau, thoi_gian):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_file('google_key.json', scopes=scopes)
        client = gspread.authorize(credentials)

        sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1

        diem_hien_thi = f"{diem}/{tong_cau}"
        sheet.append_row([thoi_gian, ma_de, diem_hien_thi])
    except Exception as e:
        import traceback
        print("Lỗi lưu Google Sheets chi tiết:")
        traceback.print_exc()

# ==========================================
# XỬ LÝ ĐỌC FILE JSON TỪ THƯ MỤC DATA
# ==========================================
def get_danh_sach_de():
    """Quét thư mục data và lấy danh sách tên các đề thi"""
    files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    return [os.path.basename(f).replace('.json', '') for f in files]

def load_exam(ma_de):
    """Đọc nội dung của 1 đề thi cụ thể"""
    filepath = os.path.join(DATA_DIR, f"{ma_de}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # --- ĐOẠN CODE THÔNG MINH TỰ ĐỘNG SỬA LỖI JSON ---
            # Nếu file JSON bị bọc bởi dictionary (như {"De_06": [...]})
            if isinstance(data, dict):
                # Nếu có key trùng tên mã đề thì lấy list bên trong
                if ma_de in data:
                    return data[ma_de]
                # Nếu key khác tên, lấy luôn list đầu tiên tìm thấy
                elif len(data.values()) > 0:
                    return list(data.values())[0]
            
            # Nếu file JSON đã chuẩn là một list [...] rồi thì trả về nguyên bản
            return data
            
    return None

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def index():
    danh_sach_de = get_danh_sach_de()
    return render_template('index.html', danh_sach_de=danh_sach_de)

@app.route('/exam/<ma_de>')
def exam(ma_de):
    questions = load_exam(ma_de)
    if not questions:
        return redirect(url_for('index'))

    # Gom nhóm câu hỏi theo phan_thi, giữ nguyên thứ tự
    sections = {}
    for q in questions:
        phan = q.get('phan_thi', 'Phần chính')
        if phan not in sections:
            sections[phan] = []
        sections[phan].append(q)

    return render_template('exam.html', ma_de=ma_de, questions=questions, sections=sections)

@app.route('/nop_bai', methods=['POST'])
def nop_bai():
    ma_de = request.form.get('ma_de')
    questions = load_exam(ma_de)
    
    if not ma_de or not questions:
        return redirect(url_for('index'))

    diem = 0
    tong_cau = len(questions)
    chi_tiet = []

    for cau in questions:
        id_cau = str(cau.get('id_cau', ''))
        loai = cau.get('loai_cau_hoi', 'trac_nghiem')
        ket_qua = {
            'id_cau': cau.get('id_cau', ''),
            'loai_cau_hoi': loai,
            'noi_dung_cau_hoi': cau.get('noi_dung_cau_hoi', ''), 
            'dung': False,
            'dap_an_hs': '',
            'dap_an_chuan': ''
        }

        if loai == 'trac_nghiem':
            dap_an_hs = request.form.get(f'cau_{id_cau}', '').strip().upper()
            dap_an_dung = cau.get('dap_an_dung', '').upper()
            ket_qua.update({
                'dap_an_hs': dap_an_hs,
                'dap_an_chuan': dap_an_dung,
                'A': cau.get('A', ''),
                'B': cau.get('B', ''),
                'C': cau.get('C', ''),
                'D': cau.get('D', '')
            })
            if dap_an_hs == dap_an_dung and dap_an_hs != '':
                ket_qua['dung'] = True
                diem += 1

        elif loai == 'tu_luan_ngan':
            dap_an_hs = request.form.get(f'cau_{id_cau}', '').strip()
            dap_an_chap_nhan = cau.get('dap_an_chap_nhan', [])
            ket_qua.update({
                'dap_an_hs': dap_an_hs,
                'dap_an_chuan': ', '.join(dap_an_chap_nhan)
            })
            if dap_an_hs in dap_an_chap_nhan:
                ket_qua['dung'] = True
                diem += 1

        chi_tiet.append(ket_qua)

    # LƯU ĐIỂM VÀO GOOGLE SHEETS
    thoi_gian_nop = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ghi_diem_vao_sheets(ma_de, diem, tong_cau, thoi_gian_nop)

    return render_template(
        'ketqua.html',
        ma_de=ma_de,
        diem=diem,
        tong_cau=tong_cau,
        chi_tiet=chi_tiet
    )

if __name__ == '__main__':
    app.run(debug=True)