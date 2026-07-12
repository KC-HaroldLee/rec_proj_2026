"""라우터 모듈 간 순환 import를 피하기 위해 Jinja2Templates 인스턴스를 따로 둔다."""
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
