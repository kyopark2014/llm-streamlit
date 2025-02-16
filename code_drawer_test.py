code = """
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# Get data for both companies from 2010
kakao = yf.download('035720.KS', start='2010-01-01')
naver = yf.download('035420.KS', start='2010-01-01')

# Create the plot
plt.figure(figsize=(15, 8))

# Plot both lines
plt.plot(kakao.index, kakao['Close'], label='Kakao', color='yellow')
plt.plot(naver.index, naver['Close'], label='Naver', color='green')

# Customize the plot
plt.title('Stock Price Comparison: Kakao vs Naver (2010-Present)', fontsize=14)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Price (KRW)', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(fontsize=10)

# Rotate x-axis labels for better readability
plt.xticks(rotation=45)

# Format y-axis with thousand separator
plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

# Adjust layout to prevent label cutoff
plt.tight_layout()

plt.show()
"""

import matplotlib.pyplot as plt
print('avialot style: ', plt.style.available)

import re
code = re.sub(r"seaborn", "classic", code)
code = re.sub(r"plt.savefig", "#plt.savefig", code)

pre = f"os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'\n"  # matplatlib
post = """\n
import io
import base64
buffer = io.BytesIO()
plt.savefig(buffer, format='png')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.getvalue()).decode()

print(image_base64)
"""

code = pre + code + post    
print(f"code: {code}")

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
