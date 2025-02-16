code = """
os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 네이버와 카카오의 주가 데이터 준비
naver_data = pd.DataFrame({
    'Date': ['2025-01-14', '2025-01-15', '2025-01-16', '2025-01-17', '2025-01-20', 
            '2025-01-21', '2025-01-22', '2025-01-23', '2025-01-24', '2025-01-31',
            '2025-02-03', '2025-02-04', '2025-02-05', '2025-02-06', '2025-02-07',
            '2025-02-10', '2025-02-11', '2025-02-12', '2025-02-13', '2025-02-14'],
    'NAVER': [202000, 206500, 206500, 209000, 205000, 204500, 204000, 204500, 204000, 
             216500, 217000, 218500, 229000, 232000, 225500, 227500, 228500, 225000, 
             220000, 221000]
})

kakao_data = pd.DataFrame({
    'Date': ['2025-01-14', '2025-01-15', '2025-01-16', '2025-01-17', '2025-01-20',
            '2025-01-21', '2025-01-22', '2025-01-23', '2025-01-24', '2025-01-31',
            '2025-02-03', '2025-02-04', '2025-02-05', '2025-02-06', '2025-02-07',
            '2025-02-10', '2025-02-11', '2025-02-12', '2025-02-13', '2025-02-14'],
    'KAKAO': [36850, 37000, 36900, 36400, 36450, 36450, 36300, 35750, 35750, 
             38350, 41800, 40900, 43200, 45300, 44500, 42500, 42850, 42000, 
             40200, 38750]
})

# 데이터 전처리
naver_data['Date'] = pd.to_datetime(naver_data['Date'])
kakao_data['Date'] = pd.to_datetime(kakao_data['Date'])

# 기준일 대비 변화율 계산
naver_base = naver_data['NAVER'].iloc[0]
kakao_base = kakao_data['KAKAO'].iloc[0]

naver_data['NAVER_Change'] = (naver_data['NAVER'] - naver_base) / naver_base * 100
kakao_data['KAKAO_Change'] = (kakao_data['KAKAO'] - kakao_base) / kakao_base * 100

# 그래프 그리기
plt.figure(figsize=(12, 6))
plt.plot(naver_data['Date'], naver_data['NAVER_Change'], label='NAVER', linewidth=2)
plt.plot(kakao_data['Date'], kakao_data['KAKAO_Change'], label='KAKAO', linewidth=2)

plt.title('NAVER vs KAKAO 주가 변동률 비교 (기준일: 2025-01-14)', fontsize=12)
plt.xlabel('날짜')
plt.ylabel('변동률 (%)')
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend()

# x축 날짜 포맷 조정
plt.xticks(rotation=45)

# 그래프 여백 조정
plt.tight_layout()

# 그래프 저장
#plt.savefig('stock_comparison.png')

import io
import base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.getvalue()).decode()

print(image_base64)
"""

from rizaio import Riza
client = Riza()

resp = client.command.exec(
    runtime_revision_id="01JM3JQFH1HW3SKDNEJTJJH740",
    language="python",
    code=code,
    env={
        "DEBUG": "true",
    }
)
    
print(f"response: {dict(resp)}") # includling exit_code, stdout, stderr
output = dict(resp)

from PIL import Image
from io import BytesIO
import base64
base64Img = resp.stdout
im = Image.open(BytesIO(base64.b64decode(base64Img)))
im.save('image1.png', 'PNG')
