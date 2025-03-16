import numpy as np
import matplotlib.pyplot as plt

# 데이터 생성
x = np.linspace(-2*np.pi, 2*np.pi, 1000)
y = np.cos(x)

# 그래프 설정
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.grid(True)
plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
plt.axvline(x=0, color='k', linestyle='-', alpha=0.3)

# 제목과 레이블 설정
plt.title('Cosine Function Graph', fontsize=16)
plt.xlabel('x (radians)', fontsize=12)
plt.ylabel('cos(x)', fontsize=12)

# x축에 주요 지점 표시
ticks = [-2*np.pi, -3*np.pi/2, -np.pi, -np.pi/2, 0, np.pi/2, np.pi, 3*np.pi/2, 2*np.pi]
labels = [r'-2$\pi$', r'-3$\pi$/2', r'-$\pi$', r'-$\pi$/2', '0', 
          r'$\pi$/2', r'$\pi$', r'3$\pi$/2', r'2$\pi$']
plt.xticks(ticks, labels)

# y축 범위 설정
plt.ylim(-1.5, 1.5)

plt.tight_layout()
#plt.show()

import io
import base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.getvalue()).decode()

print(image_base64)