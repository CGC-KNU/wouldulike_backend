# -*- coding: utf-8 -*-
from pathlib import Path
path = Path('coupons/api/views.py')
text = path.read_text(encoding='utf-8')
text = text.replace('"??? ???????."', '"�ʼ� �ʵ��Դϴ�."')
path.write_text(text, encoding='utf-8')
